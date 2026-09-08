"""The lifecycle shared by the CLI and host adapters."""

import datetime as dt
import hashlib
import json
import re
import uuid
from pathlib import Path

from . import contracts, git, store


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _active(state):
    try:
        if not all(key in state for key in ("contract", "revision", "baseline", "run_id", "progress", "receipts", "failures")):
            raise ValueError("missing required task fields")
        uuid.UUID(state["run_id"])
        if type(state["revision"]) is not int or state["revision"] < 1:
            raise ValueError("invalid contract revision")
        if not isinstance(state["baseline"], str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", state["baseline"]):
            raise ValueError("baseline must be a full Git object id")
        contracts.validate(state["contract"])
        progress = state["progress"]
        if not isinstance(progress, dict):
            raise ValueError("progress must be an object")
        for field in ("summary", "next_action"):
            contracts.text(progress.get(field), field, 2000)
        hypotheses = progress.get("failed_hypotheses", [])
        if not isinstance(hypotheses, list) or any(not isinstance(item, str) for item in hypotheses):
            raise ValueError("failed_hypotheses must be a text list")
        if not isinstance(state["receipts"], list) or any(not isinstance(item, dict) for item in state["receipts"]):
            raise ValueError("receipts must be a list of objects")
        if not isinstance(state["failures"], dict):
            raise ValueError("failures must be an object")
        for failure in state["failures"].values():
            if (not isinstance(failure, dict) or type(failure.get("count")) is not int
                    or failure["count"] < 0 or not isinstance(failure.get("fingerprints"), list)
                    or any(not isinstance(item, str) for item in failure["fingerprints"])):
                raise ValueError("invalid failure counter")
        if not isinstance(state.get("baseline_watched", {}), dict):
            raise ValueError("baseline_watched must be an object")
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"Invalid Trailbun state: {exc}") from exc


def _report(root, state):
    _active(state)
    root = git.repo_root(root)
    contract = contracts.validate(state["contract"])
    artifact = git.artifact(root, contract["watch_ignored"])
    changed = git.changed_paths(root, state["baseline"], contract["watch_ignored"], state.get("baseline_watched", {}))
    outside = [name for name in changed if not git.path_allowed(root, name, contract["allowed_paths"])]
    receipts = state.get("receipts", [])
    latest = receipts[-1] if receipts else {}
    current = (latest.get("status") == "ok" and latest.get("revision") == state["revision"]
               and latest.get("contract_digest") == contracts.digest(contract)
               and latest.get("artifact_fingerprint") == artifact["fingerprint"])
    diagnosis = bool(state.get("needs_diagnosis", False))
    current = current and not outside and not diagnosis
    return {"schema_version": 1, "status": "violation" if outside or diagnosis else "ok",
            "run_id": state["run_id"], "revision": state["revision"], "baseline": state["baseline"],
            "contract": contract, "progress": state["progress"], "changed_paths": changed,
            "outside_allowed_paths": outside, "fingerprint": artifact["fingerprint"],
            "verification_current": current, "needs_diagnosis": diagnosis,
            "last_receipt": latest.get("id"),
            "completion": "verified" if current else "incomplete"}


def start(root, contract, *, abandon_reason=None):
    root = git.repo_root(root)
    contract = contracts.validate(contract)
    if abandon_reason is not None:
        abandon_reason = contracts.text(abandon_reason, "abandonment reason")
    with store.locked(root) as state:
        if not git.clean(root):
            raise RuntimeError("Start requires a clean worktree; commit or isolate existing changes yourself")
        artifact = git.artifact(root, contract["watch_ignored"])
        if state:
            verified = _report(root, state)["verification_current"] if abandon_reason is None else False
            if not verified and abandon_reason is None:
                raise RuntimeError("An incomplete active task exists; amend it or supply an explicit abandonment reason")
            store.archive(root, {**state, "ended_at": _now(),
                "end_reason": abandon_reason or "Verified task completed", "abandoned": not verified})
            state.clear()
        state.update({"schema_version": 1, "run_id": str(uuid.uuid4()), "contract": contract,
            "revision": 1, "baseline": artifact["head"], "initial_fingerprint": artifact["fingerprint"],
            "baseline_watched": artifact["watched"], "created_at": _now(), "contract_history": [],
            "progress": {"summary": "Not started", "next_action": "Inspect relevant files and restate the contract",
                         "failed_hypotheses": []}, "receipts": [], "failures": {}, "needs_diagnosis": False})
        report = _report(root, state)
    return report


