"""Reversible project-local hook installation and honest coverage reporting."""

import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, UTC
from importlib.resources import files
from pathlib import Path

# Claude Code reads .claude/settings.local.json as project-local, per-machine settings
# (https://code.claude.com/docs/en/hooks, checked 2026-09-09). The generated command embeds
# this machine's interpreter path, so the local file is the default target.
HOSTS = {"claude": ".claude/settings.local.json", "codex": ".codex/hooks.json"}
SHARED_TARGETS = {"claude": ".claude/settings.json", "codex": ".codex/hooks.json"}
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")
HOOK_TIMEOUT = 60
# Tool names come from the host documentation: Edit, Write, NotebookEdit and Bash for Claude Code
# (https://code.claude.com/docs/en/hooks, checked 2026-09-09) and apply_patch for Codex, which also
# has a retained live receipt (evidence/native-codex-corrected-trust.json). Codex PostToolUse stays
# unmatched so shell writes remain observed after the fact whatever the shell tool is named.
MATCHERS = {
    "claude": {"PreToolUse": "Edit|Write|NotebookEdit", "PostToolUse": "Edit|Write|NotebookEdit|Bash",
               "PostToolUseFailure": "Edit|Write|NotebookEdit|Bash"},
    "codex": {"PreToolUse": "apply_patch"},
}
# Claude Code consults Edit(path) rules for every file-changing tool and for recognized Bash file
# commands and redirections; Write(path) rules are accepted but never consulted
# (https://code.claude.com/docs/en/permissions, checked 2026-09-09).
PERMISSION_DENY = ["Edit(/.trailbun/**)", "Edit(/.claude/settings.json)", "Edit(/.claude/settings.local.json)"]


def _root(root):
    from . import git
    return git.repo_root(root)


def _directory(root):
    from . import store
    return store.directory(root)


def _bootstrap(root):
    from . import store
    return store.bootstrap(root)


def _exclude(root, names, remove=False):
    from . import store
    return store.exclude_paths(root, names, remove=remove)


def _tracked(root, relative):
    from . import git
    try:
        return bool(git.run(root, "ls-files", "-z", "--", relative).strip(b"\0"))
    except RuntimeError:
        return False


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


def _codex_windows_command(executable):
    quoted = executable.replace("'", "''")
    script = "$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
    script += f"[Console]::In.ReadToEnd() | & '{quoted}' -X utf8 -m trailbun hook --host codex; "
    # A missing interpreter leaves $LASTEXITCODE null and stdout empty, which Codex reads as success.
    script += ("if ($null -eq $LASTEXITCODE) { Write-Output '{\"systemMessage\":\"Trailbun hook interpreter missing; "
               "task not verified\"}'; exit 0 }; exit $LASTEXITCODE")
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded}"


def _handlers(host, shared=False):
    if host not in HOSTS:
        raise ValueError("Host must be claude or codex")
    args = ["-X", "utf8", "-m", "trailbun", "hook", "--host", host]
    if host == "claude":
        if shared:
            # A shared file must not carry one machine's interpreter path; the host resolves trailbun on PATH.
            handler = {"type": "command", "command": "trailbun", "args": ["hook", "--host", host], "timeout": HOOK_TIMEOUT}
        else:
            handler = {"type": "command", "command": sys.executable, "args": args, "timeout": HOOK_TIMEOUT}
    else:
        handler = {"type": "command", "command": shlex.join([sys.executable, *args]),
                   "commandWindows": _codex_windows_command(sys.executable), "timeout": HOOK_TIMEOUT}
    events = (*EVENTS, "PostToolUseFailure") if host == "claude" else EVENTS
    groups = {}
    for event in events:
        group = {"hooks": [dict(handler)]}
        matcher = MATCHERS.get(host, {}).get(event)
        if matcher:
            group = {"matcher": matcher, **group}
        groups[event] = [group]
    return groups


def _skills(host):
    base = ".claude/skills" if host == "claude" else ".agents/skills"
    return {f"{base}/trailbun-{name}/SKILL.md": files("trailbun").joinpath("skills", name, "SKILL.md").read_bytes()
            for name in ("start", "resume", "diagnose")}


