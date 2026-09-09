"""Probe native manual compaction and the subsequent SessionStart context.

One manual compaction request and one short next turn; never an automatic-compaction claim.
Protocol: https://learn.chatgpt.com/docs/app-server#trigger-thread-compaction
"""

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.native_smoke import command, sha, source_hashes, user_config_snapshot
from benchmarks.study import _resolve_host, redact
from trailbun import __version__, engine, integration, store


def context_restored(events, thread, expected):
    compacted = False
    for event in events:
        params = event.get("params", {})
        if params.get("threadId") != thread:
            continue
        if event.get("method") == "item/completed" and params.get("item", {}).get("type") == "contextCompaction":
            compacted = True
        run = params.get("run", {})
        if (compacted and event.get("method") == "hook/completed" and run.get("eventName") == "sessionStart"
                and run.get("status") == "completed" and any(entry.get("kind") == "context" and entry.get("text") == expected for entry in run.get("entries", []))):
            return True
    return False


def public_events(events):
    methods = {"hook/started", "hook/completed", "item/started", "item/completed",
               "turn/started", "turn/completed", "thread/tokenUsage/updated", "warning", "error"}
    return [event for event in events if event.get("method") in methods]


def inspect_runtime(root):
    values, errors = {}, []
    operations = {"config": user_config_snapshot, "sources": source_hashes,
                  "fingerprint": lambda: engine.check(root)["fingerprint"], "state": lambda: store.load(root)}
    for name, operation in operations.items():
        try:
            values[name] = operation()
            if name == "sources":
                values[name]["scripts/native_smoke.py"] = sha(Path(command.__code__.co_filename))
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            values[name] = None
            errors.append(f"{name}: {exc}")
    return values, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    stream_path, script_path = output.with_suffix(".events.jsonl"), output.with_suffix(".script.py")
    if any(path.exists() for path in (output, stream_path, script_path)):
        raise FileExistsError("Preserve earlier probe evidence; choose another output")
    script_bytes = Path(__file__).read_bytes()
    root = Path(tempfile.mkdtemp(prefix="trailbun-native-compact-"))
    command(["git", "init", "-q", str(root)], root)
    (root / "src").mkdir()
    (root / "src/inside.txt").write_text("unchanged\n")
    (root / "AGENTS.md").write_text("This isolated compaction fixture allows no tool calls, edits, network access or agents. Answer briefly.\n")
    integration.setup(root, "codex")
    command(["git", "add", "."], root)
    command(["git", "-c", "user.name=Trailbun fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Manual compaction fixture"], root)
    engine.start(root, {"goal": "Restore the violet-rabbit task after manual compaction", "allowed_paths": ["src"],
        "exclusions": ["No edits during this probe"], "checks": [{"id": "fixture", "argv": [sys.executable, "-c", "pass"]}]})
    engine.checkpoint(root, {"summary": "Checkpoint violet-rabbit-17", "next_action": "Report the saved checkpoint without editing files"})
    canonical = engine.resume(root)["context"]
    artifact_before = engine.check(root)["fingerprint"]
    config_before, sources_before = user_config_snapshot(), source_hashes()
    sources_before["scripts/native_smoke.py"] = sha(Path(command.__code__.co_filename))
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    config = tomllib.loads((home / "config.toml").read_text()) if (home / "config.toml").exists() else {}
    # Prevent unrelated user MCP servers/plugins from starting in this fixture.
    mcp = "mcp_servers={" + ",".join(json.dumps(name) + "={enabled=false}" for name in config.get("mcp_servers", {})) + "}"
    binary = _resolve_host("codex")
    argv = [*binary, "-c", "projects={" + json.dumps(str(root)) + '={trust_level="trusted"}}',
            "-c", mcp, "-c", "features.plugins=false"]
    if os.name == "nt":
        argv += ["-c", 'windows.sandbox="elevated"']
    argv += ["app-server"]
    version = command([*binary, "--version"], root)
    process = subprocess.Popen(argv, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", start_new_session=os.name != "nt")
    messages, events, errors = queue.Queue(), [], []
    def reader():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
        messages.put(None)
    threading.Thread(target=reader, daemon=True).start()
    stderr = []
    threading.Thread(target=lambda: stderr.extend(process.stderr), daemon=True).start()
    request_id = 0
    def receive(deadline):
        value = messages.get(timeout=max(.01, deadline - time.monotonic()))
        if value is None:
            raise RuntimeError("Native app-server ended unexpectedly")
        if "method" in value:
            events.append(value)
        return value
    def request(method, params):
        nonlocal request_id
        request_id += 1
        process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 120
        while True:
            value = receive(deadline)
            if value.get("id") == request_id:
                if "error" in value:
                    raise RuntimeError(str(value["error"]))
                return value["result"]
    def wait_turn():
        deadline = time.monotonic() + 120
        while True:
            value = receive(deadline)
            if value.get("method") == "turn/completed":
                if value["params"]["turn"]["status"] != "completed":
                    raise RuntimeError(str(value["params"]["turn"]))
                return
    thread = session = None
    started = time.monotonic()
    try:
        request("initialize", {"clientInfo": {"name": "trailbun-compaction-probe", "version": __version__}, "capabilities": {"experimentalApi": True}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        effective = request("config/read", {"cwd": str(root), "includeLayers": True})
        flags = next(layer["config"] for layer in effective["layers"] if layer["name"]["type"] == "sessionFlags")
        if flags.get("projects") != {str(root): {"trust_level": "trusted"}}:
            raise RuntimeError("Exact fixture trust was not loaded")
        listed = request("hooks/list", {"cwds": [str(root)]})
        handlers = [hook for data in listed["data"] for hook in data["hooks"]]
        if len(handlers) != 4 or any(Path(h["sourcePath"]).parent != root / ".codex" for h in handlers):
            raise RuntimeError("Absent or unrelated hooks in native fixture")
        if config_before != user_config_snapshot():
            raise RuntimeError("User configuration changed before thread start")
        result = request("thread/start", {"cwd": str(root), "model": "gpt-6-astra", "approvalPolicy": "never",
            "sandbox": "workspace-write", "ephemeral": True, "config": {"bypass_hook_trust": True},
            "developerInstructions": "This isolated compaction probe permits no tool calls. Answer briefly and leave verification incomplete."})
        thread = result["thread"]["id"]
        session = result["thread"].get("sessionId", thread)  # Root threads own their session ID.
        command([sys.executable, "-m", "trailbun", "resume", "--host", "codex", "--session", session, "--json"], root)
        request("thread/inject_items", {"threadId": thread, "items": [{"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "We are running a manual compaction fixture. No edits or tools are needed. Preserve the current task, scope and checkpoint. This is a short controlled conversation, not automatic context pressure."}]}]})
        request("thread/compact/start", {"threadId": thread})
        wait_turn()
        request("turn/start", {"threadId": thread, "input": [{"type": "text", "text": "Acknowledge the restored Trailbun checkpoint in one sentence. Use no tools. Verification stays incomplete."}]})
        wait_turn()
    except (OSError, RuntimeError, ValueError, KeyError, queue.Empty) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10, check=True)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"Native process cleanup: {exc}")
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError) as retry:
                errors.append(f"Native process cleanup retry: {retry}")
    observed, inspection_errors = inspect_runtime(root)
    errors.extend(inspection_errors)
    after, sources_after = observed["config"], observed["sources"]
    state = observed["state"] or {}
    restored = context_restored(events, thread, canonical)
    checks = {"native_context_after_compaction": restored, "user_config_unchanged": config_before == after,
        "sources_unchanged": sources_before == sources_after, "artifacts_unchanged": artifact_before == observed["fingerprint"],
        "bound_session": bool(state.get("run_id")) and state.get("bindings", {}).get("codex:" + str(session)) == state["run_id"], "no_errors": not errors}
    output.parent.mkdir(parents=True, exist_ok=True)
    with stream_path.open("x", encoding="utf-8") as stream:
        stream.write(redact("\n".join(json.dumps(event) for event in public_events(events)) + "\n", root))
    with script_path.open("xb") as stream:
        stream.write(script_bytes)
    report = {"schema_version": 1, "status": "ok" if all(checks.values()) else "incomplete", "checks": checks,
        "measured_at": datetime.now(UTC).isoformat(), "host_version": version, "requested_model": "gpt-6-astra",
        "fixture": str(root), "thread_id": thread, "session_id": session, "canonical_context": canonical,
        "user_config_before": config_before, "user_config_after": after, "sources_before": sources_before, "sources_after": sources_after,
        "elapsed_seconds": round(time.monotonic() - started, 3), "errors": errors, "stderr": "".join(stderr),
        "event_export": "Only hook, item, turn, token-usage and diagnostic notifications; account and installation metadata omitted",
        "events": {"path": stream_path.name, "sha256": sha(stream_path)}, "script": {"path": script_path.name, "sha256": sha(script_path)},
        "limits": ["Manual compaction with a short injected user history only", "Automatic compaction remains unverified", "No model-response quality or subsequent tool behavior claim"],
        "sources": ["https://learn.chatgpt.com/docs/app-server#trigger-thread-compaction", "https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/hook_runtime.rs#L117"]}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(redact(json.dumps(report, indent=2) + "\n", root))
    print(json.dumps({"status": report["status"], "output": str(output), "checks": checks}))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
