import subprocess
import sys

import pytest

from trailbun import engine, store
from trailbun.verify import verify


@pytest.fixture
def task(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    for key, value in [('user.name', 'Test'), ('user.email', 'test@example.invalid')]:
        subprocess.run(['git', '-C', str(tmp_path), 'config', key, value], check=True)
    (tmp_path / 'answer.txt').write_text('no', encoding='utf-8')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), 'commit', '-qm', 'baseline'], check=True)
    contract = {'goal': 'Write yes', 'exclusions': ['No other changes'],
                'allowed_paths': ['answer.txt'], 'checks': [{'id': 'answer', 'argv': [sys.executable, '-c',
                "from pathlib import Path; assert Path('answer.txt').read_text() == 'yes'"]}]}
    engine.start(tmp_path, contract)
    return tmp_path


def test_success_receipt_becomes_stale(task):
    (task / 'answer.txt').write_text('yes')
    result = verify(task)
    assert result['status'] == 'ok'
    assert engine.check(task)['verification_current']
    (task / 'answer.txt').write_text('changed')
    assert not engine.check(task)['verification_current']


def test_duplicates_do_not_count_as_corrective_attempts(task):
    (task / 'answer.txt').write_text('attempt one')
    assert verify(task)['status'] == 'violation'
    verify(task)
    assert not store.load(task).get('needs_diagnosis', False)
    (task / 'answer.txt').write_text('attempt two')
    verify(task)
    assert store.load(task)['needs_diagnosis']


def test_check_mutating_source_cannot_attest_it(task):
    state = store.load(task)
    contract = state['contract']
    contract['checks'][0]['argv'] = [sys.executable, '-c', "from pathlib import Path; Path('answer.txt').write_text('yes')"]
    engine.amend(task, contract, 'Exercise a mutating verification command')
    assert verify(task)['status'] == 'incomplete'
    assert not engine.check(task)['verification_current']


def test_missing_executable_is_incomplete(task):
    contract = store.load(task)['contract']
    contract['checks'][0]['argv'] = ['trailbun-command-that-does-not-exist']
    engine.amend(task, contract, 'Test missing executable')
    assert verify(task)['status'] == 'incomplete'


def test_scoped_violation_prevents_verification_commands(task):
    (task / 'unapproved.txt').write_text('unexpected')
    result = verify(task)
    assert result['status'] == 'violation'
    assert result.get('checks', []) == []


def test_expected_red_is_once_and_does_not_count(task):
    contract = store.load(task)['contract']
    contract['expected_red'] = ['answer']
    engine.amend(task, contract, 'Explicit initial TDD baseline')
    result = verify(task, baseline=True)
    assert result['expected_red_observed']
    assert store.load(task)['failures'] == {}
    with pytest.raises(ValueError):
        verify(task, baseline=True)
    (task / 'answer.txt').write_text('first real correction')
    verify(task)
    assert not store.load(task)['needs_diagnosis']


def test_timeout_is_incomplete_not_a_failed_correction(task):
    contract = store.load(task)['contract']
    contract['checks'][0].update(argv=[sys.executable, '-c', 'import time; time.sleep(2)'], timeout_seconds=1)
    engine.amend(task, contract, 'Exercise timeout')
    assert verify(task)['status'] == 'incomplete'
    assert store.load(task)['failures'] == {}


def test_secret_values_are_redacted_from_receipt(task, monkeypatch):
    monkeypatch.setenv('TRAILBUN_TEST_SECRET', 'sensitive-test-marker')
    contract = store.load(task)['contract']
    contract['checks'][0]['argv'] = [sys.executable, '-c', "import os; print(os.environ['TRAILBUN_TEST_SECRET'])"]
    engine.amend(task, contract, 'Exercise redaction')
    assert verify(task)['checks'][0]['output'].strip() == '[REDACTED]'


def test_post_check_inspection_failure_retains_executed_evidence(task, monkeypatch):
    from trailbun import git
    contract = store.load(task)['contract']
    contract['checks'][0]['argv'] = [sys.executable, '-c', "from pathlib import Path; Path('answer.txt').write_text('uninspectable'); print('check did run')"]
    engine.amend(task, contract, 'Retain evidence when artifact inspection fails')
    original = git.artifact
    def inspect(root, *args):
        if (root / 'answer.txt').read_text() == 'uninspectable':
            raise RuntimeError('Unsupported generated artifact')
        return original(root, *args)
    monkeypatch.setattr(git, 'artifact', inspect)
    result = verify(task)
    assert result['status'] == 'incomplete'
    assert result['artifact_after'] is None
    assert 'check did run' in result['checks'][0]['output']
    assert store.load(task)['receipts'][-1]['status'] == 'incomplete'
