"""Git artifact inspection. Reports observed and net changes, not all past writes."""

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

from . import contracts


def executable(name):
    """Resolve a program through PATH and PATHEXT only, never the working directory.

    Windows CreateProcess searches the parent's current directory before PATH when
    the name carries no directory. Returning an absolute path removes that lookup.
    """
    if os.path.dirname(name):
        return name
    extensions = [""]
    if os.name == "nt":
        extensions += [ext for ext in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep) if ext]
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        for extension in extensions:
            candidate = Path(entry) / (name + extension)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    raise OSError(f"Cannot find {name!r} on PATH")


def run(root, *args, allowed_codes=(0,), input_data=None):
    try:
        result = subprocess.run([executable("git"), "--no-optional-locks", "-C", str(root), *args],
                                capture_output=True, timeout=15, input=input_data)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Git inspection failed: {exc}") from exc
    if result.returncode not in allowed_codes:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail or f"Git inspection failed: git {args[0]} exited with {result.returncode}")
    return result.stdout


def repo_root(root):
    return Path(os.fsdecode(run(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve()


def head(root):
    return run(root, "rev-parse", "--verify", "HEAD").decode().strip()


def is_ancestor(root, baseline):
    """True when the recorded baseline is reachable from HEAD; False when Git says it is not."""
    result = subprocess.run([executable("git"), "--no-optional-locks", "-C", str(root), "merge-base",
                             "--is-ancestor", baseline, "HEAD"], capture_output=True, timeout=15)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.decode("utf-8", "replace").strip()
    if "not a valid commit" in detail.lower() or "bad revision" in detail.lower():
        return False
    raise RuntimeError(detail or "Git inspection failed: merge-base")


def baseline_error(baseline):
    return (f"Baseline {baseline[:12]} is not an ancestor of HEAD. The recorded commit was amended, rebased, "
            "reset away or left behind by a branch switch. Run trailbun amend --contract <file> --reason \"...\" "
            "--rebaseline to record HEAD as the new baseline, or trailbun start --contract <file> "
            "--abandon-reason \"...\" to archive this task.")


def require_baseline(root, baseline):
    if not is_ancestor(root, baseline):
        raise RuntimeError(baseline_error(baseline))


def dirty_paths(root):
    records = run(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
    names = []
    skip = False
    for record in records:
        if skip:  # The second record of a rename is the original name.
            skip = False
            continue
        if not record:
            continue
        names.append(os.fsdecode(record[3:]))
        skip = record[:1] in (b"R", b"C")
    return names


def clean(root):
    return not dirty_paths(root)


def is_ignored(root, name):
    fields = run(root, "check-ignore", "--no-index", "--verbose", "--non-matching", "-z",
                 "--stdin", allowed_codes=(0, 1), input_data=os.fsencode(name) + b"\0").split(b"\0")
    return len(fields) >= 4 and bool(fields[2]) and not fields[2].startswith(b"!")


def runtime_name(name):
    value = os.path.normcase(name).replace("\\", "/")
    return value == ".trailbun" or value.startswith(".trailbun/")


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
    from . import store
    store.directory(root)
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
    return sorted(name for name in paths if not runtime_name(name))


def _scope_matches(value, scope):
    value, scope = (os.path.normcase(item).replace("\\", "/") for item in (value, scope))
    return scope == "." or value == scope or value.startswith(scope.rstrip("/") + "/")


HOST_CONFIG_PATHS = (".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json",
                     ".codex/config.toml", ".claude/skills/trailbun-start", ".claude/skills/trailbun-resume",
                     ".claude/skills/trailbun-diagnose", ".agents/skills/trailbun-start",
                     ".agents/skills/trailbun-resume", ".agents/skills/trailbun-diagnose")


def git_dir(root):
    return Path(os.fsdecode(run(root, "rev-parse", "--absolute-git-dir").rstrip(b"\r\n"))).resolve()


def path_allowed(root, value, allowed_paths, metadata=None):
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
        # Host hook and skill files are denied under a broad scope unless an allowed path names them exactly.
        protected = [item for item in HOST_CONFIG_PATHS if _scope_matches(relative, item)]
        if protected and not any(os.path.normcase(scope) == os.path.normcase(item)
                                 for scope in matching for item in protected):
            return False
        if metadata is None:
            metadata = git_dir(root)
        runtime = (root / ".trailbun").resolve()
        if target == metadata or target.is_relative_to(metadata) or target == runtime or target.is_relative_to(runtime):
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
            if not runtime_name(name) and any(_scope_matches(name, scope) for scope in watch_ignored)}


def artifact(root, watch_ignored=()):
    root = repo_root(root)
    from . import store
    store.directory(root)
    index = run(root, "ls-files", "--stage", "-z")
    if any(record.startswith(b"160000 ") for record in index.split(b"\0")):
        raise RuntimeError("Submodule contents are unsupported; artifact inspection is incomplete")
    paths = set(_names(run(root, "ls-files", "-z")))
    paths.update(_names(run(root, "ls-files", "--others", "--exclude-standard", "-z")))
    watched = watched_files(root, watch_ignored)
    paths.update(watched)
    files = {name: _file_digest(root, name) for name in sorted(paths) if not runtime_name(name)}
    result = {"head": head(root), "index": hashlib.sha256(index).hexdigest(), "files": files, "watched": watched}
    result["fingerprint"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    # Contents only: staging or committing the same bytes must not count as a new corrective attempt.
    content = {"files": files, "watched": watched}
    result["content_fingerprint"] = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return result
