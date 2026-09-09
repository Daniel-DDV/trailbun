"""Small, scriptable entry point. Hook output is always native host JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__

CONTRACT_EXAMPLE = """\
Contract (JSON object):
  {
    "goal": "Redirect signed-out users to /login",
    "exclusions": ["No new authentication framework"],
    "allowed_paths": ["src/redirect.py", "tests/test_redirect.py"],
    "checks": [{"id": "redirect", "argv": ["python", "-m", "pytest", "tests/test_redirect.py", "-q"],
                "timeout_seconds": 60}],
    "expected_red": [],
    "watch_ignored": []
  }
Fields: goal (required text); allowed_paths (required, repository-relative files or
directories, no wildcards, "." for the whole tree); checks (1 to 32 entries with a
simple unique id, an argv array run without a shell, optional timeout 1 to 600 s);
exclusions, expected_red and watch_ignored are optional.
Location: write it to .trailbun/task.json after setup or start has created the
runtime, or pass it on stdin with --contract -. Any other untracked file in the
repository blocks start and later counts as drift.
Exit codes: 0 ok, 1 violation, 2 incomplete or error."""

DESCRIPTIONS = {
    "start": "Record a new task: goal, allowed paths and acceptance checks, from a clean worktree.",
    "amend": "Replace the contract of the active task, recording the reason and the previous revision.",
    "checkpoint": "Save progress, the next action and disproven hypotheses for a later session.",
    "resume": "Print the saved task context and, with --host and --session, bind this native session.",
    "check": "Compare the worktree with the task baseline and report paths outside the allowed scope.",
    "verify": "Run every contracted check and write a receipt bound to the current file contents.",
    "diagnose": "Record a diagnosis with evidence after two distinct failed corrections of one check.",
    "doctor": "Report whether the host integration is installed, invoked, disabled or drifted.",
    "setup": "Install project-local hooks and skills for one host, reversibly.",
    "uninstall": "Remove the hooks, skills and exclude entries that setup recorded for one host.",
    "demo": "Replay an isolated, deterministic demonstration in a temporary Git repository.",
    "hook": "Host-invoked adapter: read one hook payload on stdin and print the host's JSON reply.",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='trailbun', description='Keep your agent on the trail: task contracts, '
                                     'scope checks and verification receipts for coding agents.')
    parser.add_argument('--version', action='version', version=f'Trailbun {__version__}')
    commands = parser.add_subparsers(dest='command', required=True, metavar='command')
    for name, description in DESCRIPTIONS.items():
        epilog = CONTRACT_EXAMPLE if name in ('start', 'amend') else None
        command = commands.add_parser(name, help=description, description=description, epilog=epilog,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
        command.add_argument('--project', type=Path, default=Path.cwd(),
                             help='Any directory inside the Git worktree (default: current directory)')
        if name != 'hook':
            command.add_argument('--json', action='store_true', help='Print the full JSON result instead of text')
        if name in ('start', 'amend'):
            command.add_argument('--contract', required=True, help='Path to the contract JSON file, or - for stdin')
        if name == 'start':
            command.add_argument('--abandon-reason', help='Archive an incomplete active task with this reason first')
        if name == 'amend':
            command.add_argument('--reason', required=True, help='Why the contract changes; recorded in the history')
            command.add_argument('--rebaseline', action='store_true',
                                 help='Record HEAD as the new baseline after the recorded commit was rewritten')
        if name in ('start', 'resume', 'doctor', 'setup', 'uninstall', 'hook'):
            command.add_argument('--host', choices=['claude', 'codex'],
                                 required=name in ('doctor', 'setup', 'uninstall', 'hook'),
                                 help='Native host' + (' (with --session, bind this session)' if name in ('start', 'resume') else ''))
        if name in ('start', 'resume'):
            command.add_argument('--session', help='Native session ID printed by the SessionStart hook')
        if name == 'checkpoint':
            command.add_argument('--summary', required=True, help='What is known now')
            command.add_argument('--next-action', required=True, help='The single next step')
            command.add_argument('--failed-hypothesis', action='append', default=[],
                                 help='A disproven hypothesis; repeatable')
        if name in ('checkpoint', 'resume'):
            command.add_argument('--export', type=Path, help='Write the resume context to this new file')
        if name == 'verify':
            command.add_argument('--baseline', action='store_true',
                                 help='Record the declared expected_red failures once before editing')
        if name == 'diagnose':
            for field, help_text in (('reproduction', 'How the failure is reproduced'),
                                     ('cause', 'The investigated cause'),
                                     ('evidence', 'A nonempty local file or receipt:<id>'),
                                     ('next-action', 'The next distinguishing check')):
                command.add_argument('--' + field, required=True, help=help_text)
        if name == 'setup':
            command.add_argument('--shared', action='store_true',
                                 help='Claude only: write .claude/settings.json (committed) instead of settings.local.json')
        if name == 'doctor':
            command.add_argument('--probe', action='store_true',
                                 help='Start the installed hook command once with a synthetic SessionStart payload')
        if name == 'demo':
            command.add_argument('--output', type=Path, help='Directory that receives demo.json (must not exist yet)')
    return parser


def _read_contract(source: str) -> dict:
    try:
        text = sys.stdin.read() if source == '-' else Path(source).read_text(encoding='utf-8-sig')
    except OSError as exc:
        raise ValueError(f"Cannot read contract {source}: {exc}") from exc
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ValueError(f"Cannot read contract {source}: invalid JSON ({exc})") from exc


def _execute(args: argparse.Namespace) -> dict:
    from . import engine
    name, root = args.command, args.project
    if name in ('start', 'resume') and bool(args.host) != bool(args.session):
        raise ValueError('Pass both --host and --session to bind the native session.')
    if name in ('start', 'resume') and args.session and (len(args.session) > 256 or not args.session.strip() or '\0' in args.session):
        raise ValueError('Session ID must contain 1 to 256 nonempty characters without NUL.')
    export = getattr(args, 'export', None)
    if export is not None:
        if export.exists():
            raise ValueError(f'Export target already exists: {export}')
        if not export.parent.is_dir():
            raise ValueError(f'Export directory does not exist: {export.parent}')
    if name in ('start', 'amend'):
        contract = _read_contract(args.contract)
        result = (engine.start(root, contract, abandon_reason=args.abandon_reason) if name == 'start' else
                  engine.amend(root, contract, args.reason, rebaseline=args.rebaseline))
    elif name == 'checkpoint':
        result = engine.checkpoint(root, {'summary': args.summary, 'next_action': args.next_action,
                                          'failed_hypotheses': args.failed_hypothesis})
    elif name in ('resume', 'check'):
        result = getattr(engine, name)(root)
    elif name == 'diagnose':
        result = engine.diagnose(root, {key: getattr(args, key) for key in
                                       ('reproduction', 'cause', 'evidence', 'next_action')})
    elif name == 'verify':
        from .verify import verify
        result = verify(root, baseline=args.baseline)
    elif name == 'demo':
        from .demo import demo
        result = demo(args.output)
    elif name == 'setup':
        from . import integration
        result = integration.setup(root, args.host, shared=args.shared)
    elif name == 'doctor':
        from . import integration
        result = integration.doctor(root, args.host, run_probe=args.probe)
    else:
        from . import integration
        result = getattr(integration, name)(root, args.host)
    if name in ('start', 'resume') and (args.host or args.session):
        from .hooks import bind
        if result.get('run_id'):
            bind(root, args.host, args.session)
    if export is not None:
        with export.open('x', encoding='utf-8') as exported:
            exported.write(result.get('context', json.dumps(result, indent=2)) + '\n')
    return result


def _lines(value, limit=8):
    value = list(value)
    shown = ', '.join(value[:limit])
    return (shown + f' (+{len(value) - limit} more)') if len(value) > limit else (shown or 'none')


def render(name: str, result: dict) -> str:
    """Plain-text view of a result. JSON stays available with --json."""
    lines = [f"Trailbun | {result['status'].upper()}"]
    if 'error' in result and 'checks' not in result:
        lines.append(result['error'])
    if 'context' in result:
        lines.append(result['context'])
        return '\n'.join(lines)
    if name == 'demo':
        for step in result.get('steps', []):
            lines.append('')
            lines.extend(render(step['event'], step).splitlines())
        lines.append('')
        lines.append('Deterministic demonstration; no live model. Replay with: trailbun demo')
        return '\n'.join(lines)
    if 'checks' in result:  # verify receipt
        for item in result['checks']:
            exit_code = item.get('exit_code')
            lines.append(f"  check {item['id']}: {item['status']} (exit {exit_code}, {item.get('duration_seconds', 0)} s)")
            if item.get('error'):
                lines.append(f"    {item['error']}")
        if result.get('changed_during_checks'):
            lines.append('  changed during checks: ' + _lines(result['changed_during_checks']))
        if result.get('error') and 'checks' in result:
            lines.append('  ' + result['error'])
        lines.append(f"  receipt {result.get('id', '')[:12]} sha256 {result.get('sha256', '')[:16]}  {result.get('receipt_path', '')}")
        lines.append(f"  needs diagnosis: {result.get('needs_diagnosis', False)}")
        return '\n'.join(lines)
    if 'contract' in result:  # check / start / amend / checkpoint reports
        contract = result['contract']
        lines.append(f"  goal: {contract['goal']}")
        lines.append(f"  allowed: {_lines(contract['allowed_paths'])}")
        lines.append(f"  changed: {_lines(result.get('changed_paths', []))}")
        lines.append(f"  outside scope: {_lines(result.get('outside_allowed_paths', []))}")
        amended = result.get('amend_count', 0)
        lines.append(f"  contract: revision {result.get('revision')}, amended {amended} times since start (recorded, not enforced)")
        receipt = result.get('last_receipt')
        digest = (result.get('last_receipt_sha256') or '')[:16]
        lines.append(f"  verification: {result.get('completion')}" +
                     (f", last receipt {receipt[:12]} ({result.get('last_receipt_status')}, sha256 {digest})" if receipt else ', no receipt'))
        if result.get('needs_diagnosis'):
            lines.append('  needs diagnosis: run trailbun diagnose before the next supported edit')
        return '\n'.join(lines)
    if name == 'doctor':
        for key in ('target', 'host_version', 'configured', 'invoked', 'disabled', 'disabled_by', 'enforced'):
            lines.append(f"  {key}: {result.get(key)}")
        if result.get('probe') is not None:
            lines.append(f"  probe: handler_started={result['probe'].get('handler_started')} {result['probe'].get('detail') or ''}".rstrip())
        for item in result.get('drift', []):
            lines.append(f"  drift: {item}")
        for item in result.get('coverage', []):
            lines.append(f"  coverage: {item}")
        for item in result.get('limits', []):
            lines.append(f"  limit: {item}")
        return '\n'.join(lines)
    if name in ('setup', 'uninstall'):
        for key in ('target', 'generated_paths', 'permissions_deny', 'removed', 'preserved_conflicts', 'note'):
            if key in result:
                lines.append(f"  {key}: {result[key]}")
        for warning in result.get('warnings', []):
            lines.append(f"  warning: {warning}")
        if result.get('next'):
            lines.append('  next: ' + result['next'])
        return '\n'.join(lines)
    lines.append(json.dumps(result, ensure_ascii=True, indent=2))
    return '\n'.join(lines)


def _configure_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_streams()
    args = _parser().parse_args(argv)
    if args.command == 'hook':
        from . import hooks
        payload = {}
        try:
            value = json.load(sys.stdin)
            if not isinstance(value, dict):
                raise ValueError('Hook input must be a JSON object.')
            payload = value
            result = hooks.handle(args.project, args.host, payload)
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            result = hooks.error_response(args.host, payload.get('hook_event_name', ''), str(exc))
        print(json.dumps(result))
        return 0
    try:
        result = _execute(args)
    except (ValueError, RuntimeError, OSError) as exc:
        result = {'schema_version': 1, 'status': 'incomplete', 'error': str(exc)}
    except KeyError as exc:
        result = {'schema_version': 1, 'status': 'incomplete', 'error': f'Invalid Trailbun state: missing {exc}'}
    try:
        if args.json:
            print(json.dumps(result, ensure_ascii=True, indent=2))
        else:
            print(render(args.command, result))
    except OSError as exc:
        print(f"Trailbun | INCOMPLETE\nCannot write output: {exc}", file=sys.stderr)
        return 2
    return {'ok': 0, 'violation': 1, 'incomplete': 2}[result['status']]
