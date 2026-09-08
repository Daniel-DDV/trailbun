import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("native_compact", Path(__file__).parents[1] / "scripts/native_compact.py")
native = importlib.util.module_from_spec(spec)


def test_compact_requires_native_completion_then_matching_context_hook():
    spec.loader.exec_module(native)
    compact = {"method": "item/completed", "params": {"threadId": "thread", "item": {"type": "contextCompaction"}}}
    restored = {"method": "hook/completed", "params": {"threadId": "thread", "run": {"eventName": "sessionStart", "status": "completed", "entries": [{"kind": "context", "text": "canonical"}]}}}
    assert native.context_restored([compact, restored], "thread", "canonical")
    assert not native.context_restored([restored, compact], "thread", "canonical")
    assert not native.context_restored([compact, restored], "different", "canonical")
    assert not native.context_restored([compact, restored], "thread", "longer canonical")


def test_post_probe_inspection_errors_are_retained(monkeypatch, tmp_path):
    spec.loader.exec_module(native)
    def denied(*args):
        raise PermissionError("sandbox-owned artifact unavailable")
    monkeypatch.setattr(native, "user_config_snapshot", denied)
    monkeypatch.setattr(native, "source_hashes", denied)
    monkeypatch.setattr(native.engine, "check", denied)
    monkeypatch.setattr(native.store, "load", denied)
    values, errors = native.inspect_runtime(tmp_path)
    assert not any(values.values()) and len(errors) == 4


def test_public_events_omit_unrelated_account_and_installation_metadata():
    spec.loader.exec_module(native)
    proof = {"method": "hook/completed", "params": {"run": {"entries": []}}}
    private = [{"method": "account/rateLimits/updated", "params": {"credits": {"balance": "private"}}},
               {"method": "remoteControl/status/changed", "params": {"installationId": "private"}}]
    assert native.public_events([*private, proof]) == [proof]
