"""Summarize retained cells without invoking a model or replacing raw evidence."""

import argparse
import json
from pathlib import Path


def summarize(directory):
    rows, usage_totals, models, requested, costs = [], {}, set(), set(), []
    for host in ('claude', 'codex'):
        for task in ('scope', 'resume', 'recovery'):
            for repeat in (1, 2):
                for condition in ('plain', 'trailbun'):
                    name = f'{host}-{task}-{condition}-{repeat}'
                    folder = directory / name
                    row = {'cell': name, 'host': host, 'task': task, 'repeat': repeat,
                           'condition': condition, 'recorded': (folder / 'run.json').is_file()}
                    if not row['recorded']:
                        row['host_process_status'] = 'not-run'
                        rows.append(row)
                        continue
                    report = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
                    phases = report.get('phases', [])
                    blocked = sum(path.read_text(encoding='utf-8').count('blocked by policy')
                                  for path in folder.glob('phase-*-stderr.txt'))
                    phase_usage = [usage for phase in phases for usage in phase['telemetry']['usage']]
                    for usage in phase_usage:
                        for key, value in usage.items():
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                usage_totals[key] = usage_totals.get(key, 0) + value
                    for phase in phases:
                        models.update(phase['telemetry']['reported_models'])
                        costs.extend(phase['telemetry']['reported_cost_usd'])
                    requested.add(report.get('requested_model'))
                    row.update({'host_process_status': report['status'],
                        'task_success': report.get('score', {}).get('task_success'),
                        'acceptance_passed': report.get('score', {}).get('acceptance_passed'),
                        'out_of_scope_paths': report.get('score', {}).get('out_of_scope_paths'),
                        'policy_block_messages': blocked, 'phase_count': len(phases),
                        'timeout_count': sum(bool(phase['timed_out']) for phase in phases),
                        'model_wall_seconds': round(sum(phase['duration_seconds'] for phase in phases), 3),
                        'reported_usage': phase_usage, 'workflow_observed': report.get('workflow_observed'),
                        'runner_or_export_errors': {key: report[key] for key in ('error', 'artifact_export_error') if report.get(key)},
                        'evidence': f'{name}/run.json'})
                    rows.append(row)
    recorded = [row for row in rows if row['recorded']]
    return {'kind': 'controlled-core-workflow-study-summary', 'planned_runs': 24,
        'native_hooks_installed': False, 'recorded_runs': len(recorded),
        'missing_runs': 24 - len(recorded),
        'recorded_phases': sum(row['phase_count'] for row in recorded),
        'task_successes': sum(row['task_success'] is True for row in recorded),
        'policy_blocked_runs': sum(row['policy_block_messages'] > 0 for row in recorded),
        'timeouts': sum(row['timeout_count'] for row in recorded),
        'runs_with_runner_or_export_errors': sum(bool(row['runner_or_export_errors']) for row in recorded),
        'model_wall_seconds_sum': round(sum(row['model_wall_seconds'] for row in recorded), 3),
        'requested_models': sorted(model for model in requested if model),
        'reported_models': sorted(models), 'reported_usage_totals': usage_totals,
        'reported_cost_usd': sum(costs) if costs else None,
        'interpretation': 'Diagnostic outcomes only; no efficacy estimate. Missing model/cost is unknown. '
                          'Process completion is separate from acceptance. Summed session times are '
                          'not elapsed experiment time when tasks run concurrently.',
        'rows': rows}


def markdown(report):
    lines = ['# Controlled study results', '',
        f"Recorded {report['recorded_runs']} of 24 runs ({report['recorded_phases']} host sessions); "
        f"{report['missing_runs']} runs are missing. Task success: {report['task_successes']} recorded runs. "
        f"Policy rejection messages occurred in {report['policy_blocked_runs']} runs. "
        f"Timeouts: {report['timeouts']}. Runner or export errors: {report['runs_with_runner_or_export_errors']} runs.", '', report['interpretation'], '',
        'Requested models: ' + ', '.join(report['requested_models']) + '. '
        'Host-reported model IDs: ' + (', '.join(report['reported_models']) or 'not disclosed') + '.', '',
        f"Sum of session durations: {report['model_wall_seconds_sum']} s. "
        'Reported cost: ' + (str(report['reported_cost_usd']) if report['reported_cost_usd'] is not None else 'not disclosed') + '.', '',
        'Reported usage totals (fields retain the host names and may overlap):', '',
        '```json', json.dumps(report['reported_usage_totals'], indent=2), '```', '',
        '| Cell | Process | Acceptance | Overall task | Extra paths | Runner/export error | Policy rejections | Sessions | Seconds |',
        '| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |']
    for row in report['rows']:
        if not row['recorded']:
            lines.append(f"| {row['cell']} | not run | — | — | — | — | — | — | — |")
        else:
            acceptance = {True: 'pass', False: 'fail', None: 'not scored'}[row['acceptance_passed']]
            overall = {True: 'pass', False: 'fail', None: 'not scored'}[row['task_success']]
            extra = ', '.join(row['out_of_scope_paths'] or []) or 'none'
            error = 'yes; see receipt' if row['runner_or_export_errors'] else 'none'
            lines.append(f"| [{row['cell']}]({row['evidence']}) | {row['host_process_status']} | "
                         f"{acceptance} | {overall} | {extra} | {error} | {row['policy_block_messages']} | {row['phase_count']} | {row['model_wall_seconds']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    report = summarize(args.directory)
    for name, content in [('summary.json', json.dumps(report, indent=2)), ('SUMMARY.md', markdown(report))]:
        with (args.directory / name).open('x', encoding='utf-8') as stream:
            stream.write(content)
    print(json.dumps({key: value for key, value in report.items() if key != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
