"""Execute contracted checks; evidence belongs to an artifact, not a promise."""

from __future__ import annotations

import hashlib
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

OUTPUT_LIMIT = 16384
REDACTION_SCAN_LIMIT = 4 * 1024 * 1024
ENV_NAME = re.compile(r'TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|CREDENTIAL|PRIVATE_KEY|AUTH|COOKIE|SESSION', re.I)
PATTERNS = [
    (re.compile(r'(?i)(bearer\s+)[\w.\-]+'), r'\1[REDACTED]'),
    (re.compile(r'(?i)(basic\s+)[A-Za-z0-9+/=]{16,}'), r'\1[REDACTED]'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '[REDACTED]'),
    (re.compile(r'\b(?:sk|rk)-(?:proj-|ant-|live-|test-)?[A-Za-z0-9_\-]{16,}'), '[REDACTED]'),
    (re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b'), '[REDACTED]'),
    (re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}\b'), '[REDACTED]'),
    (re.compile(r'\bxox[abposr]-[A-Za-z0-9\-]{10,}'), '[REDACTED]'),
    (re.compile(r'\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b'), '[REDACTED]'),
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.S), '[REDACTED]'),
    (re.compile(r'(?i)\b([a-z][a-z0-9+.\-]*://)([^/\s:@]+):([^@\s/]+)@'), r'\1[REDACTED]@'),
]


def _path_replacements(root: Path | None) -> list[tuple[str, str]]:
    replacements = {}
    if root is not None:
        replacements[str(root)] = '<REPO>'
    try:
        replacements[str(Path.home())] = '<HOME>'
    except (RuntimeError, OSError):
        pass
    return sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True)


def _redact(text: str, root: Path | None = None) -> str:
    for name, value in os.environ.items():
        if len(value) >= 8 and ENV_NAME.search(name):
            text = text.replace(value, '[REDACTED]')
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    for value, replacement in _path_replacements(root):
        if len(value) < 4:
            continue
        for variant in (value, value.replace('\\', '\\\\'), value.replace('\\', '/')):
            text = text.replace(variant, replacement)
    return text


def _resolve(argv: list[str]) -> str | None:
    try:
        return git.executable(argv[0])
    except OSError:
        return None


def _run(root: Path, check: dict) -> dict:
    started = time.monotonic()
    result = {'id': check['id'], 'argv': [_redact(x, root) for x in check['argv']],
              'exit_code': None, 'status': 'incomplete'}
    resolved = _resolve(check['argv'])
    result['resolved_executable'] = _redact(resolved, root) if resolved else None
    argv = list(check['argv'])
    if resolved:
        argv[0] = resolved
        # Windows .cmd and .bat shims are batch scripts; CreateProcess needs cmd.exe to run them.
        if os.name == 'nt' and resolved.lower().endswith(('.cmd', '.bat')):
            argv = [os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'cmd.exe'), '/d', '/c', *argv]
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, shell=False,
                                     timeout=check.get('timeout_seconds', 60))
            result.update(exit_code=process.returncode,
                          status='ok' if process.returncode == 0 else 'violation')
        except (OSError, subprocess.TimeoutExpired) as exc:
            result['error'] = _redact(str(exc), root)
        size = output.tell()
        output.seek(0)
        # Redact before truncating so a secret cut at the boundary cannot survive in the retained prefix.
        text = _redact(output.read(REDACTION_SCAN_LIMIT).decode('utf-8', errors='replace'), root)
        result['output'] = text[:OUTPUT_LIMIT]
        result['output_truncated'] = size > OUTPUT_LIMIT or len(text) > OUTPUT_LIMIT
    result['duration_seconds'] = round(time.monotonic() - started, 4)
    return result


def _changed_during_checks(before: dict, after: dict | None) -> list[str]:
    if after is None:
        return []
    names = set(before['files']) | set(after['files'])
    changed = sorted(name for name in names if before['files'].get(name) != after['files'].get(name))
    if before['head'] != after['head']:
        changed.append('HEAD')
    if before['index'] != after['index']:
        changed.append('<index>')
    return changed


def verify(root: Path, baseline: bool = False) -> dict:
    root = git.repo_root(root)
    with store.locked(root, existing=True) as state:
        engine._active(state)
        before = git.artifact(root, state['contract'].get('watch_ignored', []))
        assessment = engine._report(root, state, before)
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
        changed_during = _changed_during_checks(before, after)
        if any(item['status'] == 'incomplete' for item in checks) or before != after:
            status = 'incomplete'
        receipt = {'schema_version': 1, 'id': uuid4().hex, 'run_id': state['run_id'],
                   'revision': state['revision'], 'contract_digest': contracts.digest(state['contract']),
                   'artifact_fingerprint': before['fingerprint'],
                   'content_fingerprint': before.get('content_fingerprint'),
                   'artifact_before': {k: before[k] for k in ('head', 'index', 'fingerprint')},
                   'artifact_after': {k: after[k] for k in ('head', 'index', 'fingerprint')} if after else None,
                   'changed_during_checks': changed_during,
                   'file_count': len(before['files']), 'status': status, 'checks': checks,
                   'baseline': baseline, 'timestamp': datetime.now(timezone.utc).isoformat(),
                   'environment': {'trailbun': __version__, 'python': platform.python_version(),
                                   'platform': platform.platform()}}
        if inspection_error:
            receipt['error'] = _redact(inspection_error, root)
        if baseline:
            actual = {item['id'] for item in checks if item['status'] == 'violation'}
            if actual != set(expected) or status == 'incomplete':
                receipt['status'] = 'incomplete'
                receipt['error'] = 'Observed baseline failures do not match declared expected_red checks.'
            else:
                state['baseline_recorded'] = True
                receipt['expected_red_observed'] = True
        elif status != 'incomplete':
            # The counter keys on file contents only, so staging or committing a failed
            # correction is the same attempt, not a second one.
            key = before.get('content_fingerprint') or before['fingerprint']
            for item in checks:
                failure = state['failures'].setdefault(item['id'], {'fingerprints': [], 'count': 0})
                if item['status'] == 'ok':
                    failure.update(fingerprints=[], count=0)
                elif key not in failure['fingerprints']:
                    failure['fingerprints'].append(key)
                    failure['count'] += 1
            state['needs_diagnosis'] = any(f['count'] >= 2 for f in state['failures'].values())
        receipt['needs_diagnosis'] = state.get('needs_diagnosis', False)
        location = store.directory(root) / 'receipts'
        location.mkdir(exist_ok=True)
        path = location / (receipt['id'] + '.json')
        encoded = json.dumps(receipt, indent=2)
        receipt_digest = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
        temporary = path.with_suffix('.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as file:
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        summary = {key: receipt[key] for key in ('id', 'run_id', 'revision', 'contract_digest',
                    'artifact_fingerprint', 'status', 'baseline', 'timestamp')}
        summary['path'] = str(path)
        summary['sha256'] = receipt_digest
        state['receipts'].append(summary)
        receipt['receipt_path'] = _redact(str(path), root)
        receipt['sha256'] = receipt_digest
        return receipt
