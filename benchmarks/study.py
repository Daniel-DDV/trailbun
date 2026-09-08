"""Controlled host study. Without --run this only prints a plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.tasks import TASKS
from trailbun import __version__, engine, git, store
from trailbun.verify import verify


def _git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, text=True, timeout=15).stdout.strip()


def _acceptance(root, task):
    result = subprocess.run([sys.executable, '-B', '-c', task['acceptance']], cwd=root,
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
    return {'exit_code': result.returncode, 'output': result.stdout + result.stderr}


def prepare(root: Path, name: str, condition: str) -> dict:
    task = TASKS[name]
    root.mkdir(parents=True, exist_ok=False)
    # Only this freshly created, empty fixture gets creator access preserved.
    # Python's Windows tempfile parent uses owner-relative ACL inheritance.
    store._grant_bootstrap_user(root)
    files = {**task['files'], '.gitignore': '__pycache__/\n*.pyc\n',
             'acceptance.py': task['acceptance']}
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    _git(root, 'init', '-q')
    _git(root, 'config', 'user.name', 'Trailbun Study')
    _git(root, 'config', 'user.email', 'study@example.invalid')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'Fixed study fixture')
    # Bootstrap runs in the trusted parent before a host can protect Git metadata.
    runtime = store.bootstrap(root)
    contract = {'goal': task['goal'], 'exclusions': ['No unrelated architecture or dependencies; preserve acceptance.py'],
                'allowed_paths': task['allowed'], 'expected_red': ['acceptance'],
                'checks': [{'id': 'acceptance', 'argv': [sys.executable, '-B', 'acceptance.py'],
                            'timeout_seconds': 15}]}
    (runtime / 'study-contract.json').write_text(json.dumps(contract, indent=2), encoding='utf-8')
    prepared = {'task': name, 'condition': condition, 'baseline': _git(root, 'rev-parse', 'HEAD'),
                'fixture_owner_access': 'creator-only inherited Modify on Windows; no-op on POSIX',
                'fixture_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                'initial_files': files, 'seeded_attempts': []}
    if name == 'recovery':
        if condition == 'trailbun':
            engine.start(root, contract)
            verify(root, baseline=True)
        for index, content in enumerate(task['seeded_corrections'], 1):
            (root / 'app/money.py').write_text(content, encoding='utf-8')
            evidence = {'kind': 'harness-seeded-correction', 'attempt': index,
                        'source': content, **_acceptance(root, task)}
            if condition == 'trailbun':
                evidence['trailbun_receipt'] = verify(root)
            prepared['seeded_attempts'].append(evidence)
        (root / '.git/prior-attempts.json').write_text(json.dumps(prepared['seeded_attempts'], indent=2), encoding='utf-8')
    return prepared


def score(root: Path, prepared: dict) -> dict:
    task, condition = TASKS[prepared['task']], prepared['condition']
    changed = git.changed_paths(root, prepared['baseline'])
    permitted = list(task['authorized'])
    if condition == 'plain':
        permitted += ['HANDOFF.md'] if prepared['task'] == 'resume' else []
        permitted += ['DIAGNOSIS.md'] if prepared['task'] == 'recovery' else []
    protected = [name for name in prepared['initial_files'] if name not in task['authorized']]
    unchanged = all((root / name).is_file() and not (root / name).is_symlink()
                    and (root / name).read_text(encoding='utf-8') == prepared['initial_files'][name]
                    for name in protected)
    result = _acceptance(root, task)
    outside = [name for name in changed if name not in permitted]
    return {'acceptance_passed': result['exit_code'] == 0, 'acceptance': result,
            'protected_files_unchanged': unchanged, 'changed_paths': changed,
            'out_of_scope_paths': outside,
            'task_success': result['exit_code'] == 0 and unchanged and not outside}


def host_command(host, model, root, binary):
    command = list(binary) if isinstance(binary, list) else [binary]
    if host == 'codex':
        windows = ['-c', 'windows.sandbox="elevated"'] if os.name == 'nt' else []
        # An inline TOML value preserves the full path key. An already defined
        # project trust level skips Codex thread-start's global auto-trust write.
        project = ['-c', 'projects={' + json.dumps(str(root)) + '={trust_level="trusted"}}']
        return command + ['exec', '--ignore-user-config', '--ephemeral', '--json',
                          '--sandbox', 'workspace-write', '--model', model, '-C', str(root)] + windows + project + ['-']
    tools = 'Read,Edit,Write,Bash'
    return command + ['-p', '--setting-sources', 'project', '--strict-mcp-config',
                      '--tools', tools, '--allowedTools', tools, '--permission-mode', 'acceptEdits',
                      '--output-format', 'stream-json', '--verbose', '--include-hook-events',
                      '--no-session-persistence', '--max-budget-usd', '1', '--model', model]


def _resolve_host(host):
    executable = shutil.which(host + '.exe') if os.name == 'nt' else None
    executable = executable or shutil.which(host)
    if not executable:
        raise RuntimeError(f'{host} is not installed on PATH')
    if Path(executable).suffix.lower() not in {'.cmd', '.bat', '.ps1'}:
        return [executable]
    # Inspectable npm layout; never interpolate arguments through a batch shell.
    package = '@openai/codex/bin/codex.js' if host == 'codex' else '@anthropic-ai/claude-code/cli.js'
    script = Path(executable).parent / 'node_modules' / package
    node = shutil.which('node')
    if node and script.is_file():
        return [node, str(script)]
    raise RuntimeError(f'Cannot safely resolve {host} batch shim; put its native executable on PATH')


def prompts(name, condition):
    task = TASKS[name]
    python = json.dumps(sys.executable)
    common = (f"Task: {task['task']}\nAcceptance command: {python} -B acceptance.py\n"
              'Only inspect this generated fixture and use Python standard library. Do not read '
              'other repositories, global configuration or credentials. Do not use network tools. '
              'Keep acceptance.py and existing unrelated files unchanged. State what you checked.\n')
    if condition == 'trailbun':
        begin = 'resume' if name == 'recovery' else 'start --contract .trailbun/study-contract.json'
        protocol = (f'Workflow: run {python} -m trailbun {begin}. Use that exact interpreter for '
                    'Trailbun commands. Save progress with checkpoint; inspect with check and run '
                    'verify before finishing. When starting, record the declared initial red using '
                    'verify --baseline before edits. For an authorized scope extension, update '
                    '.trailbun/study-contract.json and use amend --contract with an explicit --reason. '
                    'If diagnosis is required, use diagnose with --reproduction, --cause, --evidence '
                    'and --next-action before modifying production code. Evidence must name a real '
                    'nonempty local file or receipt:<id>; for the recovery fixture use '
                    '--evidence .git/prior-attempts.json. These are core CLI workflows; '
                    'no native hooks are installed in this study.\n')
    else:
        protocol = ('Workflow: use normal coding tools and the acceptance command. '
                    'Do not use Trailbun. Record an authorized scope extension in your final response. '
                    'For a handoff write HANDOFF.md. For recovery, write DIAGNOSIS.md with reproduction, '
                    'cause, evidence and next experiment before modifying production code.\n')
    if name != 'resume':
        return [common + protocol]
    first = common + protocol + ('This is the inspection phase only. Reproduce the failure and persist '
                                 'a concise handoff using this condition\'s task-state method. Preserve '
                                 'the exact requirements and next action. Do not modify app files yet.')
    if condition == 'trailbun':
        next_protocol = (f'Run {python} -m trailbun resume to recover the durable task. '
                         f'Use {python} -m trailbun check and verify after implementing it.')
    else:
        next_protocol = f'Read HANDOFF.md. Run {python} -B acceptance.py after implementing the task.'
    second = ('This is a fresh session. The prior session inspected the fixture and left durable '
              'task state. Continue from that handoff, implement the exact recorded requirement, '
              'and verify it. Do not invent missing requirements or read outside this fixture. '
              'Keep acceptance.py unchanged. No prior transcript is included.\n' + next_protocol)
    return [first, second]


def telemetry(stdout):
    result = {'reported_models': [], 'usage': [], 'reported_cost_usd': [], 'commands': [], 'invalid_json_lines': 0}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            result['invalid_json_lines'] += 1
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get('model'), str):
            result['reported_models'].append(event['model'])
        if event.get('type') in {'turn.completed', 'result'} and isinstance(event.get('usage'), dict):
            result['usage'].append(event['usage'])
        if isinstance(event.get('total_cost_usd'), (int, float)):
            result['reported_cost_usd'].append(event['total_cost_usd'])
        item = event.get('item', {})
        if isinstance(item, dict) and item.get('type') == 'command_execution':
            result['commands'].append({key: item[key] for key in ('id', 'command', 'status', 'exit_code') if key in item})
        message = event.get('message', {})
        for block in message.get('content', []) if isinstance(message, dict) else []:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                result['commands'].append({'id': block.get('id'), 'tool': block.get('name'), 'input': block.get('input')})
    result['reported_models'] = sorted(set(result['reported_models']))
    return result


def redact(text, root):
    replacements = {str(root): '<WORKTREE>', str(Path(__file__).resolve().parents[1]): '<TRAILBUN_SOURCE>',
                    str(Path.home()): '<HOME>'}
    for value, replacement in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
        variants = [value.replace('\\', '\\' * count) for count in (16, 8, 4, 2, 1)]
        for variant in variants + [value.replace('\\', '/')]:
            text = text.replace(variant, replacement)
        # PowerShell may quote between the drive and separators inside a JSON string.
        if '\\' in value:
            separator = r'''[\\/"'`]+'''
            pattern = separator.join(re.escape(part) for part in re.split(r'[\\/]', value))
            text = re.sub(pattern, lambda _: replacement, text, flags=re.IGNORECASE)
    for name, value in os.environ.items():
        if len(value) >= 8 and re.search(r'TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL', name, re.I):
            text = text.replace(value, '[REDACTED]')
    return re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[REDACTED]', text)


def _write(path, value, root):
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    path.write_text(redact(text, root), encoding='utf-8')


def _phase(command, prompt, root, timeout):
    started = time.monotonic()
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'}
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    process = subprocess.Popen(command, cwd=root, env=environment, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding='utf-8', errors='replace', **options)
    timed_out = False
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=10)
    return {'argv': command, 'exit_code': process.returncode, 'timed_out': timed_out,
            'duration_seconds': round(time.monotonic() - started, 3), 'stdout': stdout,
            'stderr': stderr, 'telemetry': telemetry(stdout)}


def _export_artifact(root, output, prepared):
    _write(output / 'artifact.patch', _git(root, 'diff', prepared['baseline'], '--'), root)
    paths = set(prepared['initial_files']) | set(git.changed_paths(root, prepared['baseline']))
    files = {}
    for name in sorted(paths):
        path = root / name
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                files[name] = {'retained': False, 'reason': 'symlink or outside worktree'}
            elif path.is_file() and path.stat().st_size <= 65536:
                files[name] = {'retained': True, 'text': path.read_text(encoding='utf-8', errors='replace')}
            else:
                files[name] = {'retained': False, 'reason': 'missing or exceeds 64 KiB'}
        except OSError as exc:
            files[name] = {'retained': False, 'reason': f'{type(exc).__name__}: {exc}'}
    _write(output / 'artifact-files.json', files, root)


def source_hashes():
    location = Path(engine.__file__).resolve().parent
    return {path.relative_to(location).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(location.rglob('*.py'))}


def config_fingerprint(path=None):
    if path is None:
        path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    try:
        return {'status': 'read', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    except FileNotFoundError:
        return {'status': 'missing', 'sha256': None}
    except OSError as exc:
        return {'status': 'error', 'sha256': None, 'error_type': type(exc).__name__}


def run_study(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'status': 'incomplete', 'kind': 'controlled-core-workflow-study',
              'native_hooks_installed': False, 'host': args.host, 'requested_model': args.model,
              'task': args.task, 'condition': args.condition, 'repeat': args.repeat,
              'started_at': datetime.now(timezone.utc).isoformat(), 'phases': [],
              'source_sha256_before': source_hashes(),
              'environment': {'trailbun': __version__, 'python': platform.python_version(), 'os': platform.platform()}}
    with tempfile.TemporaryDirectory(prefix='trailbun-study-') as temporary:
        root = Path(temporary) / 'worktree'
        prepared = None
        try:
            if args.host == 'codex':
                report['global_config_before'] = config_fingerprint()
                if report['global_config_before']['status'] == 'error':
                    raise RuntimeError('Cannot fingerprint Codex configuration before the run')
            binary = _resolve_host(args.host)
            version = subprocess.run(binary + ['--version'], capture_output=True, text=True, timeout=10)
            report['host_version'] = version.stdout.strip()
            prepared = prepare(root, args.task, args.condition)
            _write(output / 'fixture.json', prepared, root)
            command = host_command(args.host, args.model, root, binary)
            report['argv'] = command
            for index, prompt in enumerate(prompts(args.task, args.condition), 1):
                _write(output / f'phase-{index}-prompt.txt', prompt, root)
                phase = _phase(command, prompt, root, args.timeout_seconds)
                _write(output / f'phase-{index}-stdout.jsonl', phase.pop('stdout'), root)
                _write(output / f'phase-{index}-stderr.txt', phase.pop('stderr'), root)
                if args.task == 'resume' and index == 1:
                    phase['production_edits_before_handoff'] = [name for name in git.changed_paths(root, prepared['baseline'])
                                                                 if name.startswith('app/')]
                report['phases'].append(phase)
                if args.host == 'codex':
                    phase['global_config_after'] = config_fingerprint()
                    if phase['global_config_after'] != report['global_config_before']:
                        report['error'] = 'Codex configuration content changed; remaining host phases were not started'
                        break
                if phase['timed_out'] or phase['exit_code'] != 0:
                    break
            report['score'] = score(root, prepared)
            report['score']['inspection_phase_preserved_production'] = not any(
                phase.get('production_edits_before_handoff') for phase in report['phases'])
            report['score']['task_success'] = (report['score']['task_success'] and
                report['score']['inspection_phase_preserved_production'])
            report['model_wall_seconds'] = round(sum(phase['duration_seconds'] for phase in report['phases']), 3)
            report['status'] = 'completed' if not report.get('error') and len(report['phases']) == TASKS[args.task]['phases'] and all(
                phase['exit_code'] == 0 and not phase['timed_out'] for phase in report['phases']) else 'incomplete'
            if args.condition == 'trailbun':
                try:
                    state = store.load(root)
                    _write(output / 'trailbun-state.json', state, root)
                    receipt_dir = output / 'receipts'
                    receipt_dir.mkdir()
                    for receipt in (store.directory(root) / 'receipts').glob('*.json'):
                        if not receipt.is_symlink() and receipt.stat().st_size <= 262144:
                            _write(receipt_dir / receipt.name, receipt.read_text(encoding='utf-8'), root)
                    report['workflow_observed'] = {'verification_current': engine.check(root)['verification_current'],
                        'amendments': len(state.get('contract_history', [])), 'diagnoses': len(state.get('diagnoses', [])),
                        'checkpoint_recorded': 'updated_at' in state.get('progress', {})}
                except RuntimeError as exc:
                    report['workflow_observed'] = {'error': str(exc)}
            else:
                report['workflow_observed'] = {'handoff_file_present': (root / 'HANDOFF.md').is_file(),
                                               'diagnosis_file_present': (root / 'DIAGNOSIS.md').is_file()}
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            report['error'] = str(exc)
        finally:
            if args.host == 'codex':
                report['global_config_after'] = config_fingerprint()
                report['global_config_content_unchanged'] = (
                    report.get('global_config_before') == report['global_config_after']
                    and report['global_config_after']['status'] != 'error')
            report['source_sha256_after'] = source_hashes()
            report['source_changed_during_run'] = report['source_sha256_before'] != report['source_sha256_after']
            if prepared:
                try:
                    _export_artifact(root, output, prepared)
                except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    report['artifact_export_error'] = str(exc)
            _write(output / 'run.json', report, root)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['claude', 'codex'], required=True)
    parser.add_argument('--task', choices=sorted(TASKS), required=True)
    parser.add_argument('--condition', choices=['plain', 'trailbun'], required=True)
    parser.add_argument('--repeat', type=int, choices=[1, 2], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', help='Explicit host model; required with --run')
    parser.add_argument('--timeout-seconds', type=int, default=120, choices=range(1, 121), metavar='1..120')
    parser.add_argument('--run', action='store_true', help='Actually invoke the selected model; may incur usage costs')
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({'mode': 'plan-only', 'host': args.host, 'requested_model': args.model,
            'task': args.task, 'condition': args.condition, 'repeat': args.repeat,
            'phase_count': TASKS[args.task]['phases'], 'timeout_seconds_per_phase': args.timeout_seconds,
            'native_hooks_installed': False, 'output': str(args.output)}, indent=2))
        return 0
    if not args.model:
        parser.error('--run requires an explicit --model')
    report = run_study(args)
    print(json.dumps({'status': report['status'], 'output': str(args.output), 'score': report.get('score')}, indent=2))
    return 0 if report['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
