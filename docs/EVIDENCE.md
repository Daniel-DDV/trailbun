# Trailbun evidence register

Reviewed 2026-09-08. Evidence is specific to the recorded version, environment
and action. This register separates an executable mechanism from a measured
benefit to an agent.

## Core validation

Local regression run: **102 passed, 1 skipped in 50.10 seconds**, Python 3.12.11
on Windows 11. The skip is a newline filename that Windows cannot create.
The suite covers contract validation, Git layers and renames, linked worktrees,
symlink escapes, Windows path case, stale verification, expected initial red,
failure budgets, evidence-backed diagnosis, malformed state, session isolation,
native protocol translation and reversible installation conflicts.

```sh
uv run pytest -ra
uv run python -m build
```

The source distribution and wheel build successfully. The wheel contains all
three native skills. CI defines Windows, Ubuntu and macOS across Python
3.11–3.14; remote execution results are recorded below when available.

Independent review found and corrected defects before release: a `.git` symlink
alias, subtree-scoped checks, removed ignored watchers, case-sensitive scope
matching on Windows, corrupt state handling, lost incomplete-check evidence,
session validation after mutation, disabled-hook reporting and partial uninstall
on conflicts. Regressions accompany the corrections. Review is not a claim that
every possible host or filesystem action is covered.

## Deterministic demonstration

[The retained JSON](../evidence/demo/demo.json) contains the real temporary Git
task, detected unapproved path, restored checkpoint and executed successful
acceptance check. [The 25-second GIF](../assets/demo.gif) is rendered from that
JSON with [the rendering script](../scripts/render_demo.py).

This is a deterministic demonstration with **no live model**. Temporary runtime
paths in the JSON cease to exist after cleanup; the complete demo result,
including its final receipt, remains embedded in the exported file.

## Inspection measurements

Ten repeated inspections of fixed, small text files on this Windows machine:

| Files | Median | Observed p95 | Raw measurements |
| --- | ---: | ---: | --- |
| 1,000 | 831 ms | 899 ms | [JSON](../evidence/performance-1000.json) |
| 10,000 | 6,620 ms | 6,960 ms | [JSON](../evidence/performance-10000.json) |

Measured with [measure_checks.py](../scripts/measure_checks.py), Python 3.12.11.
These timings exclude native hook startup and model work. The first run is not
a guaranteed cold-cache measurement. File sizes, storage and background load
matter; this is not a speed claim for arbitrary repositories.

Known-write prechecks inspect declared targets rather than hash the whole tree.
Post-action inspection, stop checks and bound context restoration scan the
artifact. A 10,000-file tree can approach the installed 10-second hook timeout
once startup is included. A timeout may bypass intervention; a slow or missing
hook is not successful enforcement.

## Native host coverage

| Host | Installed version | Current live boundary |
| --- | --- | --- |
| Codex | 0.153.4 | Authenticated model invocation confirmed; rejected-write smoke in progress. |
| Claude Code | 2.1.263 | CLI available; authentication reports `loggedIn: false`, so model smoke is pending. |
| Grok Build | Not exercised | Deferred. |

Adapter fixtures execute the generated commands against the real Python CLI,
including Windows paths with spaces, apostrophes, dollar signs and Unicode.
They validate protocol construction, not host-side rejection.

Native rejection requires the actual tool attempt, denial, unchanged sentinel
hash and matching hook invocation record. Any one-off Codex hook-trust bypass
used for vetted automation is recorded explicitly; it does not configure trust
for ordinary sessions. Automatic compaction, manual compaction, `/clear`, host
updates, arbitrary shell commands and MCP tools need their own live receipts.
No universal write protection is claimed.

## Controlled agent study

[The runner and method](../benchmarks/README.md) define **24 cells**: three small
tasks, two repeats, two hosts and two conditions. This study uses Trailbun's
core CLI workflow; native hooks are not installed. Resume has two fresh-session
phases. Recovery failures are deliberately seeded by the harness.

Codex runs are in progress. Claude runs are pending authentication. Missing
runs are not successes or zero-cost observations. Every completed, failed or
interrupted invocation will remain in the evidence bundle. Requested models,
host-reported models, usage, wall time and acceptance are recorded separately.

These controlled tasks can reveal workflow friction. They cannot establish
natural context-rot prevention, a universal performance percentage or a model
ranking. No agent-effectiveness percentage is claimed.
