"""Owned, ignored per-worktree state accessible to native workspace sandboxes."""

import csv
import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from . import git

OWNER = {"schema_version": 1, "owner": "trailbun"}
IGNORE_RULE = b"/.trailbun/"
BLOCK_BEGIN = b"# Trailbun runtime begin"
BLOCK_END = b"# Trailbun runtime end"


def _grant_bootstrap_user(location):
    """Keep the initializing user's access when a sandbox owns later state files."""
    if os.name != "nt":
        return
    # OWNER RIGHTS inherited from a Windows temporary directory follows each
    # new file's owner. Add only the bootstrap user's SID to this new runtime.
    # https://learn.microsoft.com/windows-server/administration/windows-commands/icacls
    system = Path(os.environ["SystemRoot"]) / "System32"
    try:
        result = subprocess.run([str(system / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
                                check=True, capture_output=True, text=True, errors="replace", timeout=10)
        rows = list(csv.reader(result.stdout.splitlines()))
        if len(rows) != 1 or len(rows[0]) != 2 or not re.fullmatch(r"S-1-(?:\d+-)+\d+", rows[0][1]):
            raise ValueError("Cannot identify the bootstrap user's SID")
        subprocess.run([str(system / "icacls.exe"), str(location), "/grant", f"*{rows[0][1]}:(OI)(CI)M", "/q"],
                       check=True, capture_output=True, timeout=10)
    except (subprocess.SubprocessError, ValueError, csv.Error) as exc:
        raise OSError("Cannot preserve the bootstrap user's access to Trailbun runtime") from exc


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
    # Only the runtime prefix is listed; a full ls-files on every call scales with the repository.
    if any(git.runtime_name(name) for name in git._names(git.run(root, "ls-files", "-z", "--", ".trailbun"))):
        raise RuntimeError("Trailbun runtime is tracked; remove it from the index before using task state")
    return location


def has_task(root):
    """True when a state file exists, without creating the runtime or touching Git's exclude file."""
    return (git.repo_root(root) / ".trailbun" / "state.json").is_file()


def _exclude_file(root):
    exclude = _git_path(root, "info/exclude")
    common = Path(os.fsdecode(git.run(root, "rev-parse", "--git-common-dir").rstrip(b"\r\n")))
    common = (root / common).resolve() if not common.is_absolute() else common.resolve()
    if not exclude.is_relative_to(common):
        raise RuntimeError("Refusing to change an exclude file outside this repository's Git metadata")
    return exclude


def _block_lines(original):
    """Return (before, block_lines, after) for the owned block, creating an empty block when absent."""
    lines = original.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    stripped = [line.strip() for line in lines]
    if BLOCK_BEGIN in stripped and BLOCK_END in stripped[stripped.index(BLOCK_BEGIN):]:
        start = stripped.index(BLOCK_BEGIN)
        end = stripped.index(BLOCK_END, start)
        return lines[:start], lines[start + 1:end], lines[end + 1:]
    return lines, [], []


def _write_block(exclude, before, block, after):
    exclude.parent.mkdir(parents=True, exist_ok=True)
    content = before + [BLOCK_BEGIN] + block + [BLOCK_END] + after
    with exclude.open("wb") as output:
        output.write(b"\n".join(content) + b"\n")


def exclude_paths(root, names, *, remove=False):
    """Add or remove exact repository-relative entries inside the Trailbun block of .git/info/exclude.

    Entries are anchored with a leading slash so they match only the generated file.
    """
    root = git.repo_root(root)
    exclude = _exclude_file(root)
    original = exclude.read_bytes() if exclude.exists() else b""
    before, block, after = _block_lines(original)
    entries = [b"/" + os.fsencode(str(name).replace("\\", "/").lstrip("/")) for name in names]
    current = [line.strip() for line in block]
    if remove:
        block = [line for line in block if line.strip() not in entries]
    else:
        block = block + [entry for entry in entries if entry not in current]
    if IGNORE_RULE not in [line.strip() for line in block] and not remove:
        block = [IGNORE_RULE] + block
    if [line.strip() for line in block] != current or BLOCK_BEGIN not in original:
        _write_block(exclude, before, block, after)
    return [entry.decode("utf-8", "replace") for entry in block]


def bootstrap(root):
    """Initialize ownership and an exact local ignore before entering a native sandbox."""
    root = git.repo_root(root)
    location = directory(root)
    try:
        exclude_paths(root, [])
        if not git.is_ignored(root, ".trailbun/owner.json"):
            raise RuntimeError("A conflicting ignore rule exposes .trailbun; correct it outside the native sandbox")
        if not location.exists():
            location.mkdir()
            try:
                _grant_bootstrap_user(location)
            except OSError:
                location.rmdir()  # Newly created and still empty; never remove user content.
                raise
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
        raise RuntimeError("Trailbun state exceeds the 1 MiB limit; start a reviewed follow-up task")
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
    try:
        identifier = str(uuid.UUID(state["run_id"]))
    except (KeyError, TypeError, ValueError):
        identifier = "unreadable-" + uuid.uuid4().hex
    location = directory(root) / "archive"
    location.mkdir(parents=True, exist_ok=True)
    _write(location / (identifier + ".json"), state)


@contextmanager
def locked(root, *, existing=False):
    """Hold the state lock. With existing=True, refuse before bootstrapping when no task exists."""
    if existing and not has_task(root):
        raise RuntimeError("No active Trailbun task in this worktree; run trailbun start")
    location = bootstrap(root)
    path = location / "state.json"
    try:
        with FileLock(str(location / "state.lock"), timeout=5):
            state = _read(path) if path.exists() else {}
            yield state
            _write(path, state)
    except Timeout as exc:
        raise RuntimeError("Trailbun state is busy; retry after the active operation") from exc