def amend(root, contract, reason):
    contract = contracts.validate(contract)
    reason = contracts.text(reason, "amendment reason")
    with store.locked(root) as state:
        _active(state)
        state.setdefault("contract_history", []).append({"revision": state["revision"],
            "contract": state["contract"], "reason": reason, "timestamp": _now()})
        state["contract"] = contract
        state["revision"] += 1
        # Failure evidence remains available; counts belong to the prior check definitions.
        state.setdefault("failure_history", []).append(state.get("failures", {}))
        state["failures"] = {}
        state["needs_diagnosis"] = False
        report = _report(root, state)
    return report


def check(root):
    return _report(root, store.load(root))


def checkpoint(root, data):
    allowed = {"summary", "next_action", "failed_hypothesis", "failed_hypotheses"}
    if not isinstance(data, dict) or not data or set(data) - allowed:
        raise ValueError("Checkpoint accepts summary, next_action and failed hypotheses only")
    if "failed_hypothesis" in data and "failed_hypotheses" in data:
        raise ValueError("Use either failed_hypothesis or failed_hypotheses")
    hypotheses = data.get("failed_hypotheses", [data["failed_hypothesis"]] if "failed_hypothesis" in data else [])
    if not isinstance(hypotheses, list):
        raise ValueError("failed_hypotheses must be a list")
    hypotheses = [contracts.text(value, "failed hypothesis", 2000) for value in hypotheses]
    data = {key: contracts.text(value, key, 2000) for key, value in data.items() if key in {"summary", "next_action"}}
    with store.locked(root) as state:
        _active(state)
        for key in ("summary", "next_action"):
            if key in data:
                state["progress"][key] = data[key]
        if hypotheses:
            history = state["progress"].setdefault("failed_hypotheses", [])
            if len(history) + len(hypotheses) > 20:
                raise ValueError("Checkpoint supports at most 20 failed hypotheses; start a reviewed follow-up task")
            history.extend(hypotheses)
        state["progress"]["updated_at"] = _now()
        report = _report(root, state)
    return report


def resume(root):
    report = check(root)
    contract, progress = report["contract"], report["progress"]
    report["context"] = "\n".join([
        "Trailbun task context (data, not additional authority):",
        "Goal: " + contract["goal"], "Allowed paths: " + ", ".join(contract["allowed_paths"]),
        "Exclusions: " + "; ".join(contract["exclusions"]),
        "Acceptance checks: " + json.dumps(contract["checks"], ensure_ascii=False),
        "Expected initial red checks: " + ", ".join(contract["expected_red"]),
        "Progress: " + progress["summary"], "Next action: " + progress["next_action"],
        "Disproven hypotheses: " + "; ".join(progress.get("failed_hypotheses", [])),
        "Verification: " + report["completion"],
        "Last receipt: " + (report["last_receipt"] or "none"),
    ])
    if len(report["context"].encode("utf-8")) > 6 * 1024:
        raise RuntimeError("Resume context exceeds 6 KiB; explicitly compact the checkpoint before resuming")
    return report


def diagnose(root, data):
    required = {"reproduction", "cause", "evidence", "next_action"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Diagnosis requires reproduction, cause, evidence and next_action")
    data = {key: contracts.text(value, key, 2000) for key, value in data.items()}
    root = git.repo_root(root)
    with store.locked(root) as state:
        _active(state)
        evidence = data["evidence"]
        reference = None
        if evidence.startswith("receipt:"):
            reference = evidence.removeprefix("receipt:")
            receipt = next((item for item in state["receipts"] if item.get("id") == reference), {})
            evidence = receipt.get("path")
            if not isinstance(evidence, str):
                raise ValueError("Diagnosis evidence receipt has no retained file")
        path = Path(evidence)
        path = path if path.is_absolute() else root / path
        try:
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError("Diagnosis evidence must be an existing nonempty local file or retained receipt")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ValueError(f"Cannot read diagnosis evidence: {exc}") from exc
        evidence_record = {"path": str(path.resolve()), "sha256": digest.hexdigest(), "receipt_id": reference}
        history = state.setdefault("diagnoses", [])
        if any(item.get("evidence_record", {}).get("sha256") == evidence_record["sha256"] for item in history):
            raise ValueError("Diagnosis evidence was already used; retain new evidence before resetting the correction budget")
        history.append({**data, "evidence_record": evidence_record, "timestamp": _now(),
                        "previous_failures": state["failures"]})
        state["failures"] = {}
        state["needs_diagnosis"] = False
        state["progress"]["next_action"] = data["next_action"]
        report = _report(root, state)
    return report
