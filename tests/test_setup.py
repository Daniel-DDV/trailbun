import json
import os
import subprocess
from pathlib import Path

import pytest

from trailbun import integration


@pytest.fixture
def project(repo, tmp_path, monkeypatch):
    """A real Git repository and a fake home directory, so no user settings file leaks into doctor."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(integration, "_version", lambda host: "fixture-1.0")
    return repo


@pytest.mark.parametrize("host,relative", [("claude", ".claude/settings.local.json"), ("codex", ".codex/hooks.json")])
def test_setup_is_idempotent_preserves_config_and_uninstalls_only_own_entries(project, host, relative):
    target = project / relative
    target.parent.mkdir(parents=True)
    prior = {"custom": True, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "user-check"}]}]}}
    target.write_text(json.dumps(prior), encoding="utf-8")
    assert integration.setup(project, host)["status"] == "ok"
    once = target.read_bytes()
    assert integration.setup(project, host)["status"] == "ok"
    assert target.read_bytes() == once
    current = json.loads(target.read_text(encoding="utf-8"))
    current["later-user-setting"] = 42
    target.write_text(json.dumps(current), encoding="utf-8")
    assert integration.uninstall(project, host)["status"] == "ok"
    assert json.loads(target.read_text(encoding="utf-8")) == {**prior, "later-user-setting": 42}


def test_setup_does_not_overwrite_existing_skill(project):
    target = project / ".claude/skills/trailbun-start/SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("User-owned skill", encoding="utf-8")
    with pytest.raises(ValueError, match="conflict"):
        integration.setup(project, "claude")
    assert target.read_text() == "User-owned skill"
    assert not (project / ".claude/settings.local.json").exists()


def test_uninstall_preserves_modified_owned_skill(project):
    integration.setup(project, "codex")
    target = project / ".agents/skills/trailbun-resume/SKILL.md"
    target.write_text("User revision", encoding="utf-8")
    result = integration.uninstall(project, "codex")
    assert result["status"] == "incomplete"
    assert target.read_text() == "User revision"


def test_uninstall_conflict_can_be_restored_and_retried(project):
    integration.setup(project, "codex")
    target = project / ".agents/skills/trailbun-resume/SKILL.md"
    original = target.read_bytes()
    config = project / ".codex/hooks.json"
    original_config = config.read_bytes()
    target.write_text("User revision", encoding="utf-8")
    assert integration.uninstall(project, "codex")["status"] == "incomplete"
    assert config.read_bytes() == original_config
    target.write_bytes(original)
    assert integration.uninstall(project, "codex")["status"] == "ok"


def test_doctor_reports_disabled_claude_hooks_after_previous_invocation(project):
    integration.setup(project, "claude")
    integration.record_invocation(project, "claude", {"hook_event_name": "SessionStart", "session_id": "s1"}, {})
    target = project / ".claude/settings.local.json"
    config = json.loads(target.read_text())
    config["disableAllHooks"] = True
    target.write_text(json.dumps(config))
    report = integration.doctor(project, "claude")
    assert report["status"] == "incomplete"
    assert report["disabled"] is True
    assert report["disabled_by"].startswith("local:")


def test_doctor_reads_user_and_project_disable_flags_with_local_precedence(project):
    integration.setup(project, "claude")
    user = Path(os.environ["USERPROFILE"]) / ".claude" / "settings.json"
    user.parent.mkdir(parents=True)
    user.write_text('{"disableAllHooks": true}', encoding="utf-8")
    assert integration.doctor(project, "claude")["disabled_by"].startswith("user:")
    (project / ".claude/settings.json").write_text('{"disableAllHooks": false}', encoding="utf-8")
    assert integration.doctor(project, "claude")["disabled"] is False
    (project / ".claude/settings.json").write_text('{"disableAllHooks": true}', encoding="utf-8")
    assert integration.doctor(project, "claude")["disabled_by"].startswith("project:")
    assert any("disableAllHooks" in item for item in integration.config_drift(project, "claude"))


def test_doctor_does_not_equate_configuration_or_invocation_with_enforcement(project):
    integration.setup(project, "claude")
    report = integration.doctor(project, "claude")
    assert report["configured"] is True
    assert report["invoked"] is False
    assert report["enforced"] is False
    integration.record_invocation(project, "claude", {"hook_event_name": "PreToolUse", "session_id": "s1"}, {"hookSpecificOutput": {"permissionDecision": "deny"}})
    report = integration.doctor(project, "claude")
    assert report["invoked"] is True
    assert report["enforced"] is False


def test_denied_invocation_survives_a_later_allowed_tool(project):
    integration.setup(project, "codex")
    payload = {"hook_event_name": "PreToolUse", "session_id": "s1",
               "tool_name": "apply_patch", "tool_use_id": "call-one", "tool_input": {"command": "fixture"}}
    integration.record_invocation(project, "codex", payload, {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "Trailbun scope violation: outside.txt"}})
    integration.record_invocation(project, "codex", {**payload, "tool_name": "Bash", "tool_use_id": "call-two"}, {})
    record = json.loads((integration._directory(project) / "denied-codex.json").read_text())
    assert record["tool_name"] == "apply_patch" and record["tool_use_id"] == "call-one"
    assert record["reason"] == "Trailbun scope violation: outside.txt"
    assert len(record["input_fingerprint"]) == 64
    assert "command" not in record


def test_invalid_configuration_is_not_rewritten(project):
    target = project / ".codex/hooks.json"
    target.parent.mkdir()
    target.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        integration.setup(project, "codex")
    assert target.read_text() == "{broken"


def test_preexisting_identical_unowned_hook_is_not_duplicated(project):
    target = project / ".codex/hooks.json"
    target.parent.mkdir()
    original = json.dumps({"hooks": integration._handlers("codex")})
    target.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="conflict"):
        integration.setup(project, "codex")
    assert target.read_text() == original


def test_corrupt_installation_manifest_reports_an_actionable_error(project):
    from trailbun import store
    manifest = store.bootstrap(project) / "install-codex.json"
    manifest.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        integration.doctor(project, "codex")


def test_codex_windows_command_has_no_unquoted_interpreter_interpolation(monkeypatch):
    monkeypatch.setattr(integration.sys, "executable", "C:\\Odd ' $path\\python.exe")
    handlers = integration._handlers("codex")
    hook = handlers["Stop"][0]["hooks"][0]
    assert "-EncodedCommand " in hook["commandWindows"]
    assert "Odd" not in hook["commandWindows"]


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_installed_command_reaches_real_cli_and_preserves_json_stdin(tmp_path, host):
    root = tmp_path / "project with $ and ' café"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    handler = integration._handlers(host)["SessionStart"][0]["hooks"][0]
    if host == "claude":
        command = [handler["command"], *handler["args"]]
    elif os.name == "nt":
        command = handler["commandWindows"].split()
    else:
        command = ["sh", "-c", handler["command"]]
    payload = {"hook_event_name": "SessionStart", "session_id": "native-fixture", "source": "startup", "cwd": str(root)}
    result = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False), text=True,
                            encoding="utf-8", capture_output=True, cwd=root, timeout=15)
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert "native-fixture" in response["hookSpecificOutput"]["additionalContext"]


def test_setup_bootstraps_owned_writable_runtime_before_installing(repo):
    from trailbun import store
    integration.setup(repo, "codex")
    runtime = store.directory(repo)
    assert runtime == repo / ".trailbun"
    assert json.loads((runtime / "owner.json").read_text())["owner"] == "trailbun"
    assert (runtime / "install-codex.json").exists()
    ignored = subprocess.run(["git", "check-ignore", ".trailbun/owner.json"], cwd=repo, capture_output=True)
    assert ignored.returncode == 0
