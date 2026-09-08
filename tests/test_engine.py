import csv
import json
import os
import subprocess
from pathlib import Path

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
    before = store.load(repo)
    with pytest.raises(RuntimeError, match="6 KiB"):
        engine.checkpoint(repo, {"failed_hypotheses": ["x" * 1800] * 4})
    assert store.load(repo) == before
    assert "receipt-one" in engine.resume(repo)["context"]


def test_start_and_amend_reject_intrinsically_unresumable_contracts(repo, contract):
    original = dict(contract)
    contract["goal"] = "goal " * 700
    contract["exclusions"] = ["exclusion " * 300]
    with pytest.raises(RuntimeError, match="6 KiB"):
        engine.start(repo, contract)
    assert not (store.directory(repo) / "state.json").exists()
    engine.start(repo, original)
    before = store.load(repo)
    with pytest.raises(RuntimeError, match="6 KiB"):
        engine.amend(repo, contract, "Oversized revised task")
    assert store.load(repo) == before
    assert engine.resume(repo)["status"] == "ok"


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


def test_runtime_bootstrap_is_owned_ignored_and_idempotent(repo, contract):
    exclude = repo / ".git/info/exclude"
    original = exclude.read_bytes()
    location = store.bootstrap(repo)
    assert location == repo / ".trailbun"
    assert (location / "owner.json").is_file()
    assert exclude.read_bytes().startswith(original)
    once = exclude.read_bytes()
    store.bootstrap(repo)
    assert exclude.read_bytes() == once
    assert git.clean(repo)
    engine.start(repo, contract)


def _windows_acl_rules(path=None, *, sddl=""):
    # Resolve SDDL aliases through Windows, never by account-name/RID heuristics.
    # https://learn.microsoft.com/dotnet/api/system.security.accesscontrol.commonobjectsecurity.getaccessrules
    script = """
$ErrorActionPreference = 'Stop'
if ($env:TRAILBUN_TEST_ACL_SDDL) {
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetSecurityDescriptorSddlForm($env:TRAILBUN_TEST_ACL_SDDL)
} elseif ([System.IO.Directory]::Exists($env:TRAILBUN_TEST_ACL_PATH)) {
    $acl = [System.IO.Directory]::GetAccessControl($env:TRAILBUN_TEST_ACL_PATH)
} else {
    $acl = [System.IO.File]::GetAccessControl($env:TRAILBUN_TEST_ACL_PATH)
}
$rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]) | ForEach-Object {
    @{ sid = $_.IdentityReference.Value; rights = [int]$_.FileSystemRights;
       inheritance = [int]$_.InheritanceFlags; propagation = [int]$_.PropagationFlags;
       inherited = $_.IsInherited; type = [int]$_.AccessControlType }
})
ConvertTo-Json -InputObject $rules -Compress
"""
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
                            env={**os.environ, "TRAILBUN_TEST_ACL_PATH": str(path or ""),
                                 "TRAILBUN_TEST_ACL_SDDL": sddl},
                            check=True, capture_output=True, text=True, timeout=15)
    return json.loads(result.stdout)


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL inheritance")
def test_native_acl_resolution_accepts_local_administrator_alias():
    aliased = _windows_acl_rules(sddl="D:(A;OICI;0x1301bf;;;LA)")
    assert len(aliased) == 1
    sid = aliased[0]["sid"]
    assert sid != "LA"
    assert aliased == _windows_acl_rules(sddl=f"D:(A;OICI;0x1301bf;;;{sid})")


def _operator_acl_matches(rule, sid, *, inheritance=3, inherited=False):
    expected = {"sid": sid, "inheritance": inheritance, "propagation": 0,
                "inherited": inherited, "type": 0}
    return (all(rule[key] == value for key, value in expected.items())
            and rule["rights"] & 0x1301BF == 0x1301BF)  # Modify and Synchronize.


