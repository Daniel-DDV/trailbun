# Trailbun evidence register

Reviewed 2026-09-09. Evidence is specific to the recorded version, environment
and action. This register separates an executable mechanism from a measured
benefit to an agent.

## Core validation

Local regression run: **135 passed, 1 skipped in 90.71 seconds**, Python 3.12.10
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
three native skills. A separate replay of native-probe and study regressions
from the extracted source archive passed **29 tests in 13.42 seconds**.
The [first remote CI run](https://github.com/Daniel-DDV/trailbun/actions/runs/34281041603)
passed all twelve Windows, Ubuntu and macOS / Python 3.11–3.14 combinations.
The subsequent runtime compatibility correction receives a separate final run.

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

Published local paths are redacted. Fingerprints refer to the original inputs;
the redacted export records that distinction explicitly.

## Inspection measurements

Ten repeated inspections of fixed, small text files on this Windows machine:

| Files | Median | Observed p95 | Raw measurements |
| --- | ---: | ---: | --- |
| 1,000 | 1,139 ms | 1,206 ms | [JSON](../evidence/performance-1000-final.json) |
| 10,000 | 6,841 ms | 6,990 ms | [JSON](../evidence/performance-10000-final.json) |

Measured with [measure_checks.py](../scripts/measure_checks.py), Python 3.12.11.
These timings exclude native hook startup and model work. The first run is not
a guaranteed cold-cache measurement. Other local validation work was active on
the same machine. File sizes, storage and background load matter; this is not a
speed claim for arbitrary repositories. Earlier pre-migration measurements are
retained separately and are not a controlled before/after comparison.

Known-write prechecks inspect declared targets rather than hash the whole tree.
Post-action inspection, stop checks and bound context restoration scan the
artifact. A 10,000-file tree can approach the installed 10-second hook timeout
once startup is included. A timeout may bypass intervention; a slow or missing
hook is not successful enforcement.

## Native host coverage

| Host | Installed version | Current live boundary |
| --- | --- | --- |
| Codex | 0.153.4 | Windows: one permitted native patch succeeds and one out-of-scope native patch is rejected; sentinel and global configuration remain unchanged in the corrected probe. |
| Claude Code | 2.1.263 | CLI available; authentication reports `loggedIn: false`, so model smoke is pending. |
| Grok Build | Not exercised | Deferred. |

Adapter fixtures execute the generated commands against the real Python CLI,
including Windows paths with spaces, apostrophes, dollar signs and Unicode.
They validate protocol construction, not host-side rejection.

The corrected Codex probe retains its [report](../evidence/native-codex-corrected-trust.json),
[native stream](../evidence/native-codex-corrected-trust.stream.jsonl),
[native diagnostic](../evidence/native-codex-corrected-trust.stderr.txt) and
[offline reassessment](../evidence/native-codex-corrected-trust.reassessment.json).
The original verifier reported incomplete because it expected a failed
`file_change` event. Codex rejects `PreToolUse` before that event lifecycle
starts. The independently reviewed reassessment instead requires the native
router rejection, exact attempted patch fingerprint, bound hook receipt,
successful allowed patch and external file hashes. All nine checks pass;
the original verdict and raw evidence remain intact.
[Codex tool dispatch](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/tools/registry.rs#L527)

The earlier [interpreter failure](../evidence/native-codex.json) and
[ineffective trust override](../evidence/native-codex-system-python.json) are
retained as failed validation attempts. They are not successful enforcement.
The [model-free configuration probe](../evidence/native-config-probe.json)
checks the corrected exact-project trust resolution and hook discovery.

Native rejection requires the actual tool attempt, denial, unchanged sentinel
hash and matching hook invocation record. Any one-off Codex hook-trust bypass
used for vetted automation is recorded explicitly; it does not configure trust
for ordinary sessions. Automatic compaction, `/clear`, host updates, arbitrary
shell commands and MCP tools need their own live receipts.
No universal write protection is claimed.

A separate [manual-compaction receipt](../evidence/native-codex-manual-compact.json)
records a real `thread/compact/start` completion followed by the native
`SessionStart` hook returning the exact saved goal, scope and checkpoint in the
bound session. All six checks pass; the 26.266-second probe leaves source,
artifact and global configuration content unchanged. This uses a short injected
conversation, not natural context exhaustion, and does not measure whether the
model subsequently follows the supplied context.
[Codex manual compaction API](https://learn.chatgpt.com/docs/app-server#trigger-thread-compaction)

The public compaction stream omits unrelated account, rate-limit and installation
notifications. Its report records the removed notification types and original
and public hashes; the native proof events remain available for independent
replay. Regression coverage checks future exports apply the same filtering.

Codex 0.153.4 invokes `PostToolUse` after successful tool execution. A failed
shell command that already changed files may therefore be observed only by a
later artifact or stop check. Claude's separate failure-event adapter has
fixture coverage, not a live receipt.
[Codex post-tool dispatch](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/tools/registry.rs#L630)

Earlier validation attempts exposed another host side effect: Codex 0.153.4
automatically persisted trust for five temporary test projects when a writable
thread started without an effective project trust setting. `--ignore-user-config`
and `--ephemeral` did not prevent that branch. The runner's initial dotted-key
override had been parsed incorrectly; corrected overrides supply a TOML table
as the value. This is distinct from Trailbun's project-local setup behavior.
Original probe metadata is corrected explicitly and the raw streams retained.
[Codex thread-start implementation](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/app-server/src/request_processors/thread_processor.rs#L1334)

## Controlled agent study

[The runner and method](../benchmarks/README.md) define **24 cells**: three small
tasks, two repeats, two hosts and two conditions. This study uses Trailbun's
core CLI workflow; native hooks are not installed. Resume has two fresh-session
phases. Recovery failures are deliberately seeded by the harness.

The [final Codex batch](../evidence/study-final/SUMMARY.md) completed all twelve
Codex cells across sixteen sessions using Codex 0.153.4, requested model
`gpt-6-astra`, Python 3.12.10 and the corrected Windows fixture setup:

- Functional acceptance passes in all twelve cells, six per condition.
- All six Trailbun cells retain a checkpoint and current verification; both
  scope cells record the necessary amendment, and both recovery cells record
  the required diagnosis.
- All protected files remain unchanged. There are no timeouts, execution-policy
  errors or unreadable exports; source and global configuration content match
  their before/after hashes in every cell.
- Total recorded host-phase time is 1,125.159 seconds. Sessions overlapped, so
  this is not elapsed experiment time. The host reports 2,689,374 input tokens
  (2,353,152 cached) and 20,903 output tokens; actual model IDs and cost were
  not disclosed.

The strict artifact score passes in nine cells: six Trailbun and three plain.
The remaining plain cells create `DIAGNOSIS.md`, which the generic plain-mode
prompt mentions but those fixtures' artifact sets exclude. That is a disclosed
prompt sensitivity, not evidence of spontaneous drift or worse engineering.
Read the [method caveats](../evidence/study-final/NOTES.md) before comparing
conditions. The twelve Claude cells remain unrun because authentication was
unavailable; their absence is explicit in the full matrix.

The [initial Codex batch](../evidence/study/SUMMARY.md) attempted eleven cells
(fourteen native sessions). All encountered execution-policy rejection before
the workflow could run. One Codex cell and all twelve Claude cells were not run.
These are infrastructure failures, not measurements of Trailbun's effectiveness.

The Windows preflight identified a missing explicit sandbox implementation in
the runner. It also exposed an independent artifact-read permission error in
the temporary fixtures. CPython's Windows `mkdir(0700)` uses inherited OWNER
RIGHTS, which can cease to grant the original caller access when a sandbox user
owns a newly created file. This is a fixture-specific finding, not proof that
ordinary Windows repositories are universally affected.
[CPython implementation](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c#L5363)

Runtime bootstrap now preserves only the initializing user's inherited Modify
access on the owned directory. The native probe independently checks access
after the sandbox writes state. No project-wide or system ACL is changed.
Codex's Git-metadata protection required moving task state outside `.git`.
Those findings and original streams are retained; corrected runs are separate.
Requested models, host-reported models, usage, wall time and acceptance are
recorded separately. Missing results are not successes or zero-cost observations.

These controlled tasks can reveal workflow friction. They cannot establish
natural context-rot prevention, a universal performance percentage or a model
ranking. No agent-effectiveness percentage is claimed.
