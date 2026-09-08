# Controlled workflow study

This study compares normal coding tools with Trailbun's **core CLI workflow**
inside real Claude Code and Codex sessions. It does not install native hooks or
measure whether a host rejects writes. Native blocking needs separate receipts.

The fixed matrix is **3 tasks × 2 repeats × 2 hosts × 2 conditions = 24 runs**.
Each run uses a fresh temporary Git repository and fresh host sessions. The resume
task has two separate phases, so the full matrix requires 32 host invocations.
No model is called unless the operator explicitly passes `--run` and `--model`.
The parent bootstraps the locally ignored `.trailbun` runtime before either host
condition starts. Mutable contract input lives there, outside protected Git
metadata; no model needs permission to alter `.git`.

On Windows, the parent preserves the original operator's inherited **Modify**
access on the newly created, empty fixture directory before placing any files.
Only that exact user SID and generated root are affected; no broad group or
recursive ACL reset is used. This avoids a fixture-specific ownership trap:
Python's [`TemporaryDirectory`](https://github.com/python/cpython/blob/v3.12.10/Lib/tempfile.py#L886)
uses [`mkdir(0o700)`](https://github.com/python/cpython/blob/v3.12.10/Lib/tempfile.py#L384),
whose [Windows ACL](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c#L5363)
grants inherited owner-relative rights. A sandbox user creating a file becomes
its owner, so the original operator can otherwise lose read access. The study
records this provisioning in `fixture.json`; it does not change Codex's writable
roots, protected Git metadata, network policy, or global configuration.

## Tasks and comparisons

| Task | Controlled condition | What is measured |
| --- | --- | --- |
| `scope` | A shared route really must change outside the initial narrow scope; an old note suggests unnecessary architecture. | Acceptance, extra paths and whether a precise authorized amendment is recorded. |
| `resume` | Inspection and implementation occur in separate fresh sessions. Plain mode uses `HANDOFF.md`; Trailbun uses a checkpoint. | Preserved production files in phase one, final acceptance and durable handoff presence. |
| `recovery` | The harness seeds two distinct bad rounding corrections and retains their actual failing outputs in both conditions. | Final acceptance and recorded diagnosis, with seeded attempts separated from model behavior. |

Each pair receives the same task requirements and original acceptance checks.
The workflow instructions differ: ordinary files/commands versus Trailbun's
start, checkpoint, resume, amend, diagnose, check and verify. Both conditions
allow the shared-route fix. Extra code is not automatically evidence of worse
engineering; this fixture defines exactly what the task needs.

`tasks.py` contains original fixtures, graders and reference solutions used only
by offline tests. Solutions are never placed in the model's fixture or prompt.
After a run, the scorer executes the original grader outside the editable test
file and separately checks that protected files remain unchanged. This is an
honest correctness check for cooperative coding agents, not an adversarial judge
sandbox: generated Python still executes with the runner's local permissions.

## Preview a run

From the repository checkout with its development environment installed:

```sh
uv run python -m benchmarks.study --host codex --task scope --condition plain --repeat 1 --output study/codex-scope-plain-1
```

This prints a plan and creates no output directory. Select exactly one host,
task, condition and repeat. Available values are:

- `--host claude|codex`
- `--task scope|resume|recovery`
- `--condition plain|trailbun`
- `--repeat 1|2`

## Execute a selected run

```sh
uv run python -m benchmarks.study --host codex --task scope --condition plain --repeat 1 --model gpt-6-astra --output study/codex-scope-plain-1 --run
```

Run the matching condition with the same exact model and a new directory.
Use an explicitly selected Claude model for Claude runs. Model access and host
authentication must already work; the runner does not change credentials or
repair login. Keep condition order balanced across repetitions: plain first in
repeat 1, Trailbun first in repeat 2. Retain interrupted and unsuccessful runs.

Each phase has a 120-second wall-clock limit, reducible with
`--timeout-seconds`. A timeout terminates only the process tree created for that
phase. Claude also receives a $1 reported API budget per phase; Codex has no
equivalent budget flag in this runner. A resume run contains two phases.

Codex runs with `--ignore-user-config`, `--ephemeral`, `--json` and the
`workspace-write` sandbox. On Windows, a process-only
`-c windows.sandbox="elevated"` selects the existing native sandbox setup:
ignoring user configuration otherwise drops that platform setting. This does
not relax filesystem/network permissions.
See the [Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox).

Codex 0.153.4 can [persist project trust when starting a writable thread](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/app-server/src/request_processors/thread_processor.rs#L1334),
even with `--ephemeral --ignore-user-config`. The runner therefore supplies an
inline `projects` TOML value defining trust only for the freshly generated
fixture, through a process override. It records SHA-256 fingerprints of the
Codex user configuration before and after each run; configuration contents are
never exported. A changed fingerprint after a phase prevents subsequent host
sessions in that run. The flag construction is tested, and a separate model-free
configuration readback must confirm exact fixture resolution before live use.
Earlier diagnostic batches predate this correction and retain their observed
automatic configuration side effects in their notes.

Claude uses project settings, an explicit tool list,
`acceptEdits`, strict MCP configuration and no session persistence. The runner
does not bypass hook trust or sandboxing. Managed host policies and host-provided
system instructions can still differ; this does not isolate every vendor default.
Flags were checked against installed CLI help on 2026-09-08. See the official
[Codex CLI reference](https://developers.openai.com/codex/cli/reference/) and
[Claude CLI reference](https://code.claude.com/docs/en/cli-reference).

## Retained evidence

Each fresh output directory contains:

- `run.json`: requested model, host version, OS/Python/Trailbun versions, argv,
  exit status, elapsed time, original acceptance result and changed paths. New
  runs also retain before/after package-source hashes and Codex configuration
  fingerprints; missing observations in older receipts remain unknown.
- `fixture.json`: original files, their combined SHA-256 and seeded failures.
- `phase-N-prompt.txt`, `phase-N-stdout.jsonl`, `phase-N-stderr.txt`: the exact
  prompts and host streams after redaction.
- `artifact.patch` and `artifact-files.json`: the resulting changes and small
  text artifacts, including relevant untracked files.
- `trailbun-state.json` and `receipts/` when the guarded workflow produced them.

Local worktree, source and home paths and recognized credential values are
redacted. Symlinks and files over 64 KiB are not copied into the artifact bundle;
omissions are recorded. The temporary worktree is removed only after evidence
export. Existing output directories are refused rather than overwritten.

Host-reported model IDs, token usage and costs are retained only when present.
An empty `reported_models` list means the stream did not disclose a model ID;
`requested_model` is not silently substituted. Missing cost is not zero cost.
Tool events may contain start and completion notifications for the same command;
use their IDs before calculating command counts.

Generate an aggregate without more model calls:

```sh
uv run python -m benchmarks.summarize evidence/study
```

This writes `summary.json` and `SUMMARY.md`, refusing to overwrite existing
summaries. Missing cells stay visible; absent cost and model IDs remain unknown.
Host process completion, task acceptance, policy errors and usage are separate.

## Interpretation

Report all 24 cells, exact models, condition order, timeouts and missing runs.
Compare acceptance, unapproved paths, workflow use, time and reported usage
separately. A tool can be used correctly without improving the task outcome.

These are tiny, controlled diagnostic tasks. The resume boundary is deliberate;
the bad corrections are seeded. Neither is evidence of naturally occurring
context rot or a spontaneous model retry loop. Two repeats per cell cannot
support universal percentages or model rankings. Native enforcement receipts,
the deterministic `trailbun demo` and this workflow study answer different
questions. Current project claims belong in [EVIDENCE.md](../docs/EVIDENCE.md).

## Offline validation

```sh
uv run pytest tests/test_study.py
```

These tests validate fixture failures, reference solutions, independent scoring,
the legitimate amendment, seeded recovery state, command construction, redaction
and the no-model-call default. They do not call paid models.