@pytest.mark.parametrize("change", [{"sid": "different-user"}, {"rights": 0x1301BD}])
def test_operator_acl_requires_exact_principal_and_all_modify_rights(change):
    rule = {"sid": "operator", "rights": 0x1301BF, "inheritance": 3,
            "propagation": 0, "inherited": False, "type": 0}
    assert _operator_acl_matches(rule, "operator")
    assert not _operator_acl_matches({**rule, **change}, "operator")


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL inheritance")
@pytest.mark.parametrize("preexisting_full_control", [False, True])
def test_runtime_keeps_explicit_operator_access_after_atomic_replace(repo, monkeypatch, preexisting_full_control):
    result = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"],
                            check=True, capture_output=True, text=True)
    sid = next(csv.reader(result.stdout.splitlines()))[1]
    before = []
    original_grant = store._grant_bootstrap_user
    def record_initial_acl(location):
        if preexisting_full_control:
            icacls = Path(os.environ["SystemRoot"]) / "System32/icacls.exe"
            subprocess.run([str(icacls), str(location), "/grant", f"*{sid}:(OI)(CI)F", "/q"],
                           check=True, capture_output=True, timeout=15)
        before.extend(_windows_acl_rules(location))
        original_grant(location)
    monkeypatch.setattr(store, "_grant_bootstrap_user", record_initial_acl)
    location = store.bootstrap(repo)
    after = _windows_acl_rules(location)
    assert any(_operator_acl_matches(rule, sid) for rule in after)
    # /grant merges existing access. Require precisely the old rights plus Modify,
    # and preserve every unrelated principal's rules without granting new ones.
    previous_rights = current_rights = 0
    for rule in before:
        if rule["sid"] == sid and rule["type"] == 0:
            previous_rights |= rule["rights"]
    for rule in after:
        if rule["sid"] == sid and rule["type"] == 0:
            current_rights |= rule["rights"]
    assert current_rights == previous_rights | 0x1301BF
    if preexisting_full_control:
        assert previous_rights == current_rights == 0x1F01FF
    assert sorted(json.dumps(rule, sort_keys=True) for rule in before if rule["sid"] != sid) == sorted(
        json.dumps(rule, sort_keys=True) for rule in after if rule["sid"] != sid)
    path = location / "state.json"
    store._write(path, {"schema_version": 1, "revision": 1})
    store._write(path, {"schema_version": 1, "revision": 2})
    file_rules = _windows_acl_rules(path)
    assert any(_operator_acl_matches(rule, sid, inheritance=0, inherited=True) for rule in file_rules)
    file_rights = 0
    for rule in file_rules:
        if rule["sid"] == sid and rule["type"] == 0:
            file_rights |= rule["rights"]
    assert file_rights == current_rights
    assert store.load(repo)["revision"] == 2


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL bootstrap")
def test_runtime_does_not_grant_new_user_access_on_later_bootstrap(repo, monkeypatch):
    store.bootstrap(repo)
    def unexpected(_location):
        raise AssertionError("A later sandbox caller must not add its identity")
    monkeypatch.setattr(store, "_grant_bootstrap_user", unexpected)
    store.bootstrap(repo)


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL bootstrap")
def test_failed_acl_provisioning_leaves_no_owned_runtime(repo, monkeypatch):
    def denied(_location):
        raise OSError("ACL provisioning denied")
    monkeypatch.setattr(store, "_grant_bootstrap_user", denied)
    with pytest.raises(RuntimeError, match="outside the native sandbox"):
        store.bootstrap(repo)
    assert not (repo / ".trailbun").exists()


def test_unowned_runtime_conflict_leaves_user_files_and_excludes_untouched(repo):
    location = repo / ".trailbun"
    location.mkdir()
    owned = location / "personal.txt"
    owned.write_text("User-owned data")
    exclude = repo / ".git/info/exclude"
    original = exclude.read_bytes()
    with pytest.raises(RuntimeError, match="ownership"):
        store.bootstrap(repo)
    assert owned.read_text() == "User-owned data"
    assert exclude.read_bytes() == original


def test_tracked_runtime_is_rejected_even_with_an_owner_marker(repo):
    location = store.bootstrap(repo)
    git_command(repo, "add", "-f", ".trailbun/owner.json")
    with pytest.raises(RuntimeError, match="tracked"):
        store.bootstrap(repo)


def test_deleted_tracked_runtime_is_rejected_before_bootstrap_mutations(repo):
    location = repo / ".trailbun"
    location.mkdir()
    (location / "user-file.txt").write_text("User-owned tracked content")
    git_command(repo, "add", ".trailbun/user-file.txt")
    git_command(repo, "commit", "-qm", "Track preexisting directory")
    (location / "user-file.txt").unlink()
    location.rmdir()
    exclude = repo / ".git/info/exclude"
    before = exclude.read_bytes()
    with pytest.raises(RuntimeError, match="tracked"):
        store.bootstrap(repo)
    assert not location.exists()
    assert exclude.read_bytes() == before


def test_existing_legacy_state_is_preserved_and_explicitly_reported(repo):
    legacy = repo / ".git/trailbun/state.json"
    legacy.parent.mkdir()
    legacy.write_text('{"schema_version":1,"retained":true}')
    before = legacy.read_bytes()
    with pytest.raises(RuntimeError, match="Legacy"):
        store.bootstrap(repo)
    assert legacy.read_bytes() == before
    assert not (repo / ".trailbun").exists()


def test_runtime_never_stales_artifact_even_when_all_ignored_files_are_watched(repo, contract):
    contract["watch_ignored"] = ["."]
    engine.start(repo, contract)
    before = git.artifact(repo, ["."])
    engine.checkpoint(repo, {"summary": "Saved progress"})
    after = git.artifact(repo, ["."])
    assert before["fingerprint"] == after["fingerprint"]
    assert not any(name == ".trailbun" or name.startswith(".trailbun/") for name in after["files"])
    assert engine.check(repo)["changed_paths"] == []


def test_runtime_alias_is_never_a_permitted_source_write(repo, contract):
    location = store.bootstrap(repo)
    alias = repo / "runtime-alias"
    try:
        alias.symlink_to(location, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    assert not git.path_allowed(repo, "runtime-alias/state.json", ["."])


def test_bootstrap_error_is_actionable_when_git_ignore_cannot_be_initialized(repo, monkeypatch):
    original = type(repo).open
    def denied(path, *args, **kwargs):
        if path.name == "exclude" and args and ("a" in args[0] or "w" in args[0]):
            raise PermissionError("Protected Git metadata")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(type(repo), "open", denied)
    with pytest.raises(RuntimeError, match="outside"):
        store.bootstrap(repo)
    assert not (repo / ".trailbun").exists()