def _paths(root, host, shared=False):
    if host not in HOSTS:
        raise ValueError("Host must be claude or codex")
    manifest_path = _directory(root) / f"install-{host}.json"
    relative = SHARED_TARGETS[host] if shared else HOSTS[host]
    if manifest_path.exists():
        try:
            recorded = _read(manifest_path).get("target")
        except ValueError:
            recorded = None
        if isinstance(recorded, str) and recorded in (HOSTS[host], SHARED_TARGETS[host]):
            relative = recorded
        elif recorded is None and host == "claude":
            relative = SHARED_TARGETS[host]  # 0.2.0 manifests recorded no target and wrote settings.json.
    return _inside(root, relative), manifest_path


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
    value.setdefault("generated_paths", [])
    value.setdefault("permissions_deny", [])
    return value


def _deny_rules(config):
    permissions = config.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError("Invalid permissions configuration")
    rules = permissions.setdefault("deny", [])
    if not isinstance(rules, list):
        raise ValueError("Invalid permissions.deny configuration")
    return rules


def setup(project: Path, host: str, shared: bool = False) -> dict:
    root = _root(project)
    target, manifest_path = _paths(root, host, shared)
    manifest = _manifest(manifest_path, host) if manifest_path.exists() else None
    if manifest and shared and manifest.get("target") not in (None, SHARED_TARGETS[host]):
        raise ValueError(f"Trailbun is installed in {manifest['target']}; uninstall before switching to --shared")
    config = _config(target)
    templates = _skills(host)
    old_hooks = manifest["hooks"] if manifest else {}
    for event, entries in old_hooks.items():
        if any(entry not in config.get("hooks", {}).get(event, []) for entry in entries):
            raise ValueError(f"Installation conflict: modified {event} hook")
    for relative in templates:
        path = _inside(root, relative)
        if path.exists() and (not manifest or _digest(path.read_bytes()) != manifest["skills"].get(relative)):
            raise ValueError(f"Installation conflict: {relative}")
    owned = _handlers(host, shared)
    if not manifest and any(entry in config.get("hooks", {}).get(event, []) for event, entries in owned.items() for entry in entries):
        raise ValueError("Installation conflict: identical hook exists without a Trailbun ownership manifest")
    hooks = config.setdefault("hooks", {})
    for event, entries in old_hooks.items():
        hooks[event] = [entry for entry in hooks[event] if entry not in entries]
    for event, entries in owned.items():
        hooks.setdefault(event, []).extend(entries)
    deny = []
    if host == "claude":
        rules = _deny_rules(config)
        deny = [rule for rule in PERMISSION_DENY if rule not in rules or rule in (manifest or {}).get("permissions_deny", [])]
        for rule in deny:
            if rule not in rules:
                rules.append(rule)
    config_existed = manifest["config_existed"] if manifest else target.exists()
    relative_target = target.relative_to(root).as_posix()
    generated = [relative for relative in templates if not _tracked(root, relative)]
    if not config_existed and not _tracked(root, relative_target):
        generated.append(relative_target)
    record = {"schema_version": 1, "host": host, "hooks": owned, "target": relative_target,
              "shared": bool(shared), "config_existed": config_existed,
              "skills": {p: _digest(content) for p, content in templates.items()},
              "generated_paths": sorted(generated), "permissions_deny": deny,
              "matchers": MATCHERS.get(host, {}), "hook_timeout_seconds": HOOK_TIMEOUT,
              "installed_at": datetime.now(UTC).isoformat()}
    # Validate every destination before the first mutation.
    _bootstrap(root)
    for relative, content in templates.items():
        _write(_inside(root, relative), content)
    _write(target, config)
    _write(manifest_path, record)
    # Generated files are machine-specific; keep them out of git status so start sees a clean tree.
    _exclude(root, generated)
    warnings = []
    if shared and host == "claude":
        warnings.append("Shared settings run `trailbun` from PATH; every teammate needs the CLI installed.")
    return {"schema_version": 1, "status": "ok", "host": host, "configured": True, "target": relative_target,
            "generated_paths": sorted(generated), "permissions_deny": deny, "warnings": warnings,
            "next": (f"Restart {host} in this project and review hook trust. The SessionStart hook prints a session ID; "
                     f"then run: trailbun start --contract .trailbun/task.json --host {host} --session <SESSION_ID>. "
                     f"Check with: trailbun doctor --host {host} --probe.")}


