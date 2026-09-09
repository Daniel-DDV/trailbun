<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.webp">
  <source media="(prefers-color-scheme: light)" srcset="assets/hero-light.webp">
  <img src="assets/hero-light.png" alt="Trailbun: a scruffy rabbit points back to a simple trail beside a deep hole filled with unnecessary architecture diagrams." width="100%">
</picture>

# Trailbun

[![CI](https://github.com/Daniel-DDV/trailbun/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Daniel-DDV/trailbun/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/trailbun?include_prereleases)](https://pypi.org/project/trailbun/)
[![Python](https://img.shields.io/pypi/pyversions/trailbun)](https://pypi.org/project/trailbun/)

**Keep your agent on the trail.** Task contracts, scope checks and verification
receipts for coding agents on Codex and Claude Code.

Your agent started with a small bug. Three failed fixes later it is building a
framework, and the original task has scrolled out of its context. Trailbun
writes the task down outside the conversation and checks every change against it.

```text
2026-09-08T22:06:12Z ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: Trailbun scope violation: protected/outside.txt
```

That line is from a real Codex 0.153.4 session on Windows 11 using `apply_patch`.
The attempted patch, the hook receipt, the agent's own report and the unchanged
file hash are in the evidence register: [stderr](evidence/native-codex-corrected-trust.stderr.txt),
[stream](evidence/native-codex-corrected-trust.stream.jsonl),
[reassessment](evidence/native-codex-corrected-trust.reassessment.json). The
probe's own status field reads `incomplete` because its first verifier expected
an event Codex does not emit for pre-tool denials; the reassessment passes all
nine checks. Claude Code 2.1.263 is installed and the adapter fixtures pass
against the Python CLI. There is no live Claude receipt yet.

**Status: 0.2.1 preview.**
Codex 0.153.4 on Windows: one permitted native patch succeeded, one out-of-scope
patch was rejected, and a saved checkpoint returned after manual compaction.
Receipts in [docs/EVIDENCE.md](docs/EVIDENCE.md).
Claude Code: adapter and generated-command fixtures pass against the Python CLI.
No live session has been run.
No effectiveness percentage is claimed.

**[Try the demo](#try-it) · [Use it on a project](docs/USAGE.md) · [Inspect the evidence](docs/EVIDENCE.md)**

## Try it

With [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git installed:

```sh
uvx --from git+https://github.com/Daniel-DDV/trailbun@v0.2.1 trailbun demo
```

Once the 0.2.1 pre-release is on PyPI this becomes `uvx trailbun demo`.

The demo creates an isolated temporary Git repository, saves a redirect-fix
task, introduces an unnecessary authentication framework, reports the scope
violation, restores a checkpoint and verifies the small fix. It makes no model
calls and does not edit your project. It prints four short screens; add
`--json` for the full result, or `--output trailbun-demo` to keep `demo.json`.

![Trailbun demo rendered from the retained demo JSON: the check reports new-auth-framework.txt as a violation, then the receipt passes.](assets/demo.gif)

The GIF is rendered from [the retained demo JSON](evidence/demo/demo.json); a
[static final frame](assets/demo-final.png) is also available.

## What it does

A **contract** is a small JSON file with the goal, the allowed paths and the
acceptance checks. The **baseline** is the Git commit the task started from. A
**receipt** is the recorded result of running the checks, bound to a hash of
every file it checked.

| When this happens | Trailbun's response |
| --- | --- |
| A green check belongs to older code | The receipt records a hash of every tracked and untracked file and the check definitions. Change one byte and the receipt is stale. |
| The agent wanders into other files, including committed ones | Compare the worktree with the commit the task started from: committed, staged, unstaged and untracked changes. |
| The session forgets the task | Restore the goal, exclusions, progress, failed hypotheses and next action from a compact checkpoint, including after compaction on a bound session. |
| The same correction keeps failing | Require a recorded diagnosis with evidence after two distinct failed corrective artifacts for the same check. |
| The agent tries to finish without evidence | Block Stop once on Codex, with a live receipt; Claude Code has fixture coverage only. The task stays incomplete when checks are missing or stale. |

A task file in the repository is what the study's plain condition uses. Trailbun
differs in three checkable ways: it diffs against the commit the task started
from, its passing receipt goes stale when any checked file changes, and on Codex
it returns a native deny for `apply_patch` outside scope. Claude Code's
permission rules can deny edits to a path pattern and apply the same rules to
Bash redirects; they cannot express "only these two files", and they cannot tell
you whether the tests that passed ran against the files you are about to merge.

An explicitly declared initial TDD failure does not count as a failed corrective
attempt. Legitimate scope changes use `amend`, with a reason and the original
baseline retained.

```text
task → checkpoint → check the artifact → diagnose or verify → fresh start
```

## Install

```sh
uv tool install git+https://github.com/Daniel-DDV/trailbun@v0.2.1
trailbun --version
```

Requires Python 3.11 to 3.14 and Git. Installing the CLI does not rewrite your
global agent configuration. Native hooks are a separate, explicit project-local
setup step. See [uv's tool installation documentation](https://docs.astral.sh/uv/guides/tools/).

For a repository you want to use with Codex or Claude Code:

```sh
trailbun setup --host codex --project .
# Or: trailbun setup --host claude --project .
```

Setup writes project-local hooks and three skills, keeps the generated files
out of `git status` through `.git/info/exclude`, and prints the next command.
For Claude Code the hooks go to `.claude/settings.local.json`, which stays on
this machine; `--shared` writes `.claude/settings.json` for a team instead.
Then follow [task and session setup](docs/USAGE.md). Starting a task requires a
clean Git worktree. Each native session binds to the task with its host and
session ID; an old task on disk does not silently activate a guard in a new chat.

```sh
trailbun doctor --host codex --project . --probe
trailbun uninstall --host codex --project .
```

Remove project integration before removing the CLI with `uv tool uninstall trailbun`.
Uninstall leaves task evidence available.

## Commands

| Command | Purpose |
| --- | --- |
| `start` / `amend` | Define the task or record an explicit contract change; `--rebaseline` after history was rewritten. |
| `checkpoint` / `resume` | Save a compact handoff or restore task context. |
| `check` / `verify` | Inspect artifact drift or execute acceptance checks. |
| `diagnose` | Record reproduction, cause, evidence and the next experiment. |
| `setup` / `doctor` / `uninstall` | Manage and inspect one project's native integration. |
| `demo` | Replay the isolated demonstration. |
| `hook` | Host-invoked adapter; setup installs it, you do not run it yourself. |

Run `trailbun <command> --help` for arguments; `start --help` shows the contract
format. Machine-readable output uses `--json`; exits are `0` for OK, `1` for a
violation and `2` for incomplete work or an error.

## Coverage and evidence

A fixture proves the behavior it exercises; a live host receipt proves only its
named version, OS and action path. The [claims table](docs/EVIDENCE.md#claims)
labels every claim ASSERTED, ENFORCED or MEASURED.

| Surface | Current evidence boundary |
| --- | --- |
| Python core | Deterministic regression fixtures; current run results are in [evidence](docs/EVIDENCE.md). |
| Codex | 0.153.4 on Windows: a permitted native patch succeeds, an out-of-scope patch is rejected, and saved context returns after manual compaction. [Receipts](docs/EVIDENCE.md#native-host-coverage). |
| Claude Code | 2.1.263 installed. Adapter and generated-command fixtures pass against the Python CLI. No live receipt yet; the probe is the next check. |
| Shell, MCP and other write paths | No universal pre-write coverage; workspace checks observe relevant changes after they happen. |
| Controlled workflow study | 12 of 12 Codex cells pass in both conditions. No difference between conditions is claimed; the tasks are small and instructed. Claude cells are unrun. [Results and limits](evidence/study-final/SUMMARY.md). |

## What it does not do

- It checks file scope only. Matching the allowed paths does not prove a change satisfies the user's intent.
- It inspects Edit, Write, NotebookEdit and `apply_patch` targets before they run. Shell and MCP writes are checked afterwards against tracked and untracked files; ignored files only when the contract lists them.
- It is not a sandbox. The agent may have tools outside the paths a hook can inspect.
- The agent can change the contract. `amend`, `start --abandon-reason` and `diagnose` are ordinary commands, and the session hook shows the agent its own session ID. Trailbun records each change with a reason, a timestamp and the calling command. It does not stop the agent from making one. Read `.trailbun/state.json` or `trailbun check --json` before you trust a receipt.
- Hooks run on every Edit, Write, NotebookEdit and Bash call the host reports. A post-action check hashes the tracked and untracked tree; on a 10,000-file tree that took about 7 seconds on the measured machine. A slow or missing hook is not enforcement; `doctor --probe` and the invocation receipts show whether it ran.
- Checkpoints restore text. They do not repair model attention, and no effectiveness percentage is claimed.

## Contribute a useful failure

The best contribution is a small reproduction: the intended task, what actually
happened, the host and version, and the next check that would have caught it.
Open an issue with the [useful failure template](.github/ISSUE_TEMPLATE/useful-failure.md)
or see [CONTRIBUTING.md](CONTRIBUTING.md), the [Receipt Card](docs/RECEIPT.md)
and the [15-minute Reality Check](docs/REALITY_CHECK.md).

The [Nine Laws](docs/LAWS.md) explain the engineering discipline. The
[brand notes](docs/BRAND.md) include artwork provenance and reusable assets.

Created by [Daniel Verloop](https://github.com/Daniel-DDV). [MIT license](LICENSE).
