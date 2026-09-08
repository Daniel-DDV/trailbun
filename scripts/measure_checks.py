"""Measure core inspection on a fixed-size synthetic Git fixture, without models."""

import argparse
import json
import math
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from trailbun import engine


def measure(count=1000, repeats=10):
    with tempfile.TemporaryDirectory(prefix='trailbun-perf-') as directory:
        root = Path(directory)
        def git(*args):
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid', *args], check=True, capture_output=True)
        git('init', '-q')
        (root / 'src').mkdir()
        for index in range(count):
            (root / 'src' / f'file{index:05}.txt').write_text(f'value = {index}\n')
        git('add', '.')
        git('commit', '-qm', 'Fixed performance fixture')
        engine.start(root, {'goal': 'Inspect fixed fixture', 'allowed_paths': ['src'],
                            'checks': [{'id': 'placeholder', 'argv': ['python', '-V']}]})
        timings = []
        for _ in range(repeats):
            begin = time.perf_counter()
            result = engine.check(root)
            assert result['status'] == 'ok'
            timings.append(round((time.perf_counter() - begin) * 1000, 2))
        return {'kind': 'core-inspection-microbenchmark', 'platform': platform.platform(),
                'python': platform.python_version(), 'files': count, 'runs': repeats,
                'milliseconds': timings, 'first_ms': timings[0], 'median_ms': statistics.median(timings),
                'p95_ms': sorted(timings)[math.ceil(len(timings)*.95)-1],
                'limits': 'One machine; excludes native hook startup and model execution. First run is not an OS cold-cache guarantee.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=int, default=1000)
    parser.add_argument('--repeats', type=int, default=10)
    args = parser.parse_args()
    if args.files < 1 or args.repeats < 2:
        parser.error('Use at least one file and two repeats.')
    print(json.dumps(measure(args.files, args.repeats), indent=2))
