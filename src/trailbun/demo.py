"""A deterministic demonstration, never presented as an agent benchmark."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import engine
from .verify import verify


def demo(output: Path | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix='trailbun-demo-') as directory:
        root = Path(directory)
        def git(*args):
            subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
        git('init', '-q')
        git('config', 'user.name', 'Trailbun Demo')
        git('config', 'user.email', 'demo@example.invalid')
        (root / 'redirect.txt').write_text('/broken', encoding='utf-8')
        git('add', '.')
        git('commit', '-qm', 'Reproducible broken redirect')
        contract = {'goal': 'Fix the expired-session redirect', 'exclusions': ['Do not redesign authentication'],
                    'allowed_paths': ['redirect.txt'], 'checks': [{'id': 'redirect', 'argv': [sys.executable,
                    '-c', "from pathlib import Path; assert Path('redirect.txt').read_text() == '/login'"]}]}
        steps = [dict(event='save-task', **engine.start(root, contract))]
        (root / 'new-auth-framework.txt').write_text('An unnecessary detour', encoding='utf-8')
        steps.append(dict(event='detect-detour', **engine.check(root)))
        # The fixture deliberately owns this exact temporary file.
        (root / 'new-auth-framework.txt').unlink()
        engine.checkpoint(root, {'summary': 'Found the redirect bug; discarded architecture detour.',
                                'next_action': 'Change redirect.txt to /login',
                                'failed_hypotheses': ['A new authentication framework is unnecessary.']})
        steps.append(dict(event='restore-task', **engine.resume(root)))
        (root / 'redirect.txt').write_text('/login', encoding='utf-8')
        steps.append(dict(event='verify-result', **verify(root)))
        report = {'schema_version': 1, 'status': steps[-1]['status'],
                  'kind': 'deterministic-demonstration', 'agent_run': False, 'steps': steps}
        if output:
            output.mkdir(parents=True, exist_ok=True)
            with (output / 'demo.json').open('x', encoding='utf-8') as file:
                json.dump(report, file, indent=2)
        return report
