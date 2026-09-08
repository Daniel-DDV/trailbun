from checks.hook_exit_audit import candidate_files, inspect_text
import json
import subprocess
import sys
from pathlib import Path


def test_exit_one_is_flagged_as_potential_fail_open():
    findings = inspect_text("#!/bin/sh\nexit 1\n", "hook.sh")
    assert findings == [
        {
            "source": "hook.sh",
            "line": 2,
            "code": 1,
            "classification": "potential-fail-open",
            "text": "exit 1",
        }
    ]


def test_exit_two_is_a_blocking_candidate():
    findings = inspect_text("if unsafe; then exit 2; fi")
    assert findings[0]["classification"] == "blocking-candidate"


def test_comments_are_ignored():
    assert inspect_text("# exit 1\n") == []


def test_candidate_files_only_selects_shell_files(tmp_path):
    shell_file = tmp_path / "hook.sh"
    shell_file.write_text("exit 2\n")
    (tmp_path / "notes.md").write_text("exit 1\n")
    assert candidate_files([tmp_path]) == [shell_file]


def test_semicolon_terminates_exit_candidate():
    assert inspect_text('exit 1;')[0]['code'] == 1


def test_missing_input_is_incomplete(tmp_path):
    script = Path(__file__).parents[1] / 'checks' / 'hook_exit_audit.py'
    result = subprocess.run([sys.executable, str(script), str(tmp_path / 'missing'), '--json'], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)['status'] == 'incomplete'


def test_empty_directory_is_not_a_successful_audit(tmp_path):
    script = Path(__file__).parents[1] / 'checks' / 'hook_exit_audit.py'
    result = subprocess.run([sys.executable, str(script), str(tmp_path), '--json'], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)['files_scanned'] == 0
