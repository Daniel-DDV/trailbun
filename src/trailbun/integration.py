"""Reversible project-local hook installation and honest coverage reporting."""

import base64
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

HOSTS = {"claude": ".claude/settings.json", "codex": ".codex/hooks.json"}
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")


def _root(root):
    from . import git
    return git.repo_root(root)


def _directory(root):
    from . import store
    return store.directory(root)


def _digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be a JSON object: {path}")
    return value


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data if isinstance(data, bytes) else (json.dumps(data, indent=2) + "\n").encode()
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(raw)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _inside(root, relative):
    target = root / relative
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Installation path escapes project: {relative}")
    return target


def _handlers(host):
    if host not in HOSTS:
        raise ValueError("Host must be claude or codex")
    args = ["-X", "utf8", "-m", "trailbun", "hook", "--host", host]
    if host == "claude":
        handler = {"type": "command", "command": sys.executable, "args": args, "timeout": 10}
    else:
        executable = sys.executable.replace("'", "''")
        script = "$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        script += f"[Console]::In.ReadToEnd() | & '{executable}' -X utf8 -m trailbun hook --host codex; exit $LASTEXITCODE"
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        handler = {"type": "command", "command": shlex.join([sys.executable, *args]),
                   "commandWindows": f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded}", "timeout": 10}
    events = (*EVENTS, "PostToolUseFailure") if host == "claude" else EVENTS
    return {event: [{"hooks": [dict(handler)]}] for event in events}


def _skills(host):
    base = ".claude/skills" if host == "claude" else ".agents/skills"
    return {f"{base}/trailbun-{name}/SKILL.md": files("trailbun").joinpath("skills", name, "SKILL.md").read_bytes()
            for name in ("start", "resume", "diagnose")}


def _paths(root, host):
    if host not in HOSTS:
        raise ValueError("Host must be claude or codex")
    return _inside(root, HOSTS[host]), _directory(root) / f"install-{host}.json"


def _config(target):
    value = _read(target) if target.exists() else {}
    if not isinstance(value.get("hooks", {}), dict) or any(not isinstance(v, list) for v in value.get("hooks", {}).values()):
        raise ValueError(f"Invalid hooks configuration: {target}")
    return value


def _manifest(path, host):
    value = _read(path)
    hooks = value.get("hooks")
    valid = (value.get("schema_version") == 1 and value.get("host") == host
             and isinstance(value.get("config_existed"), bool)
             and isinstance(value.get("skills"), dict) and isinstance(hooks, dict)
             and set(EVENTS).issubset(hooks))
    if not valid or any(not isinstance(entries, list) or not entries or not all(isinstance(entry, dict) for entry in entries) for entries in hooks.values()):
        raise ValueError(f"Invalid Trailbun installation manifest: {path}")
    return value


def setup(project: Path, host: str) -> dict:
    root = _root(project)
    target, manifest_path = _paths(root, host)
    config = _config(target)
    manifest = _manifest(manifest_path, host) if manifest_path.exists() else None
    templates = _skills(host)
    old_hooks = manifest["hooks"] if manifest else {}
    for event, entries in old_hooks.items():
        if any(entry not in config.get("hooks", {}).get(event, []) for entry in entries):
            raise ValueError(f"Installation conflict: modified {event} hook")
    for relative in templates:
        path = _inside(root, relative)
        if path.exists() and (not manifest or _digest(path.read_bytes()) != manifest["skills"].get(relative)):
            raise ValueError(f"Installation conflict: {relative}")
    owned = _handlers(host)
    if not manifest and any(entry in config.get("hooks", {}).get(event, []) for event, entries in owned.items() for entry in entries):
        raise ValueError("Installation conflict: identical hook exists without a Trailbun ownership manifest")
    hooks = config.setdefault("hooks", {})
    for event, entries in old_hooks.items():
        hooks[event] = [entry for entry in hooks[event] if entry not in entries]
    for event, entries in owned.items():
        hooks.setdefault(event, []).extend(entries)
    record = {"schema_version": 1, "host": host, "hooks": owned,
              "config_existed": manifest["config_existed"] if manifest else target.exists(),
              "skills": {p: _digest(content) for p, content in templates.items()}}
    # Validate every destination before the first mutation.
    for relative, content in templates.items():
        _write(_inside(root, relative), content)
    _write(target, config)
    _write(manifest_path, record)
    return {"schema_version": 1, "status": "ok", "host": host, "configured": True,
            "next": "Restart the host and review project/hook trust. Then run trailbun doctor."}


