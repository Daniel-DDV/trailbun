from pathlib import Path

import pytest

from trailbun import hooks


def test_patch_collects_both_move_ends_and_other_operations():
    patch = "*** Begin Patch\n*** Update File: src/a.py\n*** Move to: outside/b.py\n@@\n-old\n+new\n*** Add File: src/c.py\n+x\n*** Delete File: src/d.py\n*** End Patch"
    assert hooks.tool_paths("apply_patch", {"command": patch}) == [
        "src/a.py", "outside/b.py", "src/c.py", "src/d.py"
    ]


@pytest.mark.parametrize("payload", [{}, {"file_path": ""}, {"file_path": 4}])
def test_known_edit_rejects_missing_or_invalid_path(payload):
    with pytest.raises(ValueError):
        hooks.tool_paths("Edit", payload)


@pytest.mark.parametrize("patch", ["not a patch", "*** Begin Patch\n*** Move to: x\n*** End Patch", "*** Begin Patch\n*** Add File: \n*** End Patch"])
def test_invalid_patch_cannot_receive_scope_clearance(patch):
    with pytest.raises(ValueError):
        hooks.tool_paths("apply_patch", {"command": patch})


def test_shell_and_unknown_tools_have_no_invented_path_coverage():
    assert hooks.tool_paths("Bash", {"command": "rm outside.py"}) is None
    assert hooks.tool_paths("mcp__fs__write", {"path": "outside.py"}) is None


@pytest.fixture
def bound(monkeypatch):
    state = {"run_id": "r1", "bindings": {"claude:s1": "r1", "codex:s1": "r1"},
             "contract": {"allowed_paths": ["src/"]}, "needs_diagnosis": False}
    monkeypatch.setattr(hooks, "_load", lambda root: state)
    monkeypatch.setattr(hooks, "_root", lambda root: Path(root))
    monkeypatch.setattr(hooks, "_record", lambda *args: None)
    monkeypatch.setattr(hooks, "_allowed", lambda root, path, allowed: path.startswith("src/"))
    monkeypatch.setattr(hooks, "_assess", lambda root: {"verification_current": False, "outside_allowed_paths": [], "needs_diagnosis": False})
    return state


def event(name, **fields):
    return {"hook_event_name": name, "session_id": "s1", **fields}


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_bound_outside_edit_denied_in_native_json(bound, host):
    result = hooks.handle(Path("."), host, event("PreToolUse", tool_name="Edit", tool_input={"file_path": "outside.py"}))
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_unbound_sessions_are_not_guarded(bound):
    result = hooks.handle(Path("."), "claude", {**event("PreToolUse", tool_name="Edit", tool_input={}), "session_id": "other"})
    assert result == {}


def test_stop_reminds_once_and_does_not_claim_completion(bound):
    assert hooks.handle(Path("."), "codex", event("Stop"))["decision"] == "block"
    result = hooks.handle(Path("."), "codex", event("Stop", stop_hook_active=True))
    assert "decision" not in result
    assert "incomplete" in result["systemMessage"].lower()


def test_diagnosis_blocks_known_edit_but_not_unknown_shell(bound):
    bound["needs_diagnosis"] = True
    result = hooks.handle(Path("."), "claude", event("PreToolUse", tool_name="Write", tool_input={"file_path": "src/a.py"}))
    assert "diagnose" in result["hookSpecificOutput"]["permissionDecisionReason"]
    assert hooks.handle(Path("."), "claude", event("PreToolUse", tool_name="Bash", tool_input={"command": "python -m trailbun diagnose"})) == {}


def test_receipt_write_failure_does_not_discard_a_scope_denial(bound, monkeypatch):
    def broken_record(*args):
        raise OSError("read-only audit directory")
    monkeypatch.setattr(hooks, "_record", broken_record)
    result = hooks.handle(Path("."), "claude", event("PreToolUse", tool_name="Write", tool_input={"file_path": "outside.py"}))
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "receipt" in result["systemMessage"].lower()


def test_relative_targets_follow_event_working_directory(bound, monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr(hooks, "_allowed", lambda root, path, allowed: captured.append(path) or True)
    hooks.handle(tmp_path, "codex", event("PreToolUse", cwd=str(tmp_path / "subdir"), tool_name="apply_patch", tool_input={"command": "*** Begin Patch\n*** Add File: result.py\n+x\n*** End Patch"}))
    assert Path(captured[0]) == tmp_path / "subdir" / "result.py"


def test_oversized_context_reports_incomplete_restoration_instead_of_truncating():
    result = hooks._context("SessionStart", "important scope " * 1000)
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "not fully restored" in context
    assert len(context.encode("utf-8")) <= 6144


def test_payload_cwd_selects_the_actual_worktree(bound, monkeypatch, tmp_path):
    observed = []
    monkeypatch.setattr(hooks, "_load", lambda root: observed.append(Path(root)) or bound)
    hooks.handle(tmp_path / "original", "codex", event("Stop", cwd=str(tmp_path / "worktree"), stop_hook_active=True))
    assert observed == [tmp_path / "worktree"]


def test_hook_load_validates_contract_before_native_edit(repo, contract):
    from trailbun import engine, store
    engine.start(repo, contract)
    with store.locked(repo) as state:
        state["contract"].pop("allowed_paths")
    with pytest.raises(RuntimeError, match="state"):
        hooks._load(repo)
