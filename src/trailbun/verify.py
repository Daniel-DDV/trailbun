"""Execute contracted checks; evidence belongs to an artifact, not a promise."""

from __future__ import annotations

import os
import json
import platform
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__, contracts, engine, git, store


def _redact(text: str) -> str:
    for name, value in os.environ.items():
        if len(value) >= 8 and re.search(r'TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL', name, re.I):
            text = text.replace(value, '[REDACTED]')
    return re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[REDACTED]', text)


def _run(root: Path, check: dict) -> dict:
    started = time.monotonic()
    result = {'id': check['id'], 'argv': [_redact(x) for x in check['argv']],
              'exit_code': None, 'status': 'incomplete'}
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.run(check['argv'], cwd=root, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, shell=False,
                                     timeout=check.get('timeout_seconds', 60))
            result.update(exit_code=process.returncode,
                          status='ok' if process.returncode == 0 else 'violation')
        except (OSError, subprocess.TimeoutExpired) as exc:
            result['error'] = _redact(str(exc))
        size = output.tell()
        output.seek(0)
        result['output'] = _redact(output.read(16384).decode('utf-8', errors='replace'))
        result['output_truncated'] = size > 16384
    result['duration_seconds'] = round(time.monotonic() - started, 4)
    return result


def verify(root: Path, baseline: bool = False) -> dict:
    root = git.repo_root(root)
    assessment = engine.check(root)
    if assessment['status'] != 'ok':
        return assessment
    with store.locked(root) as state:
        before = git.artifact(root, state['contract'].get('watch_ignored', []))
        assessment = engine.check(root)
        if assessment['status'] != 'ok':
            return assessment
        expected = state['contract'].get('expected_red', [])
        if baseline and (not expected or state.get('baseline_recorded') or
                         before['fingerprint'] != state['initial_fingerprint']):
            raise ValueError('Expected-red baseline must be declared and recorded once before editing.')
        checks = [_run(root, item) for item in state['contract']['checks']]
        inspection_error = None
        try:
            after = git.artifact(root, state['contract'].get('watch_ignored', []))
        except (RuntimeError, ValueError, OSError) as exc:
            after = None
            inspection_error = str(exc)
        status = 'ok'
        if any(item['status'] == 'violation' for item in checks):
            status = 'violation'
        if any(item['status'] == 'incomplete' for item in checks) or before != after:
            status = 'incomplete'
        receipt = {'schema_version': 1, 'id': uuid4().hex, 'run_id': state['run_id'],
                   'revision': state['revision'], 'contract_digest': contracts.digest(state['contract']),
                   'artifact_fingerprint': before['fingerprint'],
                   'artifact_before': {k: before[k] for k in ('head', 'index', 'fingerprint')},
                   'artifact_after': {k: after[k] for k in ('head', 'index', 'fingerprint')} if after else None,
                   'file_count': len(before['files']), 'status': status, 'checks': checks,
                   'baseline': baseline, 'timestamp': datetime.now(timezone.utc).isoformat(),
                   'environment': {'trailbun': __version__, 'python': platform.python_version(),
                                   'platform': platform.platform()}}
        if inspection_error:
            receipt['error'] = _redact(inspection_error)
        if baseline:
            actual = {item['id'] for item in checks if item['status'] == 'violation'}
            if actual != set(expected) or status == 'incomplete':
                receipt['status'] = 'incomplete'
                receipt['error'] = 'Observed baseline failures do not match declared expected_red checks.'
            else:
                state['baseline_recorded'] = True
                receipt['expected_red_observed'] = True
        elif status != 'incomplete':
            for item in checks:
                failure = state['failures'].setdefault(item['id'], {'fingerprints': [], 'count': 0})
                if item['status'] == 'ok':
                    failure.update(fingerprints=[], count=0)
                elif before['fingerprint'] not in failure['fingerprints']:
                    failure['fingerprints'].append(before['fingerprint'])
                    failure['count'] += 1
            state['needs_diagnosis'] = any(f['count'] >= 2 for f in state['failures'].values())
        receipt['needs_diagnosis'] = state.get('needs_diagnosis', False)
        location = store.directory(root) / 'receipts'
        location.mkdir(exist_ok=True)
        path = location / (receipt['id'] + '.json')
        temporary = path.with_suffix('.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as file:
                json.dump(receipt, file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        summary = {key: receipt[key] for key in ('id', 'run_id', 'revision', 'contract_digest',
                    'artifact_fingerprint', 'status', 'baseline', 'timestamp')}
        summary['path'] = str(path)
        state['receipts'].append(summary)
        receipt['receipt_path'] = str(path)
        return receipt
