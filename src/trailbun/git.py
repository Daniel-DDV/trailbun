"""Git artifact inspection. Reports observed and net changes, not all past writes."""

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

from . import contracts


def run(root, *args):
    try:
        result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                                capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Git inspection failed: {exc}") from exc
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "Git inspection failed")
    return result.stdout


def repo_root(root):
    return Path(os.fsdecode(run(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve()


def head(root):
    return run(root, "rev-parse", "--verify", "HEAD").decode().strip()


def require_baseline(root, baseline):
    run(root, "merge-base", "--is-ancestor", baseline, "HEAD")


def clean(root):
    return not run(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")


def _names(data):
    return [os.fsdecode(item) for item in data.split(b"\0") if item]


def _diff_names(data):
    tokens = _names(data)
    paths = []
    index = 0
    while index < len(tokens):
        status_code = tokens[index]
        count = 2 if status_code.startswith(("R", "C")) else 1
        if index + count >= len(tokens):
            raise RuntimeError("Git returned an incomplete name-status record")
        paths.extend(tokens[index + 1:index + 1 + count])
        index += count + 1
    return paths


def changed_paths(root, baseline, watch_ignored=(), baseline_watched=None):
    root = repo_root(root)
    require_baseline(root, baseline)
    paths = set()
    # Separate layers retain staged changes even if the worktree reverted them.
    for args in ((baseline, "HEAD"), ("--cached", "HEAD"), ()):
        paths.update(_diff_names(run(root, "diff", "--name-status", "-z", "--find-renames", *args, "--")))
    paths.update(_names(run(root, "ls-files", "--others", "--exclude-standard", "-z")))
    watched = watched_files(root, watch_ignored)
    before = {name: digest for name, digest in (baseline_watched or {}).items()
              if any(_scope_matches(name, scope) for scope in watch_ignored)}
    paths.update(name for name in set(watched) | set(before) if watched.get(name) != before.get(name))
    return sorted(paths)


def _scope_matches(value, scope):
    value, scope = (os.path.normcase(item).replace("\\", "/") for item in (value, scope))
    return scope == "." or value == scope or value.startswith(scope.rstrip("/") + "/")


def path_allowed(root, value, allowed_paths):
    root = Path(root).resolve()
    try:
        supplied = Path(value)
        relative = supplied.relative_to(root).as_posix() if supplied.is_absolute() else value
        relative = contracts.path(relative)
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            return False
        matching = [contracts.path(scope) for scope in allowed_paths if _scope_matches(relative, scope)]
        if not matching:
            return False
        metadata = Path(os.fsdecode(run(root, "rev-parse", "--absolute-git-dir").rstrip(b"\r\n"))).resolve()
        if target == metadata or target.is_relative_to(metadata):
            return False
        for scope in matching:
            scope_target = (root / scope).resolve()
            if scope_target.is_relative_to(root) and (target == scope_target or target.is_relative_to(scope_target)):
                return True
    except (OSError, ValueError, RuntimeError):
        return False
    return False


def _file_digest(root, name):
    path = Path(root) / name
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing"
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise RuntimeError(f"Artifact contains a symlink outside the repository: {name}")
    digest = hashlib.sha256(str(stat.S_IMODE(info.st_mode)).encode() + b"\0")
    if stat.S_ISLNK(info.st_mode):
        digest.update(b"link\0" + os.fsencode(os.readlink(path)))
    elif stat.S_ISREG(info.st_mode):
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        raise RuntimeError(f"Unsupported artifact type: {name}")
    return digest.hexdigest()


def watched_files(root, watch_ignored):
    if not watch_ignored:
        return {}
    ignored = _names(run(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    return {name: _file_digest(root, name) for name in ignored
            if any(_scope_matches(name, scope) for scope in watch_ignored)}


def artifact(root, watch_ignored=()):
    root = repo_root(root)
    index = run(root, "ls-files", "--stage", "-z")
    if any(record.startswith(b"160000 ") for record in index.split(b"\0")):
        raise RuntimeError("Submodule contents are unsupported; artifact inspection is incomplete")
    paths = set(_names(run(root, "ls-files", "-z")))
    paths.update(_names(run(root, "ls-files", "--others", "--exclude-standard", "-z")))
    watched = watched_files(root, watch_ignored)
    paths.update(watched)
    files = {name: _file_digest(root, name) for name in sorted(paths)}
    result = {"head": head(root), "index": hashlib.sha256(index).hexdigest(), "files": files, "watched": watched}
    result["fingerprint"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return result
