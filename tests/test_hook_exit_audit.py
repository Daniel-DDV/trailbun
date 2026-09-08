from checks.hook_exit_audit import candidate_files, inspect_text


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