def uninstall(project: Path, host: str) -> dict:
    root = _root(project)
    target, manifest_path = _paths(root, host)
    if not manifest_path.exists():
        return {"schema_version": 1, "status": "ok", "host": host, "removed": False,
                "note": "No Trailbun installation manifest for this host; nothing to remove."}
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
    if manifest.get("permissions_deny"):
        rules = config.get("permissions", {}).get("deny", [])
        for rule in manifest["permissions_deny"]:
            if rule in rules:
                rules.remove(rule)
        if not rules:
            config.get("permissions", {}).pop("deny", None)
        if not config.get("permissions"):
            config.pop("permissions", None)
    for relative in _skills(host):
        path = _inside(root, relative)
        if path.exists():
            path.unlink()
    if config or manifest["config_existed"]:
        _write(target, config)
    elif target.exists():
        target.unlink()
    _exclude(root, manifest.get("generated_paths", []), remove=True)
    manifest_path.unlink()
    return {"schema_version": 1, "status": "ok", "host": host,
            "removed": True, "preserved_conflicts": []}


def _version(host):
    from . import git
    try:
        executable = git.executable(host)
    except OSError:
        return None
    try:
        run = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10, check=False)
        return run.stdout.strip()[:200] if run.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _state_digest(root):
    path = _directory(root) / "state.json"
    try:
        return _digest(path.read_bytes()) if path.is_file() else None
    except OSError:
        return None


def record_invocation(project, host, payload, result):
    root = _root(project)
    _, manifest = _paths(root, host)
    event = payload.get("hook_event_name")
    if not manifest.exists() or event not in (*EVENTS, "PostToolUseFailure"):
        return
    own_hooks = _manifest(manifest, host)["hooks"]
    record = {"schema_version": 1, "event": event, "session_id": payload.get("session_id"),
              "recorded_at": datetime.now(UTC).isoformat(), "config_fingerprint": _digest(own_hooks),
              "state_sha256": _state_digest(root),
              "tool_name": payload.get("tool_name"), "tool_use_id": payload.get("tool_use_id"),
              "input_fingerprint": _digest(payload.get("tool_input", {})),
              "reason": str(result.get("hookSpecificOutput", {}).get("permissionDecisionReason", result.get("reason", "")))[:1200],
              "decision": result.get("hookSpecificOutput", {}).get("permissionDecision", result.get("decision"))}
    _write(_directory(root) / f"invoked-{host}-{event}.json", record)
    if event == "PreToolUse" and record["decision"] == "deny":
        _write(_directory(root) / f"denied-{host}.json", record)


def _settings_files(root):
    """Claude settings in precedence order, lowest first: user, project, local."""
    files_ = [("user", Path.home() / ".claude" / "settings.json"),
              ("project", root / ".claude" / "settings.json"),
              ("local", root / ".claude" / "settings.local.json")]
    return files_


def hooks_disabled(root, host):
    """Return the settings file whose disableAllHooks value wins, or None. Managed settings are not readable here."""
    if host != "claude":
        return None
    winner = None
    for scope, path in _settings_files(root):
        if not path.is_file():
            continue
        try:
            value = _read(path).get("disableAllHooks")
        except ValueError:
            continue
        if value is True:
            winner = f"{scope}:{path}"
        elif value is False:
            winner = None
    return winner


def config_drift(root, host):
    """Differences between the live hook configuration and the installation manifest."""
    root = _root(root)
    target, manifest_path = _paths(root, host)
    if not manifest_path.exists():
        return []
    manifest = _manifest(manifest_path, host)
    drift = []
    if not target.exists():
        return [f"{target.relative_to(root).as_posix()} is missing"]
    try:
        config = _config(target)
    except ValueError as exc:
        return [str(exc)[:200]]
    for event, entries in manifest["hooks"].items():
        if any(entry not in config.get("hooks", {}).get(event, []) for entry in entries):
            drift.append(f"{event} hook removed or modified")
    if host == "claude":
        rules = config.get("permissions", {}).get("deny", []) if isinstance(config.get("permissions"), dict) else []
        missing = [rule for rule in manifest.get("permissions_deny", []) if rule not in rules]
        if missing:
            drift.append("permissions.deny rules removed: " + ", ".join(missing))
    disabled = hooks_disabled(root, host)
    if disabled:
        drift.append(f"disableAllHooks is true in {disabled}")
    return drift


