import os

import pytest

from conftest import git_command
from trailbun import git


def test_fixed_baseline_finds_committed_changes_and_both_rename_paths(repo):
    baseline = git_command(repo, "rev-parse", "HEAD")
    (repo / "outside.py").write_text("outside\n")
    git_command(repo, "add", ".")
    git_command(repo, "commit", "-qm", "outside")
    git_command(repo, "mv", "outside.py", "src/moved.py")
    assert set(git.changed_paths(repo, baseline)) == {"outside.py", "src/moved.py"}


def test_index_change_is_detected_when_working_file_returns_to_baseline(repo):
    baseline = git_command(repo, "rev-parse", "HEAD")
    path = repo / "src/main.py"
    path.write_text("staged\n")
    git_command(repo, "add", ".")
    path.write_text("value = 1\n")
    assert git.changed_paths(repo, baseline) == ["src/main.py"]


def test_fingerprint_covers_unchanged_tracked_untracked_and_watched_ignored(repo):
    first = git.artifact(repo, ["ignored"])
    assert "src/main.py" in first["files"]
    (repo / "new.txt").write_text("first")
    second = git.artifact(repo, ["ignored"])
    assert first["fingerprint"] != second["fingerprint"]
    (repo / "ignored").mkdir()
    (repo / "ignored/settings").write_text("first")
    third = git.artifact(repo, ["ignored"])
    assert second["fingerprint"] != third["fingerprint"]
    assert "ignored/settings" in third["watched"]


def test_scopes_preserve_dotfiles_and_reject_traversal(repo):
    assert not git.path_allowed(repo, ".env", ["env"])
    assert not git.path_allowed(repo, "../src/secrets", ["src"])
    assert not git.path_allowed(repo, "src-other/main.py", ["src"])
    assert git.path_allowed(repo, "src/main.py", ["src"])
    assert git.path_allowed(repo, str(repo / "src/main.py"), ["src"])


def test_symlink_escape_is_rejected(repo, tmp_path_factory):
    target = tmp_path_factory.mktemp("outside")
    link = repo / "src/link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    assert not git.path_allowed(repo, "src/link/new.py", ["src"])


def test_symlink_alias_cannot_authorize_git_metadata(repo):
    link = repo / "meta-alias"
    try:
        link.symlink_to(repo / ".git", target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    assert not git.path_allowed(repo, "meta-alias/config", ["."])


@pytest.mark.skipif(os.name != "nt", reason="Windows case semantics")
def test_windows_scope_matching_preserves_filesystem_case_semantics(repo):
    assert git.path_allowed(repo, "SRC/main.py", ["src"])


@pytest.mark.skipif(os.name == "nt", reason="Windows cannot create newline filenames")
def test_git_names_preserve_newlines(repo):
    baseline = git_command(repo, "rev-parse", "HEAD")
    (repo / "src/new\nname.py").write_text("value\n")
    assert "src/new\nname.py" in git.changed_paths(repo, baseline)
