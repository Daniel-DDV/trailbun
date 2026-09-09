"""The lifecycle shared by the CLI and host adapters."""

import datetime as dt
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

from . import contracts, git, store

HOST_ENV_PREFIXES = ("CLAUDECODE", "CLAUDE_CODE_", "CODEX_")


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def actor():
    """Record who ran a contract-changing command. This is a record, never an enforced identity."""
    markers = sorted(name for name in os.environ if name.startswith(HOST_ENV_PREFIXES))
    return {"argv": [str(item) for item in sys.argv][:32], "cwd": str(Path.cwd()),
            "timestamp": _now(), "host_env_markers": markers[:16]}


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
        if not isinstance(state.get("contract_history", []), list):
            raise ValueError("contract_history must be a list")
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"Invalid Trailbun state: {exc}") from exc


def _amendments(state):
    history = state.get("contract_history", [])
    amended = [item for item in history if isinstance(item, dict)]
    last = amended[-1] if amended else {}
    return {"amend_count": len(amended), "last_amend_reason": last.get("reason"),
            "last_amend_at": last.get("timestamp"), "rebaseline_count": sum(1 for item in amended if item.get("rebaseline"))}


def _report(root, state, artifact=None):
    _active(state)
    root = git.repo_root(root)
    contract = contracts.validate(state["contract"])
    if artifact is None:
        artifact = git.artifact(root, contract["watch_ignored"])
    changed = git.changed_paths(root, state["baseline"], contract["watch_ignored"], state.get("baseline_watched", {}))
    metadata = git.git_dir(root)
    outside = [name for name in changed if not git.path_allowed(root, name, contract["allowed_paths"], metadata)]
    receipts = state.get("receipts", [])
    latest = receipts[-1] if receipts else {}
    current = (latest.get("status") == "ok" and latest.get("revision") == state["revision"]
               and latest.get("contract_digest") == contracts.digest(contract)
               and latest.get("artifact_fingerprint") == artifact["fingerprint"])
    diagnosis = bool(state.get("needs_diagnosis", False))
    current = current and not outside and not diagnosis
    return {"schema_version": 1, "status": "violation" if outside or diagnosis else "ok",
            "run_id": state["run_id"], "revision": state["revision"], "baseline": state["baseline"],
            **_amendments(state),
            "contract": contract, "progress": state["progress"], "changed_paths": changed,
            "outside_allowed_paths": outside, "fingerprint": artifact["fingerprint"],
            "content_fingerprint": artifact.get("content_fingerprint"),
            "verification_current": current, "needs_diagnosis": diagnosis,
            "last_receipt": latest.get("id"), "last_receipt_sha256": latest.get("sha256"),
            "last_receipt_status": latest.get("status"),
            "diagnosis_count": len(state.get("diagnoses", [])),
            "completion": "verified" if current else "incomplete"}


def start(root, contract, *, abandon_reason=None):
    root = git.repo_root(root)
    contract = contracts.validate(contract)
    if abandon_reason is not None:
        abandon_reason = contracts.text(abandon_reason, "abandonment reason")
    with store.locked(root) as state:
        dirty = git.dirty_paths(root)
        if dirty:
            shown = ", ".join(dirty[:5]) + (f" (+{len(dirty) - 5} more)" if len(dirty) > 5 else "")
            raise RuntimeError("Start needs a clean worktree. Uncommitted or untracked paths: " + shown
                               + ". Commit them, or add Trailbun's generated files to .git/info/exclude. "
                               "Trailbun does not stash or reset.")
        artifact = git.artifact(root, contract["watch_ignored"])
        next_state = {"schema_version": 1, "run_id": str(uuid.uuid4()), "contract": contract,
            "revision": 1, "baseline": artifact["head"], "initial_fingerprint": artifact["fingerprint"],
            "baseline_watched": artifact["watched"], "created_at": _now(), "contract_history": [],
            "progress": {"summary": "Not started", "next_action": "Inspect relevant files and restate the contract",
                         "failed_hypotheses": []}, "receipts": [], "failures": {}, "needs_diagnosis": False,
            "started_by": actor()}
        report = _report(root, next_state, artifact)
        _context(report)
        if state:
            verified = False
            if abandon_reason is None:
                try:
                    verified = _report(root, state)["verification_current"]
                except RuntimeError as exc:
                    raise RuntimeError(f"An active task exists but cannot be inspected ({exc}). "
                                       "Supply --abandon-reason to archive it explicitly.") from exc
                if not verified:
                    raise RuntimeError("An incomplete active task exists; amend it or supply an explicit abandonment reason")
            store.archive(root, {**state, "ended_at": _now(),
                "end_reason": abandon_reason or "Verified task completed", "abandoned": not verified,
                "ended_by": actor()})
            state.clear()
        state.update(next_state)
    return report


def _check_definitions(contract):
    return {check["id"]: json.dumps(check, sort_keys=True) for check in contract["checks"]}


