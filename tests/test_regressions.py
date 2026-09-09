"""Regressions for the 0.2.1 review findings. Each test names the finding it guards."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from trailbun import cli, engine, git, hooks, integration, store, verify
from tests.conftest import git_command


@pytest.fixture
def outside(tmp_path_factory):
    """A directory that is not inside the repository fixture (which is tmp_path itself)."""
    return tmp_path_factory.mktemp("outside")


def _fake_home(outside, monkeypatch):
    home = outside / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


# C1: setup then start must work without any manual exclude editing.
@pytest.mark.parametrize("host", ["claude", "codex"])
def test_setup_then_start_leaves_git_status_clean(repo, contract, outside, monkeypatch, host):
    _fake_home(outside, monkeypatch)
    result = integration.setup(repo, host)
    assert result["target"] == {"claude": ".claude/settings.local.json", "codex": ".codex/hooks.json"}[host]
    assert git_command(repo, "status", "--short") == ""
    assert "--session" in result["next"]
    report = engine.start(repo, contract)
    assert report["status"] == "ok"
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    for relative in result["generated_paths"]:
        assert "/" + relative in exclude
    assert integration.uninstall(repo, host)["removed"] is True
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert "trailbun-start" not in exclude and "/.trailbun/" in exclude
    assert git_command(repo, "status", "--short") == ""


def test_shared_claude_setup_writes_committed_settings_without_machine_paths(repo, outside, monkeypatch):
    _fake_home(outside, monkeypatch)
    result = integration.setup(repo, "claude", shared=True)
    assert result["target"] == ".claude/settings.json"
    config = json.loads((repo / ".claude/settings.json").read_text(encoding="utf-8"))
    command = config["hooks"]["Stop"][0]["hooks"][0]
    assert command["command"] == "trailbun" and sys.executable not in json.dumps(config)
    assert result["warnings"]


# A4: Claude setup adds Edit deny rules for the runtime and settings files and removes them on uninstall.
def test_claude_setup_records_and_removes_permission_deny_rules(repo, outside, monkeypatch):
    _fake_home(outside, monkeypatch)
    target = repo / ".claude/settings.local.json"
    target.parent.mkdir()
    target.write_text('{"permissions": {"deny": ["Edit(/secrets/**)"]}}', encoding="utf-8")
    integration.setup(repo, "claude")
    rules = json.loads(target.read_text(encoding="utf-8"))["permissions"]["deny"]
    assert "Edit(/.trailbun/**)" in rules and "Edit(/secrets/**)" in rules
    assert not any(rule.startswith("Write(") for rule in rules)
    integration.uninstall(repo, "claude")
    assert json.loads(target.read_text(encoding="utf-8")) == {"permissions": {"deny": ["Edit(/secrets/**)"]}}


# B1: generated hook groups carry matchers so read-only tool calls do not spawn the handler.
def test_generated_hook_groups_carry_documented_matchers():
    claude = integration._handlers("claude")
    assert claude["PreToolUse"][0]["matcher"] == "Edit|Write|NotebookEdit"
    assert claude["PostToolUse"][0]["matcher"] == "Edit|Write|NotebookEdit|Bash"
    assert "matcher" not in claude["SessionStart"][0] and "matcher" not in claude["Stop"][0]
    codex = integration._handlers("codex")
    assert codex["PreToolUse"][0]["matcher"] == "apply_patch"
    assert "matcher" not in codex["PostToolUse"][0]
    assert all(group[0]["hooks"][0]["timeout"] == 60 for group in claude.values())


# A5: a rewritten baseline is an explicit finding with a recovery path, and rebaseline records it.
def test_rewritten_baseline_is_an_explicit_error_and_rebaseline_recovers(repo, contract):
    engine.start(repo, contract)
    git_command(repo, "commit", "-q", "--amend", "-m", "rewritten baseline commit")
    with pytest.raises(RuntimeError, match="not an ancestor of HEAD.*--rebaseline"):
        engine.check(repo)
    report = engine.amend(repo, contract, "history was rewritten", rebaseline=True)
    assert report["status"] == "ok" and report["rebaseline_count"] == 1
    history = store.load(repo)["contract_history"][-1]
    assert history["rebaseline"] is True and history["new_baseline"] == git.head(repo)
    assert history["previous_baseline"] != history["new_baseline"]


def test_stop_hook_blocks_once_with_the_inspection_error(monkeypatch):
    def broken(root):
        raise RuntimeError("Baseline abc is not an ancestor of HEAD")
    monkeypatch.setattr(hooks, "_assess", broken)
    monkeypatch.setattr(hooks, "_load", lambda root: {"run_id": "r1", "bindings": {"codex:s1": "r1"}, "contract": {"allowed_paths": ["."]}})
    monkeypatch.setattr(hooks, "_root", lambda root: Path(root))
    monkeypatch.setattr(hooks, "_record", lambda *args: None)
    first = hooks.handle(Path("."), "codex", {"hook_event_name": "Stop", "session_id": "s1"})
    assert first["decision"] == "block" and "not an ancestor" in first["reason"]
    second = hooks.handle(Path("."), "codex", {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True})
    assert "decision" not in second and "not an ancestor" in second["systemMessage"]


# A6: staging or committing the same failing content is the same attempt.
def test_staging_failed_content_does_not_count_as_a_second_attempt(repo):
    contract = {"goal": "Fail", "allowed_paths": ["src"],
                "checks": [{"id": "always", "argv": [sys.executable, "-c", "raise SystemExit(1)"]}]}
    engine.start(repo, contract)
    (repo / "src/main.py").write_text("value = 3\n", encoding="utf-8")
    assert verify.verify(repo)["status"] == "violation"
    git_command(repo, "add", ".")
    assert verify.verify(repo)["status"] == "violation"
    git_command(repo, "commit", "-qm", "same content committed")
    assert verify.verify(repo)["status"] == "violation"
    state = store.load(repo)
    assert state["failures"]["always"]["count"] == 1 and state["needs_diagnosis"] is False


# A7: an unchanged contract cannot be amended, and an unchanged check keeps its failure budget.
def test_amend_rejects_identical_contract_and_keeps_unchanged_check_counters(repo, contract):
    engine.start(repo, contract)
    with store.locked(repo) as state:
        state["failures"] = {"acceptance": {"count": 2, "fingerprints": ["a", "b"]}}
        state["needs_diagnosis"] = True
    with pytest.raises(ValueError, match="identical"):
        engine.amend(repo, contract, "no change")
    widened = {**contract, "allowed_paths": ["src", "tests"]}
    report = engine.amend(repo, widened, "tests need an update")
    assert report["needs_diagnosis"] is True and report["amend_count"] == 1
    assert store.load(repo)["failures"]["acceptance"]["count"] == 2
    changed = {**widened, "checks": [{"id": "acceptance", "argv": ["python", "-c", "pass"]}]}
    report = engine.amend(repo, changed, "check definition changed")
    assert report["needs_diagnosis"] is False and store.load(repo)["failures"] == {}
    assert store.load(repo)["contract_history"][-1]["actor"]["argv"]


# A1: the Stop reason and resume context disclose amendments.
def test_stop_reason_and_context_disclose_amendments(repo, contract, monkeypatch):
    engine.start(repo, contract)
    engine.amend(repo, {**contract, "allowed_paths": ["src", "tests"]}, "widen scope")
    context = engine.resume(repo)["context"]
    assert "amended 1 times since start, last reason: widen scope" in context
    monkeypatch.setattr(hooks, "_config_drift", lambda root, host: [])
    reason = hooks._stop_reason(repo, "codex", engine.check(repo))
    assert "amended 1 times" in reason and "recorded, not enforced" in reason


# C4: commands that need a task must not create the runtime or edit the exclude file first.
@pytest.mark.parametrize("command", ["checkpoint", "diagnose", "amend"])
def test_no_task_commands_leave_no_side_effects(repo, contract, outside, command):
    tmp_path = outside
    exclude = repo / ".git" / "info" / "exclude"
    before = exclude.read_bytes() if exclude.exists() else None
    contract_file = tmp_path / "task.json"
    contract_file.write_text(json.dumps(contract), encoding="utf-8")
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("x", encoding="utf-8")
    argv = {"checkpoint": ["checkpoint", "--summary", "s", "--next-action", "n"],
            "diagnose": ["diagnose", "--reproduction", "r", "--cause", "c", "--evidence", str(evidence), "--next-action", "n"],
            "amend": ["amend", "--contract", str(contract_file), "--reason", "r"]}[command]
    code = cli.main([*argv, "--project", str(repo), "--json"])
    assert code == 2
    assert not (repo / ".trailbun").exists()
    assert (exclude.read_bytes() if exclude.exists() else None) == before


# C5: contract read errors and corrupt state are messages, not tracebacks.
def test_contract_and_state_errors_are_messages(repo, contract, outside, capsys):
    tmp_path = outside
    assert cli.main(["start", "--contract", str(tmp_path / "missing.json"), "--project", str(repo), "--json"]) == 2
    assert "Cannot read contract" in json.loads(capsys.readouterr().out)["error"]
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert cli.main(["start", "--contract", broken.as_posix(), "--project", str(repo), "--json"]) == 2
    assert "invalid JSON" in json.loads(capsys.readouterr().out)["error"]
    engine.start(repo, contract)
    (repo / ".trailbun" / "state.json").write_text('{"schema_version": 1, "revision": 1}', encoding="utf-8")
    good = tmp_path / "task.json"
    good.write_text(json.dumps(contract), encoding="utf-8")
    code = cli.main(["start", "--contract", str(good), "--abandon-reason", "corrupt", "--project", str(repo), "--json"])
    assert code == 0
    assert any(path.name.startswith("unreadable-") for path in (repo / ".trailbun" / "archive").iterdir())


def test_dirty_worktree_error_lists_paths(repo, contract):
    (repo / "stray.txt").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match=r"Uncommitted or untracked paths: stray.txt"):
        engine.start(repo, contract)


def test_checkpoint_deduplicates_hypotheses(repo, contract):
    engine.start(repo, contract)
    engine.checkpoint(repo, {"failed_hypotheses": ["one", "one", "two"]})
    engine.checkpoint(repo, {"failed_hypotheses": ["two", "three"]})
    assert store.load(repo)["progress"]["failed_hypotheses"] == ["one", "two", "three"]


def test_export_is_validated_before_state_changes(repo, contract, outside):
    tmp_path = outside
    engine.start(repo, contract)
    existing = tmp_path / "handoff.txt"
    existing.write_text("keep", encoding="utf-8")
    code = cli.main(["checkpoint", "--summary", "later", "--next-action", "n", "--export", str(existing),
                     "--project", str(repo), "--json"])
    assert code == 2
    assert store.load(repo)["progress"]["summary"] == "Not started"


# C2: every subcommand documents itself.
def test_every_subcommand_has_help(capsys):
    for name in cli.DESCRIPTIONS:
        with pytest.raises(SystemExit):
            cli.main([name, "--help"])
        output = capsys.readouterr().out
        assert cli.DESCRIPTIONS[name].split(":")[0] in output
        if name in ("start", "amend"):
            assert "allowed_paths" in output and ".trailbun/task.json" in output


# C6: the default output is readable text.
def test_check_and_demo_print_text_without_json(repo, contract, capsys):
    engine.start(repo, contract)
    assert cli.main(["check", "--project", str(repo)]) == 0
    text = capsys.readouterr().out
    assert text.startswith("Trailbun | OK") and "outside scope: none" in text and "{" not in text.splitlines()[0]
    assert cli.main(["demo"]) == 0
    text = capsys.readouterr().out
    assert "CATCH" not in text and "new-auth-framework.txt" in text and "no live model" in text


# C9: resume output survives a non-UTF-8 pipe.
def test_resume_survives_non_utf8_stdout(repo, contract):
    engine.start(repo, {**contract, "goal": "Route → login"})
    env = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run([sys.executable, "-m", "trailbun", "resume", "--project", str(repo)],
                            capture_output=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    assert b"Route" in result.stdout


# A10 and C8: executables resolve through PATH, never the working directory; .cmd shims run on Windows.
def test_executable_resolution_ignores_working_directory(tmp_path, monkeypatch):
    stray = tmp_path / ("git.exe" if os.name == "nt" else "git")
    stray.write_bytes(b"not a program")
    stray.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    resolved = Path(git.executable("git"))
    assert resolved.is_absolute() and resolved != stray.resolve()
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(OSError):
        git.executable("definitely-missing-program")


@pytest.mark.skipif(os.name != "nt", reason="Windows batch shims")
def test_cmd_shim_runs_as_a_check_on_windows(repo, outside, monkeypatch):
    tmp_path = outside
    shim = tmp_path / "bin" / "fake-npm.cmd"
    shim.parent.mkdir()
    shim.write_text("@echo off\r\necho shim ran\r\nexit /b 0\r\n", encoding="ascii")
    monkeypatch.setenv("PATH", str(shim.parent) + os.pathsep + os.environ["PATH"])
    contract = {"goal": "Shim", "allowed_paths": ["src"], "checks": [{"id": "shim", "argv": ["fake-npm", "test"]}]}
    engine.start(repo, contract)
    receipt = verify.verify(repo)
    assert receipt["status"] == "ok", receipt["checks"][0]
    assert receipt["checks"][0]["resolved_executable"].lower().endswith("fake-npm.cmd")
    assert "shim ran" in receipt["checks"][0]["output"]


# D1: secrets and absolute paths are redacted before truncation.
def test_redaction_covers_common_secret_shapes_and_paths(tmp_path):
    samples = ["postgres://user:hunter22@db.example/app", "AKIAABCDEFGHIJKLMNOP",
               "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
               "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n-----END RSA PRIVATE KEY-----",
               "Authorization: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==", "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789",
               "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "xoxb-1234567890-abcdefghij",
               str(Path.home() / "secret-project" / "file.txt")]
    text = verify._redact("\n".join(samples), tmp_path)
    assert "hunter22" not in text and "AKIAABCDEFGHIJKLMNOP" not in text and "dozjgNryP4J3" not in text
    assert "MIIB" not in text and "QWxhZGRpbjpvcGVuIHNlc2FtZQ" not in text and "abcdefghijklmnopqrstuvwxyz" not in text
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in text and "xoxb-1234567890" not in text
    assert str(Path.home()) not in text and "<HOME>" in text


def test_output_is_redacted_before_truncation(repo):
    script = "import sys; sys.stdout.write('a' * 16380 + ' AKIAABCDEFGHIJKLMNOP ' + 'b' * 100)"
    contract = {"goal": "Leak", "allowed_paths": ["src"], "checks": [{"id": "leak", "argv": [sys.executable, "-c", script]}]}
    engine.start(repo, contract)
    receipt = verify.verify(repo)
    output = receipt["checks"][0]["output"]
    assert "AKIA" not in output and len(output) <= 16384 and receipt["checks"][0]["output_truncated"]
    assert "<HOME>" in receipt["checks"][0]["argv"][0] or sys.executable == receipt["checks"][0]["argv"][0]
    assert receipt["sha256"] == store.load(repo)["receipts"][-1]["sha256"]


# C10: files written during checks are listed instead of silently making the receipt incomplete.
def test_verify_lists_files_changed_during_checks(repo):
    script = "from pathlib import Path; Path('src/generated.txt').write_text('x')"
    contract = {"goal": "Cache", "allowed_paths": ["src"], "checks": [{"id": "writer", "argv": [sys.executable, "-c", script]}]}
    engine.start(repo, contract)
    receipt = verify.verify(repo)
    assert receipt["status"] == "incomplete" and receipt["changed_during_checks"] == ["src/generated.txt"]


# A3: host configuration is protected under a broad scope and only allowed when named exactly.
def test_host_configuration_is_denied_under_broad_scope_unless_named(repo):
    for relative in (".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json",
                     ".codex/config.toml", ".claude/skills/trailbun-start/SKILL.md"):
        assert not git.path_allowed(repo, relative, ["."]), relative
        assert not git.path_allowed(repo, relative, [relative.split("/")[0]]), relative
    assert git.path_allowed(repo, ".claude/settings.json", [".claude/settings.json"])
    assert git.path_allowed(repo, ".claude/other.json", ["."])


def test_stop_reason_reports_removed_hook_configuration(repo, contract, outside, monkeypatch):
    _fake_home(outside, monkeypatch)
    integration.setup(repo, "codex")
    engine.start(repo, contract)
    (repo / ".codex/hooks.json").write_text("{}", encoding="utf-8")
    assert integration.config_drift(repo, "codex") == [f"{event} hook removed or modified" for event in integration.EVENTS]
    reason = hooks._stop_reason(repo, "codex", engine.check(repo))
    assert "differs from the installation manifest" in reason


# A11: NotebookEdit is inspected through its documented field.
def test_notebook_edit_uses_notebook_path():
    assert hooks.tool_paths("NotebookEdit", {"notebook_path": "notes/a.ipynb"}) == ["notes/a.ipynb"]
    with pytest.raises(ValueError):
        hooks.tool_paths("NotebookEdit", {"file_path": "notes/a.ipynb"})
    assert hooks.tool_paths("MultiEdit", {"file_path": "x"}) is None


# A9: doctor --probe starts the installed handler and reports whether it answered.
def test_doctor_probe_reports_handler_start(repo, outside, monkeypatch):
    _fake_home(outside, monkeypatch)
    integration.setup(repo, "codex")
    report = integration.doctor(repo, "codex", run_probe=True)
    assert report["probe"]["handler_started"] is True, report["probe"]
    assert report["probe"]["handler_output_valid"] is True


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper")
def test_codex_windows_wrapper_reports_a_missing_interpreter(tmp_path, monkeypatch):
    monkeypatch.setattr(integration.sys, "executable", str(tmp_path / "missing" / "python.exe"))
    command = integration._handlers("codex")["SessionStart"][0]["hooks"][0]["commandWindows"].split()
    result = subprocess.run(command, input='{"hook_event_name": "SessionStart", "session_id": "s"}',
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert json.loads(result.stdout.strip().splitlines()[-1])["systemMessage"].startswith("Trailbun hook interpreter missing")


# A8: diagnosis after a repeated failure needs evidence that records a failing check or lives in the worktree.
def test_diagnosis_for_repeated_failure_rejects_passing_receipts_and_outside_files(repo, contract, outside):
    tmp_path = outside
    engine.start(repo, contract)
    receipt = store.directory(repo) / "ok.json"
    receipt.write_text('{"status":"ok"}', encoding="utf-8")
    with store.locked(repo) as state:
        state["receipts"].append({"id": "green", "path": str(receipt), "status": "ok"})
        state["failures"] = {"acceptance": {"count": 2, "fingerprints": ["a", "b"]}}
        state["needs_diagnosis"] = True
    data = {"reproduction": "r", "cause": "c", "evidence": "receipt:green", "next_action": "n"}
    with pytest.raises(ValueError, match="failing check"):
        engine.diagnose(repo, data)
    outside = tmp_path / "notes.txt"
    outside.write_text("observed", encoding="utf-8")
    with pytest.raises(ValueError, match="inside the worktree"):
        engine.diagnose(repo, {**data, "evidence": str(outside)})
    inside = repo / "src" / "repro.log"
    inside.write_text("observed", encoding="utf-8")
    report = engine.diagnose(repo, {**data, "evidence": str(inside)})
    assert report["needs_diagnosis"] is False
    assert store.load(repo)["diagnoses"][-1]["evidence_record"]["kind"] == "file"


def test_store_directory_lists_only_the_runtime_prefix(repo, monkeypatch):
    calls = []
    original = git.run
    def spy(root, *args, **kwargs):
        calls.append(args)
        return original(root, *args, **kwargs)
    monkeypatch.setattr(git, "run", spy)
    store.directory(repo)
    assert ("ls-files", "-z", "--", ".trailbun") in calls
    assert ("ls-files", "-z") not in calls
