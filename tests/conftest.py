import subprocess

import pytest


def git_command(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Trailbun Test",
         "-c", "user.email=test@example.invalid", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git_command(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    git_command(tmp_path, "add", ".")
    git_command(tmp_path, "commit", "-qm", "baseline")
    return tmp_path


@pytest.fixture
def contract():
    return {"goal": "Change the value", "exclusions": ["Dependencies"],
            "allowed_paths": ["src"],
            "checks": [{"id": "acceptance", "argv": ["python", "-V"]}]}