def probe(root, host, manifest):
    """Start the installed handler with a synthetic SessionStart payload and report whether it answered."""
    entry = manifest["hooks"]["SessionStart"][0]["hooks"][0]
    if host == "claude":
        argv = [entry["command"], *entry.get("args", [])]
    elif os.name == "nt" and entry.get("commandWindows"):
        argv = shlex.split(entry["commandWindows"], posix=False)
    else:
        argv = shlex.split(entry["command"])
    payload = {"hook_event_name": "SessionStart", "session_id": "trailbun-doctor-probe", "source": "startup",
               "cwd": str(root)}
    result = {"argv_head": argv[0], "handler_started": False, "handler_output_valid": False, "detail": None}
    try:
        run = subprocess.run(argv, input=json.dumps(payload).encode(), capture_output=True, timeout=30, cwd=root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["detail"] = str(exc)[:300]
        return result
    result["exit_code"] = run.returncode
    text = run.stdout.decode("utf-8", "replace").strip()
    try:
        output = json.loads(text) if text else None
    except ValueError:
        output = None
    context = (output or {}).get("hookSpecificOutput", {}).get("additionalContext", "") if isinstance(output, dict) else ""
    result["handler_started"] = isinstance(output, dict) and ("Trailbun" in context or "systemMessage" in output)
    result["handler_output_valid"] = isinstance(output, dict) and "Trailbun" in context
    if not result["handler_started"]:
        result["detail"] = (run.stderr.decode("utf-8", "replace").strip() or text or "no output")[:300]
    return result


def doctor(project: Path, host: str, run_probe: bool = False) -> dict:
    root = _root(project)
    target, manifest_path = _paths(root, host)
    config = _config(target)
    manifest = _manifest(manifest_path, host) if manifest_path.exists() else None
    configured = bool(manifest) and all(entry in config.get("hooks", {}).get(event, [])
                    for event, entries in manifest["hooks"].items() for entry in entries)
    disabled_by = hooks_disabled(root, host)
    disabled = disabled_by is not None
    invocations = []
    if manifest:
        fingerprint = _digest(manifest["hooks"])
        for event in manifest["hooks"]:
            path = _directory(root) / f"invoked-{host}-{event}.json"
            if path.exists() and _read(path).get("config_fingerprint") == fingerprint:
                invocations.append(event)
    probe_result = probe(root, host, manifest) if run_probe and manifest else None
    coverage = (["Edit, Write and NotebookEdit path fields (adapter fixtures; no live Claude receipt yet)",
                 "permissions.deny for .trailbun and the settings files (host-documented, live-unverified)"]
                if host == "claude" else
                ["apply_patch targets and move ends (live receipt: Codex 0.153.4, Windows 11)"])
    status = "ok" if configured and invocations and not disabled else "incomplete"
    if probe_result is not None and not probe_result["handler_started"]:
        status = "incomplete"
    return {"schema_version": 1, "status": status, "host": host,
            "target": target.relative_to(root).as_posix(),
            "host_version": _version(host), "configured": configured, "invoked": bool(invocations),
            "invoked_events": invocations, "invocation_host_version": "unverified",
            "disabled": disabled, "disabled_by": disabled_by, "probe": probe_result,
            "drift": config_drift(root, host) if manifest else [],
            "enforced": False, "trust": "Host-managed; review in /hooks",
            "matchers": manifest.get("matchers", {}) if manifest else {},
            "coverage": coverage,
            "limits": ["No native rejected-write proof recorded by doctor",
                       "Unknown shell and MCP mutations are not blocked",
                       "Hook timeout or failure can bypass intervention",
                       "The agent can amend, abandon or diagnose; those commands are recorded, not blocked"]}
