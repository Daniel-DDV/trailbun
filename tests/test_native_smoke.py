import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
spec = importlib.util.spec_from_file_location("native_smoke", Path(__file__).parents[1] / "scripts/native_smoke.py")
native = importlib.util.module_from_spec(spec)


def test_model_claim_is_not_native_denial_evidence():
    spec.loader.exec_module(native)
    events = [{"type": "item.completed", "item": {"type": "agent_message", "text": "The patch was denied"}}]
    assert native.failed_patch_events(events, "protected/outside.txt") == []


def test_native_failure_must_target_the_protected_sentinel():
    spec.loader.exec_module(native)
    item = {"type": "item.completed", "item": {"type": "file_change", "status": "failed",
            "changes": [{"path": "C:\\fixture\\protected\\outside.txt", "kind": "update"}]}}
    assert native.failed_patch_events([item], "protected/outside.txt") == [item]
    assert native.failed_patch_events([item], "src/inside.txt") == []


def test_successful_native_patch_requires_completed_event_for_allowed_target():
    spec.loader.exec_module(native)
    item = {"type": "item.completed", "item": {"type": "file_change", "status": "completed",
            "changes": [{"path": "src/inside.txt", "kind": "update"}]}}
    assert native.successful_patch_events([item], "src/inside.txt") == [item]
    item["item"]["status"] = "failed"
    assert native.successful_patch_events([item], "src/inside.txt") == []


def test_existing_stream_is_rejected_before_launch(tmp_path):
    spec.loader.exec_module(native)
    path = tmp_path / "probe.json"
    path.with_suffix(".stream.jsonl").write_text("retained")
    with pytest.raises(FileExistsError):
        native.output_paths(path)
    assert path.with_suffix(".stream.jsonl").read_text() == "retained"


def test_success_requires_matching_bound_apply_patch_denial():
    spec.loader.exec_module(native)
    state = {"run_id": "run", "bindings": {"codex:session": "run"}}
    denied = {"decision": "deny", "tool_name": "apply_patch", "session_id": "session", "reason": "Trailbun scope violation: protected/outside.txt"}
    assert native.matching_denial(denied, state)
    assert not native.matching_denial({**denied, "tool_name": "Edit"}, state)
    assert not native.matching_denial({**denied, "session_id": "other"}, state)
    assert not native.matching_denial({**denied, "reason": "Trailbun cannot validate this edit"}, state)


def test_fixture_acceptance_rejects_a_changed_sentinel(tmp_path):
    spec.loader.exec_module(native)
    (tmp_path / "protected").mkdir()
    sentinel = tmp_path / "protected/outside.txt"
    sentinel.write_text("TRAILBUN_SENTINEL_UNCHANGED\n")
    argv = native.sentinel_check(sys.executable)
    assert subprocess.run(argv, cwd=tmp_path, capture_output=True).returncode == 0
    sentinel.write_text("changed\n")
    assert subprocess.run(argv, cwd=tmp_path, capture_output=True).returncode != 0


def test_windows_probe_keeps_workspace_sandbox_with_explicit_elevated_backend():
    spec.loader.exec_module(native)
    argv = native.host_command(["node", "codex.js"], "gpt-6-astra", "fixture", windows=True)
    assert argv[:2] == ["node", "codex.js"]
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert 'windows.sandbox="elevated"' in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


def test_probe_trusts_only_exact_fixture_in_runtime_overrides():
    spec.loader.exec_module(native)
    root = "C:\\fixture.with ' quote é"
    argv = native.host_command(["codex"], "gpt-6-astra", root, windows=True)
    # Codex treats the key as a literal dotted path; only the value is TOML.
    override = next(value for value in argv if value.startswith("projects="))
    key, value = override.split("=", 1)
    assert key == "projects"
    assert tomllib.loads("value=" + value)["value"] == {root: {"trust_level": "trusted"}}


def test_unreadable_runtime_is_retained_as_incomplete_evidence(monkeypatch, tmp_path):
    spec.loader.exec_module(native)
    def denied(*args):
        raise PermissionError("fixture state unavailable")
    monkeypatch.setattr(native.store, "load", denied)
    monkeypatch.setattr(native.store, "directory", denied)
    monkeypatch.setattr(native.integration, "doctor", denied)
    state, receipt, doctor, errors = native.observe_runtime(tmp_path)
    assert state == {} and receipt is None and doctor["status"] == "incomplete"
    assert len(errors) == 3


def test_user_config_snapshot_records_digest_without_contents(monkeypatch, tmp_path):
    spec.loader.exec_module(native)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    before = native.user_config_snapshot()
    path = tmp_path / "config.toml"
    path.write_text("private_setting='first'\n")
    first = native.user_config_snapshot()
    path.write_text("private_setting='second'\n")
    assert before == {"exists": False, "sha256": None}
    assert first != native.user_config_snapshot()
    assert set(first) == {"exists", "sha256"}


def test_native_router_denial_matches_retained_scope_and_exact_input():
    spec.loader.exec_module(native)
    evidence = Path(__file__).parents[1] / "evidence"
    denied = json.loads((evidence / "native-codex-corrected-trust.json").read_text())["hook_denial"]
    stderr = (evidence / "native-codex-corrected-trust.stderr.txt").read_text()
    assert native.router_denials(stderr, denied, "protected/outside.txt")
    assert not native.router_denials(stderr, denied, "src/inside.txt")
    assert not native.router_denials(stderr, {**denied, "input_fingerprint": "different"}, "protected/outside.txt")
    assert not native.router_denials("The protected patch was rejected by the PreToolUse hook", denied, "protected/outside.txt")


def test_retained_native_probe_can_be_reassessed_without_a_host_call(monkeypatch, tmp_path):
    spec.loader.exec_module(native)
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline reassessment must not launch a host")
    monkeypatch.setattr(native, "_resolve_host", forbidden)
    path = Path(__file__).parents[1] / "evidence/native-codex-corrected-trust.json"
    output = tmp_path / "review.json"
    assert native.reassess(path, output) == 0
    result = json.loads(output.read_text())
    assert result["status"] == "ok" and result["original_status"] == "incomplete"
    assert all(result["checks"].values())
    with pytest.raises(FileExistsError):
        native.reassess(path, output)