def uninstall(project: Path, host: str) -> dict:
    root = _root(project)
    target, manifest_path = _paths(root, host)
    if not manifest_path.exists():
        return {"schema_version": 1, "status": "ok", "host": host, "removed": False}
    manifest = _manifest(manifest_path, host)
    config = _config(target)
    for relative in _skills(host):
        _inside(root, relative)
    conflicts = []
    for event, entries in manifest["hooks"].items():
        if any(entry not in config.get("hooks", {}).get(event, []) for entry in entries):
            conflicts.append(f"Modified or missing {event} hook")
    for relative in _skills(host):
        path = _inside(root, relative)
        if path.exists() and _digest(path.read_bytes()) != manifest["skills"].get(relative):
            conflicts.append(relative)
    if conflicts:
        return {"schema_version": 1, "status": "incomplete", "host": host,
                "removed": False, "preserved_conflicts": conflicts}
    for event, entries in manifest["hooks"].items():
        current = config.get("hooks", {}).get(event, [])
        for entry in entries:
            if entry in current:
                current.remove(entry)
        if not current:
            config.get("hooks", {}).pop(event, None)
    if not config.get("hooks"):
        config.pop("hooks", None)
    for relative in _skills(host):
        path = _inside(root, relative)
        if path.exists():
            path.unlink()
    if config or manifest["config_existed"]:
        _write(target, config)
    elif target.exists():
        target.unlink()
    manifest_path.unlink()
    return {"schema_version": 1, "status": "ok", "host": host,
            "removed": True, "preserved_conflicts": []}


def _version(host):
    executable = shutil.which(host)
    if not executable:
        return None
    try:
        run = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10, check=False)
        return run.stdout.strip()[:200] if run.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def record_invocation(project, host, payload, result):
    root = _root(project)
    _, manifest = _paths(root, host)
    event = payload.get("hook_event_name")
    if not manifest.exists() or event not in (*EVENTS, "PostToolUseFailure"):
        return
    own_hooks = _manifest(manifest, host)["hooks"]
    record = {"schema_version": 1, "event": event, "session_id": payload.get("session_id"),
              "recorded_at": datetime.now(timezone.utc).isoformat(), "config_fingerprint": _digest(own_hooks),
              "tool_name": payload.get("tool_name"), "tool_use_id": payload.get("tool_use_id"),
              "input_fingerprint": _digest(payload.get("tool_input", {})),
              "decision": result.get("hookSpecificOutput", {}).get("permissionDecision", result.get("decision"))}
    _write(_directory(root) / f"invoked-{host}-{event}.json", record)
    if event == "PreToolUse" and record["decision"] == "deny":
        _write(_directory(root) / f"denied-{host}.json", record)


def doctor(project: Path, host: str) -> dict:
    root = _root(project)
    target, manifest_path = _paths(root, host)
    config = _config(target)
    manifest = _manifest(manifest_path, host) if manifest_path.exists() else None
    configured = bool(manifest) and all(entry in config.get("hooks", {}).get(event, [])
                    for event, entries in manifest["hooks"].items() for entry in entries)
    disabled = host == "claude" and config.get("disableAllHooks") is True
    invocations = []
    if manifest:
        fingerprint = _digest(manifest["hooks"])
        for event in manifest["hooks"]:
            path = _directory(root) / f"invoked-{host}-{event}.json"
            if path.exists() and _read(path).get("config_fingerprint") == fingerprint:
                invocations.append(event)
    return {"schema_version": 1, "status": "ok" if configured and invocations and not disabled else "incomplete", "host": host,
            "host_version": _version(host), "configured": configured, "invoked": bool(invocations),
            "invoked_events": invocations, "invocation_host_version": "unverified", "disabled": disabled,
            "enforced": False, "trust": "Host-managed; review in /hooks",
            "coverage": ["Edit/Write file_path"] if host == "claude" else ["apply_patch targets and move ends"],
            "limits": ["No native rejected-write proof recorded by doctor", "Unknown shell and MCP mutations are not blocked", "Hook timeout or failure can bypass intervention"]}
