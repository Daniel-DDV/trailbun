"""Bounded, serialized state stored outside the artifact in each Git worktree."""

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from . import git


def directory(root):
    root = git.repo_root(root)
    value = Path(os.fsdecode(git.run(root, "rev-parse", "--git-path", "trailbun").rstrip(b"\r\n")))
    return (root / value).resolve() if not value.is_absolute() else value.resolve()


def _read(path):
    if not path.is_file():
        raise RuntimeError("No active Trailbun task in this worktree; run trailbun start")
    if path.stat().st_size > 1024 * 1024:
        raise RuntimeError("Trailbun state exceeds the 1 MiB limit")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot read Trailbun state: {exc}") from exc
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise RuntimeError("Unsupported or invalid Trailbun state schema")
    return state


def load(root):
    return _read(directory(root) / "state.json")


def _write(path, state):
    data = json.dumps(state, indent=2, ensure_ascii=True) + "\n"
    if len(data.encode()) > 1024 * 1024:
        raise RuntimeError("Trailbun state exceeds the 1 MiB limit; archive older receipts")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="state-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def archive(root, state):
    """Archive a completed or explicitly abandoned run while holding its state lock."""
    identifier = str(uuid.UUID(state["run_id"]))
    location = directory(root) / "archive"
    location.mkdir(parents=True, exist_ok=True)
    _write(location / (identifier + ".json"), state)


@contextmanager
def locked(root):
    location = directory(root)
    location.mkdir(parents=True, exist_ok=True)
    path = location / "state.json"
    try:
        with FileLock(str(location / "state.lock"), timeout=5):
            state = _read(path) if path.exists() else {}
            yield state
            _write(path, state)
    except Timeout as exc:
        raise RuntimeError("Trailbun state is busy; retry after the active operation") from exc
