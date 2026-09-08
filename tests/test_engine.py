import pytest

from conftest import git_command
from trailbun import contracts, engine, git, store


def test_start_requires_clean_worktree_and_does_not_overwrite_active_run(repo, contract):
    (repo / "new.txt").write_text("untracked")
    with pytest.raises(RuntimeError, match="clean"):
        engine.start(repo, contract)
    (repo / "new.txt").unlink()
    report = engine.start(repo, contract)
    assert report["status"] == "ok"
    with pytest.raises(RuntimeError, match="active"):
        engine.start(repo, contract)
    assert store.load(repo)["baseline"] == git_command(repo, "rev-parse", "HEAD")


def test_committed_outside_edit_is_detected_and_amend_preserves_baseline(repo, contract):
    engine.start(repo, contract)
    baseline = store.load(repo)["baseline"]
    (repo / "outside.py").write_text("outside\n")
    git_command(repo, "add", ".")
    git_command(repo, "commit", "-qm", "outside edit")
    assert engine.check(repo)["outside_allowed_paths"] == ["outside.py"]
    contract["allowed_paths"].append("outside.py")
    report = engine.amend(repo, contract, "The approved fix requires this file")
    assert report["status"] == "ok"
    state = store.load(repo)
    assert state["baseline"] == baseline and state["revision"] == 2
    assert state["contract_history"][0]["revision"] == 1


def test_nested_cwd_cannot_hide_sibling_drift(repo, contract):
    engine.start(repo, contract)
    (repo / "outside.py").write_text("outside\n")
    assert engine.check(repo / "src")["outside_allowed_paths"] == ["outside.py"]


def test_checkpoint_cannot_change_contract_and_resume_is_compact(repo, contract):
    engine.start(repo, contract)
    with pytest.raises(ValueError):
        engine.checkpoint(repo, {"allowed_paths": ["."]})
    engine.checkpoint(repo, {"summary": "Failure reproduced", "next_action": "Change value",
                             "failed_hypothesis": "It was a parse error"})
    report = engine.resume(repo)
    assert "Change value" in report["context"]
    assert report["progress"]["failed_hypotheses"] == ["It was a parse error"]


def test_checkpoint_accepts_hypothesis_list_and_resume_preserves_all(repo, contract):
    engine.start(repo, contract)
    items = [f"Hypothesis {index}" for index in range(6)]
    engine.checkpoint(repo, {"failed_hypotheses": items})
    report = engine.resume(repo)
    assert all(item in report["context"] for item in items)
    with pytest.raises(ValueError):
        engine.checkpoint(repo, {"failed_hypothesis": "one", "failed_hypotheses": ["two"]})


def test_resume_references_receipt_and_fails_explicitly_when_context_is_too_large(repo, contract):
    engine.start(repo, contract)
    with store.locked(repo) as state:
        state["receipts"].append({"id": "receipt-one"})
    assert "receipt-one" in engine.resume(repo)["context"]
    engine.checkpoint(repo, {"failed_hypotheses": ["x" * 1800] * 4})
    with pytest.raises(RuntimeError, match="6 KiB"):
        engine.resume(repo)


def test_new_run_archives_verified_task_or_requires_abandonment_reason(repo, contract):
    first = engine.start(repo, contract)
    with pytest.raises(RuntimeError, match="active"):
        engine.start(repo, contract)
    with store.locked(repo) as state:
        state["receipts"].append({"status": "ok", "revision": state["revision"],
            "artifact_fingerprint": git.artifact(repo)["fingerprint"],
            "contract_digest": contracts.digest(state["contract"])})
    second = engine.start(repo, contract)
    assert first["run_id"] != second["run_id"]
    assert (store.directory(repo) / "archive" / (first["run_id"] + ".json")).is_file()
    third = engine.start(repo, contract, abandon_reason="Task superseded by a new user request")
    assert second["run_id"] != third["run_id"]


def test_verification_becomes_stale_after_mutation(repo, contract):
    engine.start(repo, contract)
    with store.locked(repo) as state:
        state["receipts"].append({"status": "ok", "revision": state["revision"],
             "artifact_fingerprint": git.artifact(repo)["fingerprint"],
             "contract_digest": contracts.digest(state["contract"])})
    assert engine.check(repo)["verification_current"] is True
    (repo / "src/main.py").write_text("value = 2\n")
    assert engine.check(repo)["verification_current"] is False


