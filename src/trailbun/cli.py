"""Small, scriptable entry point. Hook output is always native host JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='trailbun', description='Keep your agent on the trail.')
    parser.add_argument('--version', action='version', version=f'Trailbun {__version__}')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('start', 'amend', 'checkpoint', 'resume', 'check', 'verify', 'diagnose',
                 'doctor', 'setup', 'uninstall', 'demo', 'hook'):
        command = commands.add_parser(name)
        command.add_argument('--project', type=Path, default=Path.cwd())
        command.add_argument('--json', action='store_true')
        if name in ('start', 'amend'):
            command.add_argument('--contract', required=True, help='JSON file, or - for stdin')
        if name == 'start':
            command.add_argument('--abandon-reason')
        if name == 'amend':
            command.add_argument('--reason', required=True)
        if name in ('start', 'resume', 'doctor', 'setup', 'uninstall', 'hook'):
            command.add_argument('--host', choices=['claude', 'codex'],
                                 required=name in ('doctor', 'setup', 'uninstall', 'hook'))
        if name in ('start', 'resume'):
            command.add_argument('--session', help='Native session ID printed by the session hook')
        if name == 'checkpoint':
            command.add_argument('--summary', required=True)
            command.add_argument('--next-action', required=True)
            command.add_argument('--failed-hypothesis', action='append', default=[])
        if name in ('checkpoint', 'resume'):
            command.add_argument('--export', type=Path)
        if name == 'verify':
            command.add_argument('--baseline', action='store_true')
        if name == 'diagnose':
            for field in ('reproduction', 'cause', 'evidence', 'next-action'):
                command.add_argument('--' + field, required=True)
        if name == 'demo':
            command.add_argument('--output', type=Path)
    return parser


def _execute(args: argparse.Namespace) -> dict:
    from . import engine
    name, root = args.command, args.project
    if name in ('start', 'resume') and bool(args.host) != bool(args.session):
        raise ValueError('Pass both --host and --session to bind the native session.')
    if name in ('start', 'resume') and args.session and (len(args.session) > 256 or not args.session.strip() or '\0' in args.session):
        raise ValueError('Session ID must contain 1 to 256 nonempty characters without NUL.')
    if name in ('start', 'amend'):
        text = sys.stdin.read() if args.contract == '-' else Path(args.contract).read_text(encoding='utf-8-sig')
        contract = json.loads(text)
        result = (engine.start(root, contract, abandon_reason=args.abandon_reason) if name == 'start' else
                  engine.amend(root, contract, args.reason))
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
    else:
        from . import integration
        result = getattr(integration, name)(root, args.host)
    if name in ('start', 'resume') and (args.host or args.session):
        from .hooks import bind
        if result.get('run_id'):
            bind(root, args.host, args.session)
    if getattr(args, 'export', None):
        with args.export.open('x', encoding='utf-8') as exported:
            exported.write(result.get('context', json.dumps(result, indent=2)) + '\n')
    return result


def main(argv: list[str] | None = None) -> int:
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
        except (ValueError, RuntimeError, OSError) as exc:
            result = hooks.error_response(args.host, payload.get('hook_event_name', ''), str(exc))
        print(json.dumps(result))
        return 0
    try:
        result = _execute(args)
    except (ValueError, RuntimeError, OSError) as exc:
        result = {'schema_version': 1, 'status': 'incomplete', 'error': str(exc)}
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"Trailbun | {result['status'].upper()}")
        if 'context' in result:
            print(result['context'])
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2))
    return {'ok': 0, 'violation': 1, 'incomplete': 2}[result['status']]
