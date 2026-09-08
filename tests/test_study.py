import json

import pytest

from benchmarks import study
from benchmarks.tasks import TASKS
from trailbun import engine, store


@pytest.mark.parametrize('name', ['scope', 'resume', 'recovery'])
def test_fixtures_fail_initially_and_original_grader_accepts_solution(tmp_path, name):
    root = tmp_path / name
    prepared = study.prepare(root, name, 'plain')
    assert not study.score(root, prepared)['acceptance_passed']
    for path, content in TASKS[name]['solution'].items():
        (root / path).write_text(content, encoding='utf-8')
    result = study.score(root, prepared)
    assert result['acceptance_passed']
    assert result['protected_files_unchanged']
    assert result['out_of_scope_paths'] == []


def test_grading_does_not_trust_edited_acceptance_or_allow_extra_files(tmp_path):
    root = tmp_path / 'fixture'
    prepared = study.prepare(root, 'scope', 'plain')
    (root / 'acceptance.py').write_text('print("passed")\n')
    result = study.score(root, prepared)
    assert not result['acceptance_passed']
    assert not result['protected_files_unchanged']
    (root / 'unnecessary.py').write_text('pass\n')
    assert 'unnecessary.py' in study.score(root, prepared)['out_of_scope_paths']


def test_recovery_seeds_actual_distinct_failed_corrections(tmp_path):
    root = tmp_path / 'fixture'
    prepared = study.prepare(root, 'recovery', 'trailbun')
    state = store.load(root)
    assert state['needs_diagnosis'] is True
    assert state['failures']['acceptance']['count'] == 2
    assert len(prepared['seeded_attempts']) == 2
    assert all(attempt['exit_code'] != 0 for attempt in prepared['seeded_attempts'])


def test_scope_fixture_allows_justified_amendment_without_moving_baseline(tmp_path):
    root = tmp_path / 'fixture'
    prepared = study.prepare(root, 'scope', 'trailbun')
    contract = json.loads((root / '.trailbun/study-contract.json').read_text())
    engine.start(root, contract)
    original = store.load(root)['baseline']
    for path, content in TASKS['scope']['solution'].items():
        (root / path).write_text(content)
    assert 'app/routes.py' in engine.check(root)['outside_allowed_paths']
    contract['allowed_paths'].append('app/routes.py')
    result = engine.amend(root, contract, 'The stated requirement changes the shared login route.')
    assert result['outside_allowed_paths'] == []
    assert store.load(root)['baseline'] == original == prepared['baseline']
    assert study.score(root, prepared)['acceptance_passed']


def test_host_commands_use_fresh_sessions_without_trust_or_sandbox_bypass(tmp_path):
    for host in ('codex', 'claude'):
        command = study.host_command(host, 'explicit-model', tmp_path, host)
        assert 'explicit-model' in command
        assert not any('dangerously' in part for part in command)
        assert '--resume' not in command
    codex = study.host_command('codex', 'explicit-model', tmp_path, 'codex')
    assert '--ignore-user-config' in codex and '--ephemeral' in codex
    assert codex[codex.index('--sandbox') + 1] == 'workspace-write'
    assert ('windows.sandbox="elevated"' in codex) == (study.os.name == 'nt')
    claude = study.host_command('claude', 'explicit-model', tmp_path, 'claude')
    assert claude[claude.index('--setting-sources') + 1] == 'project'
    assert '--strict-mcp-config' in claude


def test_default_only_prints_plan_and_does_not_call_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(study, 'run_study', lambda *_: pytest.fail('A model was called'))
    output = tmp_path / 'evidence'
    assert study.main(['--host', 'codex', '--task', 'resume', '--condition', 'plain',
                       '--repeat', '1', '--output', str(output)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['mode'] == 'plan-only' and plan['phase_count'] == 2
    assert not output.exists()


def test_telemetry_keeps_actual_model_distinct_from_requested_model():
    log = '\n'.join(json.dumps(event) for event in [
        {'type': 'system', 'subtype': 'init', 'model': 'reported-model'},
        {'type': 'result', 'usage': {'input_tokens': 10, 'output_tokens': 4},
         'total_cost_usd': 0.01}])
    result = study.telemetry(log)
    assert result['reported_models'] == ['reported-model']
    assert result['usage'][0]['input_tokens'] == 10
    assert study.telemetry('not json')['reported_models'] == []


def test_export_redacts_local_roots_and_known_secret_values(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_API_KEY', 'do-not-publish-this-value')
    text = f'{tmp_path} do-not-publish-this-value Bearer abcdefghijklmnop'
    redacted = study.redact(text, tmp_path)
    assert str(tmp_path) not in redacted
    assert 'do-not-publish-this-value' not in redacted
    assert 'abcdefghijklmnop' not in redacted
    from pathlib import Path
    source = str(Path(study.__file__).resolve().parents[1])
    for escaped_layers in range(5):
        assert study.redact(source.replace('\\', '\\' * (2 ** escaped_layers)), tmp_path) == '<TRAILBUN_SOURCE>'


def test_summary_preserves_missing_cells_and_missing_usage(tmp_path):
    from benchmarks.summarize import summarize

    folder = tmp_path / 'codex-scope-plain-1'
    folder.mkdir()
    report = {'host': 'codex', 'task': 'scope', 'condition': 'plain', 'repeat': 1,
              'status': 'completed', 'requested_model': 'chosen-model',
              'phases': [{'duration_seconds': 2, 'exit_code': 0, 'timed_out': False,
                          'telemetry': {'usage': [], 'reported_models': [], 'reported_cost_usd': []}}],
              'score': {'task_success': False, 'acceptance_passed': False}}
    (folder / 'run.json').write_text(json.dumps(report))
    (folder / 'phase-1-stderr.txt').write_text('rejected: blocked by policy')
    result = summarize(tmp_path)
    assert result['recorded_runs'] == 1 and result['missing_runs'] == 23
    assert result['policy_blocked_runs'] == 1
    assert result['reported_usage_totals'] == {}
    assert result['reported_cost_usd'] is None
    assert result['reported_models'] == []
    assert result['rows'][12]['host_process_status'] == 'completed'
    assert result['rows'][12]['task_success'] is False
