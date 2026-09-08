"""Render a 25-second terminal animation from an actual `trailbun demo` receipt.

Requires FFmpeg with drawtext and an explicitly supplied monospace font.
Source: https://ffmpeg.org/ffmpeg-filters.html#drawtext
"""

import argparse
import json
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path


def render(receipt, output, font):
    data = json.loads(receipt.read_text(encoding='utf-8'))
    if data.get('kind') != 'deterministic-demonstration' or data.get('agent_run') is not False:
        raise ValueError('Expected an actual deterministic demo receipt.')
    steps = data['steps']
    screens = [
        '$ trailbun demo\n\nKeep your agent on the trail.\n\nA small task. One avoidable detour.\nA result you can check.',
        '1 / SAVE THE TASK\n\n' + steps[0]['contract']['goal'] + '\n\nAllowed: ' + ', '.join(steps[0]['contract']['allowed_paths']) + '\n\n' + steps[0]['status'].upper(),
        '2 / CATCH THE DETOUR\n\n' + '\n'.join(steps[1]['outside_allowed_paths']) + '\n\n' + steps[1]['status'].upper() + '\nThe original task is still the task.',
        '3 / RESTORE THE TASK\n\n' + steps[2]['progress']['summary'] + '\n\nNext: ' + steps[2]['progress']['next_action'],
        '4 / VERIFY THE RESULT\n\nCheck: ' + steps[3]['checks'][0]['id'] + '\nExit code: ' + str(steps[3]['checks'][0]['exit_code']) + '\nReceipt: ' + steps[3]['id'][:16] + '\n\n' + steps[3]['status'].upper() + '\nSave the plan. Catch the detours. Verify the result.',
    ]
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='trailbun-render-') as temporary:
        root = Path(temporary)
        shutil.copyfile(font, root / 'mono.ttf')
        filters = []
        for index, screen in enumerate(screens):
            lines = [wrapped for line in screen.splitlines()
                     for wrapped in (textwrap.wrap(line, width=68) or [''])]
            if len(lines) > 10:
                raise ValueError('Demo screen exceeds available height.')
            for number, line in enumerate(lines):
                if not line:
                    continue
                filename = f'{index}-{number}.txt'
                (root / filename).write_text(line, encoding='utf-8')
                filters.append(f"drawtext=fontfile=mono.ttf:textfile={filename}:expansion=none:fontcolor=0xF4EDDE:fontsize=22:x=42:y={70+number*36}:enable='gte(t,{index*5})*lt(t,{(index+1)*5})'")
        (root / 'footer.txt').write_text('DETERMINISTIC DEMO  /  NO LIVE MODEL  /  REPLAY: trailbun demo', encoding='utf-8')
        filters.append('drawtext=fontfile=mono.ttf:textfile=footer.txt:fontcolor=0xCDE46A:fontsize=15:x=42:y=468')
        graph = ','.join(filters) + ',split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=none'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'lavfi',
                        '-i', 'color=c=0x291F30:s=1000x520:r=5:d=25', '-filter_complex', graph,
                        '-loop', '0', str(output)], cwd=root, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font', required=True, type=Path)
    args = parser.parse_args()
    render(args.receipt, args.output, args.font)
