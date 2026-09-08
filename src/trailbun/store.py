"""Owned, ignored per-worktree state accessible to native workspace sandboxes."""

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from . import git

OWNER = {"schema_version": 1, "owner": "trailbun"}
IGNORE_RULE = b"/.trailbun/"


def _git_path(root, name):
    value = Path(os.fsdecode(git.run(root, "rev-parse", "--git-path", name).rstrip(b"\r\n")))
    return (root / value).resolve() if not value.is_absolute() else value.resolve()


def directory(root):
    root = git.repo_root(root)
    legacy = _git_path(root, "trailbun")
    if (legacy / "state.json").exists() or any(legacy.glob("install-*.json")):
        raise RuntimeError(f"Legacy Trailbun data exists at {legacy}; preserve or migrate it explicitly before initializing .trailbun")
    location = root / ".trailbun"
    if location.is_symlink() or location.resolve() != location:
        raise RuntimeError("Trailbun runtime ownership conflict: .trailbun cannot be a symlink or junction")
    if location.exists():
        try:
            marker = location / "owner.json"
            if not location.is_dir() or marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 1024:
                raise ValueError("missing owner marker")
            if json.loads(marker.read_text(encoding="utf-8")) != OWNER:
                raise ValueError("unknown owner marker")
        except (OSError, ValueError) as exc:
            raise RuntimeError("Trailbun runtime ownership conflict: preserve existing .trailbun contents") from exc
    if any(git.runtime_name(name) for name in git._names(git.run(root, "ls-files", "-z"))):
        raise RuntimeError("Trailbun runtime is tracked; remove it from the index before using task state")
    return location


def bootstrap(root):
    """Initialize ownership and an exact local ignore before entering a native sandbox."""
    root = git.repo_root(root)
    location = directory(root)
    exclude = _git_path(root, "info/exclude")
    common = Path(os.fsdecode(git.run(root, "rev-parse", "--git-common-dir").rstrip(b"\r\n")))
    common = (root / common).resolve() if not common.is_absolute() else common.resolve()
    if not exclude.is_relative_to(common):
        raise RuntimeError("Refusing to change an exclude file outside this repository's Git metadata")
    try:
        original = exclude.read_bytes() if exclude.exists() else b""
        if IGNORE_RULE not in (line.strip() for line in original.splitlines()):
            exclude.parent.mkdir(parents=True, exist_ok=True)
            block = (b"" if not original or original.endswith(b"\n") else b"\n")
            block += b"# Trailbun runtime begin\n" + IGNORE_RULE + b"\n# Trailbun runtime end\n"
            with exclude.open("ab") as output:
                output.write(block)
        if not git.is_ignored(root, ".trailbun/owner.json"):
            raise RuntimeError("A conflicting ignore rule exposes .trailbun; correct it outside the native sandbox")
        if not location.exists():
            location.mkdir()
            _write(location / "owner.json", OWNER)
    except OSError as exc:
        raise RuntimeError("Initialize Trailbun with setup or start outside the native sandbox before binding its session") from exc
    return location


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
    location = directory(root)
    if location.exists() and not git.is_ignored(git.repo_root(root), ".trailbun/owner.json"):
        raise RuntimeError("Trailbun runtime is not ignored; repair its local ignore outside the native sandbox")
    return _read(location / "state.json")


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
    location = bootstrap(root)
    path = location / "state.json"
    try:
        with FileLock(str(location / "state.lock"), timeout=5):
            state = _read(path) if path.exists() else {}
            yield state
            _write(path, state)
    except Timeout as exc:
        raise RuntimeError("Trailbun state is busy; retry after the active operation") from exc
