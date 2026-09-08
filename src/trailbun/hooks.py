"""Small native hook adapters; unknown tools never acquire invented coverage."""

from pathlib import Path


def tool_paths(tool: str, arguments: dict) -> list[str] | None:
    """Extract only documented Edit/Write and apply_patch file targets."""
    if tool not in {"Edit", "Write", "apply_patch"}:
        return None
    if not isinstance(arguments, dict):
        raise ValueError("Known edit tool has invalid arguments")
    if tool in {"Edit", "Write"}:
        path = arguments.get("file_path")
        if not isinstance(path, str) or not path.strip() or "\x00" in path:
            raise ValueError("Known edit tool has no valid file_path")
        return [path]
    patch = arguments.get("command")
    if not isinstance(patch, str):
        raise ValueError("apply_patch has no command string")
    lines = patch.strip().splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("Cannot determine targets from invalid apply_patch envelope")
    paths = []
    move_allowed = False
    for line in lines[1:-1]:
        if not line.startswith("*** "):
            continue
        kind, separator, path = line.partition(": ")
        if kind == "*** End of File":
            continue
        if kind not in {"*** Add File", "*** Update File", "*** Delete File", "*** Move to"}:
            raise ValueError("Unknown apply_patch file operation")
        if not separator or not path.strip() or "\x00" in path:
            raise ValueError("Invalid apply_patch target")
        if kind == "*** Move to" and not move_allowed:
            raise ValueError("apply_patch move has no source file")
        paths.append(path)
        move_allowed = kind == "*** Update File"
    if not paths:
        raise ValueError("apply_patch has no recognized file targets")
    return paths


def _load(root):
    from . import engine, store
    if not (store.directory(root) / "state.json").exists():
        return None
    state = store.load(root)
    engine._active(state)
    if not isinstance(state.get("run_id"), str) or not state["run_id"] or not isinstance(state.get("contract"), dict) or not isinstance(state.get("bindings", {}), dict):
        raise RuntimeError("Invalid Trailbun task or session-binding state")
    return state


def _root(root):
    from . import git
    return git.repo_root(root)


def _allowed(root, path, allowed):
    from . import git
    return git.path_allowed(git.repo_root(root), path, allowed)


def _assess(root):
    from . import engine
    return engine.check(root)


def _record(root, host, payload, result):
    from . import integration
    integration.record_invocation(root, host, payload, result)


def bind(root: Path, host: str, session_id: str) -> None:
    """Bind only on explicit start/resume; directory presence is insufficient."""
    from . import store
    if host not in {"claude", "codex"} or not session_id or len(session_id) > 256:
        raise ValueError("A supported host and valid session ID are required")
    with store.locked(root) as state:
        state.setdefault("bindings", {})[f"{host}:{session_id}"] = state["run_id"]


def _context(event, text):
    if len(text.encode("utf-8")) > 6144:
        text = "Trailbun context exceeds 6 KiB and was not fully restored. Run trailbun resume/check to inspect the complete task before changing files; shorten the saved checkpoint explicitly."
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": reason}}


def error_response(host: str, event: str, reason: str) -> dict:
    """Do not misrepresent a broken hook as an enforced policy decision."""
    return {"systemMessage": f"Trailbun hook unavailable; task not verified: {reason[:500]}"}


def _handle(root, host, payload):
    if host not in {"claude", "codex"} or not isinstance(payload, dict):
        raise ValueError("Unsupported host or invalid hook input")
    event = payload.get("hook_event_name", "")
    session = payload.get("session_id", "")
    if not isinstance(session, str) or not session or len(session) > 256:
        return {}
    state = _load(root)
    bound = state is not None and state.get("bindings", {}).get(f"{host}:{session}") == state.get("run_id")
    if event == "SessionStart":
        if bound and payload.get("source") in {"compact", "resume"}:
            from . import engine
            report = engine.resume(root)
            return _context(event, report.get("context", str(report.get("contract", {}))))
        task = "A recoverable task exists." if state else "No task is active."
        return _context(event, f"Trailbun: {task} Session binding: --host {host} --session {session}. Use trailbun start or resume explicitly to activate guards for this session.")
    if not bound:
        return {}
    if event == "PreToolUse":
        try:
            paths = tool_paths(payload.get("tool_name"), payload.get("tool_input"))
        except ValueError as exc:
            return _deny(f"Trailbun cannot validate this edit: {exc}")
        if paths is None:
            return {}
        if state.get("needs_diagnosis"):
            return _deny("Trailbun: repeated corrective failures require trailbun diagnose before another supported edit.")
        cwd = Path(payload.get("cwd", root))
        outside = [p for p in paths if not _allowed(root, str(Path(p) if Path(p).is_absolute() else cwd / p), state["contract"]["allowed_paths"])]
        if outside:
            return _deny("Trailbun scope violation: " + ", ".join(outside)[:1000])
    if event in {"PostToolUse", "PostToolUseFailure"}:
        report = _assess(root)
        if report.get("outside_allowed_paths"):
            return _context(event, "Trailbun detected workspace drift outside the task scope: " + ", ".join(report["outside_allowed_paths"]) + ". The operation already ran; inspect the changes.")
        if report.get("needs_diagnosis"):
            return _context(event, "Trailbun: run trailbun diagnose before the next supported edit.")
    if event == "Stop":
        report = _assess(root)
        if report.get("verification_current") and not report.get("outside_allowed_paths") and not report.get("needs_diagnosis"):
            return {}
        reason = "Trailbun task remains incomplete: refresh verification evidence and resolve scope or diagnosis findings. Do not claim completion without current passing evidence."
        if payload.get("stop_hook_active"):
            return {"systemMessage": reason}
        return {"decision": "block", "reason": reason}
    return {}


def handle(project: Path, host: str, payload: dict) -> dict:
    """Return native JSON. The CLI must always exit zero for this adapter."""
    if isinstance(payload, dict) and "cwd" in payload:
        if not isinstance(payload["cwd"], str) or not payload["cwd"]:
            raise ValueError("Invalid native hook working directory")
        project = Path(payload["cwd"])
    project = _root(project)
    result = _handle(project, host, payload)
    try:
        _record(project, host, payload, result)
    except (OSError, RuntimeError, ValueError) as exc:
        result["systemMessage"] = f"Trailbun invocation receipt could not be saved: {str(exc)[:300]}"
    return result