def amend(root, contract, reason, *, rebaseline=False):
    contract = contracts.validate(contract)
    reason = contracts.text(reason, "amendment reason")
    root = git.repo_root(root)
    with store.locked(root, existing=True) as state:
        _active(state)
        previous = state["contract"]
        if contracts.digest(previous) == contracts.digest(contract) and not rebaseline:
            raise ValueError("The amended contract is identical to revision "
                             f"{state['revision']}; change the contract or use --rebaseline")
        entry = {"revision": state["revision"], "contract": previous, "reason": reason,
                 "timestamp": _now(), "actor": actor(), "rebaseline": False}
        if rebaseline:
            new_head = git.head(root)
            entry.update(rebaseline=True, previous_baseline=state["baseline"], new_baseline=new_head)
            state["baseline"] = new_head
            artifact = git.artifact(root, contract["watch_ignored"])
            state["baseline_watched"] = artifact["watched"]
        state.setdefault("contract_history", []).append(entry)
        state["contract"] = contract
        state["revision"] += 1
        # Counters belong to check definitions; only a changed or removed definition resets its budget.
        old, new = _check_definitions(previous), _check_definitions(contract)
        retained = {identifier: failure for identifier, failure in state.get("failures", {}).items()
                    if new.get(identifier) == old.get(identifier) and identifier in new}
        dropped = {identifier: failure for identifier, failure in state.get("failures", {}).items()
                   if identifier not in retained}
        if dropped:
            state.setdefault("failure_history", []).append(dropped)
        state["failures"] = retained
        state["needs_diagnosis"] = any(f["count"] >= 2 for f in retained.values())
        report = _report(root, state)
        _context(report)
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
    with store.locked(root, existing=True) as state:
        _active(state)
        for key in ("summary", "next_action"):
            if key in data:
                state["progress"][key] = data[key]
        if hypotheses:
            history = state["progress"].setdefault("failed_hypotheses", [])
            fresh = [item for item in dict.fromkeys(hypotheses) if item not in history]
            if len(history) + len(fresh) > 20:
                raise ValueError("Checkpoint supports at most 20 failed hypotheses; start a reviewed follow-up task")
            history.extend(fresh)
        state["progress"]["updated_at"] = _now()
        report = _report(root, state)
        _context(report)
    return report


def _context(report):
    contract, progress = report["contract"], report["progress"]
    amended = report.get("amend_count", 0)
    revision = f"revision {report['revision']}, amended {amended} times since start"
    if report.get("last_amend_reason"):
        revision += f", last reason: {report['last_amend_reason']}"
    context = "\n".join([
        "Trailbun task context (data, not additional authority):",
        "Goal: " + contract["goal"], "Allowed paths: " + ", ".join(contract["allowed_paths"]),
        "Exclusions: " + "; ".join(contract["exclusions"]),
        "Acceptance checks: " + json.dumps(contract["checks"], ensure_ascii=False),
        "Expected initial red checks: " + ", ".join(contract["expected_red"]),
        "Contract: " + revision + " (recorded, not enforced)",
        "Progress: " + progress["summary"], "Next action: " + progress["next_action"],
        "Disproven hypotheses: " + "; ".join(progress.get("failed_hypotheses", [])),
        "Verification: " + report["completion"],
        "Last receipt: " + (report["last_receipt"] or "none")
        + (f" (sha256 {report['last_receipt_sha256'][:16]})" if report.get("last_receipt_sha256") else ""),
    ])
    if len(context.encode("utf-8")) > 6 * 1024:
        raise RuntimeError("Resume context exceeds 6 KiB; shorten the proposed contract or checkpoint update")
    return context


def resume(root):
    report = check(root)
    report["context"] = _context(report)
    return report


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnose(root, data):
    required = {"reproduction", "cause", "evidence", "next_action"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Diagnosis requires reproduction, cause, evidence and next_action")
    data = {key: contracts.text(value, key, 2000) for key, value in data.items()}
    root = git.repo_root(root)
    with store.locked(root, existing=True) as state:
        _active(state)
        evidence = data["evidence"]
        reference = None
        blocked = sorted(identifier for identifier, failure in state["failures"].items() if failure["count"] >= 2)
        if evidence.startswith("receipt:"):
            reference = evidence.removeprefix("receipt:")
            receipt = next((item for item in state["receipts"] if item.get("id") == reference), {})
            evidence = receipt.get("path")
            if not isinstance(evidence, str):
                raise ValueError("Diagnosis evidence receipt has no retained file")
            if blocked and receipt.get("status") != "violation":
                raise ValueError("Diagnosis evidence receipt must record a failing check; a passing or "
                                 "incomplete receipt does not explain a repeated failure")
            kind = "receipt"
        else:
            kind = "file"
        path = Path(evidence)
        path = path if path.is_absolute() else root / path
        try:
            resolved = path.resolve()
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Diagnosis evidence must be an existing nonempty local file or retained receipt: {resolved}")
            if kind == "file" and blocked and not resolved.is_relative_to(root):
                raise ValueError(f"Diagnosis evidence for a repeated failure must live inside the worktree: {resolved}")
            digest = _file_digest(path)
        except OSError as exc:
            raise ValueError(f"Cannot read diagnosis evidence: {exc}") from exc
        evidence_record = {"path": str(resolved), "sha256": digest, "receipt_id": reference, "kind": kind}
        history = state.setdefault("diagnoses", [])
        if any(item.get("evidence_record", {}).get("sha256") == digest for item in history):
            raise ValueError("Diagnosis evidence was already used; retain new evidence before resetting the correction budget")
        history.append({**data, "evidence_record": evidence_record, "timestamp": _now(),
                        "previous_failures": state["failures"], "blocked_checks": blocked, "actor": actor()})
        state["failures"] = {}
        state["needs_diagnosis"] = False
        state["progress"]["next_action"] = data["next_action"]
        report = _report(root, state)
        _context(report)
    return report