def test_watched_ignored_baseline_is_not_a_perpetual_change(repo, contract):
    (repo / "ignored").mkdir()
    (repo / "ignored/config").write_text("before")
    contract["watch_ignored"] = ["ignored"]
    engine.start(repo, contract)
    assert engine.check(repo)["changed_paths"] == []
    (repo / "ignored/config").write_text("after")
    assert engine.check(repo)["outside_allowed_paths"] == ["ignored/config"]


def test_removing_a_watched_scope_does_not_create_permanent_false_drift(repo, contract):
    (repo / "ignored").mkdir()
    (repo / "ignored/config").write_text("before")
    contract["watch_ignored"] = ["ignored"]
    engine.start(repo, contract)
    contract["watch_ignored"] = []
    assert engine.amend(repo, contract, "Stop monitoring this explicit ignored input")["changed_paths"] == []


@pytest.mark.parametrize("field,value", [("progress", []), ("baseline", "--help"),
    ("receipts", [None]), ("failures", {"acceptance": {"count": "two"}})])
def test_corrupt_state_is_an_explicit_incomplete_error(repo, contract, field, value):
    engine.start(repo, contract)
    with store.locked(repo) as state:
        state[field] = value
    with pytest.raises(RuntimeError, match="state"):
        engine.resume(repo)


def test_diagnosis_requires_evidence_and_clears_intervention(repo, contract):
    engine.start(repo, contract)
    with store.locked(repo) as state:
        state["needs_diagnosis"] = True
    with pytest.raises(ValueError):
        engine.diagnose(repo, {"next_action": "Try again"})
    data = {"reproduction": "Check acceptance fails", "cause": "Wrong value",
            "evidence": "a confident assertion", "next_action": "Adjust expected branch"}
    with pytest.raises(ValueError, match="evidence"):
        engine.diagnose(repo, data)
    evidence = store.directory(repo) / "diagnostic-output.txt"
    evidence.write_text("The check expected 2 and observed 1", encoding="utf-8")
    report = engine.diagnose(repo, {"reproduction": "Check acceptance fails", "cause": "Wrong value",
        "evidence": str(evidence), "next_action": "Adjust expected branch"})
    assert report["needs_diagnosis"] is False
    assert len(store.load(repo)["diagnoses"][-1]["evidence_record"]["sha256"]) == 64


def test_diagnosis_accepts_retained_receipt_and_resets_documented_failure_budget(repo, contract):
    engine.start(repo, contract)
    receipt = store.directory(repo) / "retained-receipt.json"
    receipt.write_text('{"status":"violation"}', encoding="utf-8")
    with store.locked(repo) as state:
        state["receipts"].append({"id": "one", "path": str(receipt)})
        state["failures"] = {"acceptance": {"count": 2, "fingerprints": ["first", "second"]}}
        state["needs_diagnosis"] = True
    data = {"reproduction": "Run acceptance", "cause": "Branch condition is wrong",
            "evidence": "receipt:one", "next_action": "Fix the condition"}
    engine.diagnose(repo, data)
    state = store.load(repo)
    assert state["failures"] == {}
    assert state["diagnoses"][-1]["previous_failures"]["acceptance"]["count"] == 2
    with store.locked(repo) as state:
        state["needs_diagnosis"] = True
    with pytest.raises(ValueError, match="already used"):
        engine.diagnose(repo, data)
    assert store.load(repo)["needs_diagnosis"] is True


def test_state_update_is_atomic_on_exception_and_worktree_local(repo, contract, tmp_path):
    engine.start(repo, contract)
    with pytest.raises(ValueError):
        with store.locked(repo) as state:
            state["revision"] = 999
            raise ValueError("abort")
    assert store.load(repo)["revision"] == 1
    other = tmp_path / "linked"
    git_command(repo, "worktree", "add", "--detach", str(other))
    assert store.directory(repo) != store.directory(other)
    with pytest.raises(RuntimeError, match="active"):
        store.load(other)
