import json
import subprocess
import sys

from trailbun import __version__


def run(*args):
    return subprocess.run([sys.executable, '-m', 'trailbun', *args], capture_output=True, text=True)


def test_version():
    result = run('--version')
    assert result.returncode == 0
    assert __version__ in result.stdout


def test_invalid_contract_is_structured_incomplete(tmp_path):
    invalid = tmp_path / 'contract.json'
    invalid.write_text('{not json')
    result = run('start', '--contract', str(invalid), '--project', str(tmp_path), '--json')
    assert result.returncode == 2
    assert json.loads(result.stdout)['status'] == 'incomplete'


def test_demo_is_real_and_isolated(tmp_path):
    result = run('demo', '--output', str(tmp_path / 'evidence'), '--json')
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout)
    assert evidence['status'] == 'ok'
    assert evidence['steps'][1]['status'] == 'violation'
    assert evidence['steps'][-1]['status'] == 'ok'
    assert (tmp_path / 'evidence' / 'demo.json').exists()


def test_unknown_command_is_an_error():
    assert run('forget-the-plan').returncode == 2


def test_invalid_session_is_rejected_before_task_mutation(repo, contract, tmp_path_factory):
    from trailbun import git, store
    path = tmp_path_factory.mktemp('external-contract') / 'input.json'
    path.write_text(json.dumps(contract))
    assert git.clean(repo)
    result = run('start', '--contract', str(path), '--project', str(repo),
                 '--host', 'claude', '--session', 'a' * 257, '--json')
    assert result.returncode == 2
    assert 'Session ID' in json.loads(result.stdout)['error']
    assert not (store.directory(repo) / 'state.json').exists()
