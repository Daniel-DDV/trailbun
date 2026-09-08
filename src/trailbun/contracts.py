"""Validate the small, explicit contract accepted by Trailbun."""

import hashlib
import json
import re
from pathlib import PurePosixPath


def text(value, name, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise ValueError(f"{name} must be nonempty text of at most {limit} characters")
    return value


def path(value):
    value = text(value, "path", 1024).replace("\\", "/")
    parts = PurePosixPath(value).parts
    if (value.startswith("/") or re.match(r"^[A-Za-z]:", value)
            or ".." in parts or any(c in value for c in "*?")
            or (parts and parts[0].lower() in {".git", ".trailbun"})):
        raise ValueError(f"Path must be a repository-relative file or directory: {value!r}")
    return str(PurePosixPath(value))


def _list(value, name, convert, required=False):
    if not isinstance(value, list) or len(value) > 128 or (required and not value):
        raise ValueError(f"{name} must be a {'nonempty ' if required else ''}list of at most 128 items")
    return [convert(item) for item in value]


def validate(value):
    if not isinstance(value, dict):
        raise ValueError("Contract must be an object")
    allowed = {"goal", "exclusions", "allowed_paths", "checks", "watch_ignored", "expected_red"}
    if set(value) - allowed:
        raise ValueError("Unknown contract fields: " + ", ".join(sorted(set(value) - allowed)))
    result = {"goal": text(value.get("goal"), "goal")}
    result["exclusions"] = _list(value.get("exclusions", []), "exclusions", lambda x: text(x, "exclusion"))
    for name in ("allowed_paths", "watch_ignored"):
        result[name] = sorted(set(_list(value.get(name, []), name, path, name == "allowed_paths")))
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks or len(checks) > 32:
        raise ValueError("checks must contain 1 to 32 named acceptance checks")
    result["checks"] = []
    identifiers = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) - {"id", "argv", "timeout_seconds"}:
            raise ValueError("Each check needs id, argv and optional timeout_seconds")
        identifier = text(check.get("id"), "check id", 64)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identifier) or identifier in identifiers:
            raise ValueError("Check ids must be unique simple names")
        identifiers.add(identifier)
        timeout = check.get("timeout_seconds", 60)
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError("Check timeout_seconds must be an integer between 1 and 600")
        argv = _list(check.get("argv"), "argv", lambda x: text(x, "argument"), True)
        result["checks"].append({"id": identifier, "argv": argv, "timeout_seconds": timeout})
    result["expected_red"] = sorted(set(_list(value.get("expected_red", []), "expected_red", lambda x: text(x, "check id", 64))))
    if set(result["expected_red"]) - identifiers:
        raise ValueError("expected_red must reference declared check ids")
    return result


def digest(contract):
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()
