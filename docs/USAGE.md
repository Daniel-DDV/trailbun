# Use Trailbun

Trailbun keeps one task per Git worktree. Start from a committed baseline, write
down the intended change, and verify the resulting files against named checks.
The CLI also works without a coding-agent integration.

## Glossary

| Term | Meaning |
| --- | --- |
| Contract | The JSON file with the goal, exclusions, allowed paths, checks and optional expected initial failures. |
| Baseline | The Git commit HEAD pointed at when the task started. Every scope check diffs against it. |
| Revision | The contract version number; `start` records revision 1 and each `amend` adds one. |
| Artifact | Every tracked and untracked file in the worktree, plus watched ignored files, with HEAD and the index. |
| Fingerprint | A SHA-256 over the artifact. Receipts and stale checks compare fingerprints. |
| Receipt | The retained result of one `verify` run: commands, output, exit codes, fingerprints, timestamps. |
| Checkpoint | The saved progress summary, next action and disproven hypotheses that `resume` prints. |
| Run | One task from `start` to a verified completion or an explicit abandonment. |

## Start a task

Install the CLI as shown in the [README](../README.md). Then create the runtime
once from your own terminal, either with `trailbun setup --host ...` or with a
first `trailbun start`, and write the contract to `.trailbun/task.json`. That
directory is excluded from Git by Trailbun's own block in `.git/info/exclude`,
so the contract neither dirties the worktree nor counts as drift. Before the
runtime exists, pass the contract on stdin with `--contract -` or keep it
outside the repository. Any other untracked file in the repository blocks
`start` and later counts as drift.

```json
{
  "goal": "Redirect signed-out users to /login without changing signed-in behavior",
  "exclusions": ["No new authentication framework", "No dependency changes"],
  "allowed_paths": ["src/redirect.py", "tests/test_redirect.py"],
  "checks": [
    {
      "id": "redirect",
      "argv": ["python", "-m", "pytest", "tests/test_redirect.py", "-q", "-p", "no:cacheprovider"],
      "timeout_seconds": 60
    }
  ]
}
```

```sh
git status --short
trailbun start --contract .trailbun/task.json --project .
trailbun check --project .
```

`start` refuses a dirty worktree and lists the first five paths. Commit or
isolate existing work yourself; Trailbun never stashes, resets or commits.
Initial setup or start bootstraps the owned `.trailbun` runtime directory and
its local Git exclude entry. Later agent commands update this state inside the
normal workspace sandbox. On Windows, initialization also preserves the
initializing user's inheritable Modify access on that new runtime directory.
It does not change project-wide or system permissions.

Paths are repository-relative literal files or directories, with no wildcards.
`.` permits the project tree; use narrower paths when the task permits it.
Git metadata, Trailbun runtime data and paths escaping the project are
excluded. Host configuration (`.claude/settings.json`,
`.claude/settings.local.json`, `.codex/hooks.json`, `.codex/config.toml` and
the installed Trailbun skills) is excluded from a broad scope such as `.` and
allowed only when an `allowed_paths` entry names the file exactly. Submodules
and unsupported artifact types produce an incomplete result.

Checks are argument arrays executed in the repository root, without an implicit
shell. The first element is resolved through `PATH` (and `PATHEXT` on Windows)
and recorded in the receipt as `resolved_executable`; `.cmd` and `.bat` shims
such as `npm` and `npx` run through `cmd.exe`. Use the interpreter or
environment that has your project's test dependencies. Timeouts default to 60
seconds and may range from 1 to 600 seconds.

Checks that write into the tree make the receipt incomplete and list the paths
under `changed_during_checks`; on the next `check` those paths count as drift.
Point caches outside the tree or turn them off: `PYTHONDONTWRITEBYTECODE=1`,
`pytest -p no:cacheprovider`, build output directories in `.gitignore`.

## Save and restore progress

```sh
trailbun checkpoint --summary "Found the fallback redirect in src/redirect.py" --next-action "Add a signed-out regression and fix the fallback"
trailbun resume
```

Add `--failed-hypothesis "The session cookie was not the cause"` to retain a
disproven hypothesis. The flag is repeatable and duplicates are dropped. A
checkpoint changes progress; it does not change the task's scope or checks.

`resume` prints the goal, scope, exclusions, checks, progress, hypotheses,
contract revision with the amendment count, and verification status.
`--export ../handoff.txt` writes a new file and refuses to overwrite one.
Supply that text to a fresh session. Updates that would exceed 6 KiB of resume
context are rejected; submit a shorter update.

## Verify, amend and diagnose

```sh
trailbun check
trailbun verify
```

`check` compares committed, staged, unstaged and untracked paths with the fixed
starting commit. `verify` first checks scope, then executes all contracted
checks. A receipt records the commands, the resolved executable, bounded
output, exit status, duration, contract revision and artifact fingerprints, and
`check` prints the latest receipt's SHA-256. Changed check definitions or file
contents make the previous receipt stale. Changes during verification yield an
incomplete receipt. A scope match alone does not establish completion.

For deliberate TDD, declare `"expected_red": ["redirect"]` in the contract and
run `trailbun verify --baseline` before editing. This is a one-time declaration
of the expected initial failures; it is not a passing completion receipt.

When inspection reveals a necessary scope change, edit the contract:

```sh
trailbun amend --contract .trailbun/task.json --reason "The redirect is selected in src/routes.py; include that exact file"
```

Amendments keep the original Git baseline unless `--rebaseline` is given; each
rebaseline is recorded with its reason. An amendment records the previous
contract, the reason, the time and the command that made it. It invalidates
verification. A failure counter is kept when its check definition is unchanged
and reset when the definition changed; an amendment identical to the current
contract is refused.

Trailbun compares the worktree with the commit recorded at start. If that
commit is amended, rebased, reset away or no longer reachable from HEAD, the
`check`, `verify`, `resume` and `checkpoint` commands fail with
`Baseline <sha> is not an ancestor of HEAD`, and a bound Stop hook blocks once
with that message. Review the commits between the old baseline and HEAD
yourself before continuing, because Trailbun stops comparing against them once
a new baseline is recorded. Then run
`trailbun amend --contract .trailbun/task.json --reason "..." --rebaseline`.
The previous baseline, the reason and the time are kept in the contract history.

Two distinct failed corrective artifacts for one check require diagnosis. The
counter keys on file contents, so staging or committing the same failed
correction is the same attempt. A diagnosis must name evidence: a nonempty file
inside the worktree, or a retained `receipt:<id>` whose status is `violation`.
A passing receipt or a file outside the worktree is refused while a check is
blocked.

```sh
trailbun diagnose --reproduction "Run the redirect check with a signed-out request" --cause "The fallback is chosen before the authentication branch" --evidence src/redirect-reproduction.txt --next-action "Move fallback selection after the branch and rerun the regression"
```

Trailbun records the evidence hash, its kind and the blocked checks, and
retains the previous failure counters. Reusing the same evidence cannot reset
the budget repeatedly. A hash establishes that evidence exists, not that the
proposed cause is correct. Check the diagnosis before acting on it.

A new task may replace a verified, clean task. To deliberately abandon an
incomplete one, use `start --abandon-reason "..."`; the previous run is
archived with the command that ended it.

## Native sessions

```sh
trailbun setup --host codex
# Or: trailbun setup --host claude
```

Setup adds project-local hook definitions and three small skills. Review the
generated files and restart the host. Codex requires review and trust of hook
definitions through its native workflow. Setup does not edit global settings.

Claude Code hooks go to `.claude/settings.local.json`, the per-machine file,
because the generated command embeds this machine's interpreter path.
`--shared` writes `.claude/settings.json` instead, with a bare `trailbun`
command that every teammate must have on `PATH`. Claude setup also adds
`Edit(...)` deny rules for `.trailbun/**` and the two settings files, which the
host applies to its file tools and to recognized Bash file commands and
redirections (host-documented, live-unverified). Codex writes
`.codex/hooks.json`. Rerun setup after moving the Python environment.

Generated files are listed in the installation manifest and added to the
Trailbun block in `.git/info/exclude`, so `git status` stays clean and `start`
can run immediately. Uninstall removes exactly those entries.

### Who does what

1. You run `trailbun setup --host <host>` once, from your own terminal.
2. You restart the host in the project. Its SessionStart hook runs Trailbun,
   which prints the session ID into the model's context.
3. The agent runs `trailbun start --contract .trailbun/task.json --host <host> --session <id>`
   (or `resume` with the same flags). On Claude Code the bundled `trailbun-start`
   and `trailbun-resume` skills are user-invoked only; Codex ignores that field
   and may invoke them itself.
4. The host calls the installed hook on Edit, Write, NotebookEdit and Bash
   (Claude Code) or `apply_patch` and every tool (Codex), and on Stop.
5. `trailbun doctor --host <host> --probe` shows whether the hook is installed,
   starts, has been invoked, is disabled by a settings file, or differs from
   the manifest.

### What your agent sees

SessionStart, before binding:

```text
Trailbun: No task is active. Session binding: --host codex --session <id>. Run `"<python>" -m trailbun resume --host codex --session <id>` (or trailbun start with the same flags) explicitly to activate guards for this session. Any command that changes the contract is recorded with a reason; it is not blocked.
```

PreToolUse, target outside scope (a native deny):

```text
Trailbun scope violation: protected/outside.txt
```

PostToolUse, after a shell write outside scope (context, not a deny):

```text
Trailbun detected workspace drift outside the task scope: protected/outside.txt. The operation already ran; inspect the changes.
```

Stop, without a current receipt (blocked once, then a system message):

```text
Trailbun task remains incomplete: refresh verification evidence and resolve scope or diagnosis findings. Do not claim completion without current passing evidence. Contract revision 2, amended 1 times since start, last reason: include routes.py (recorded, not enforced). Latest receipt 3f9c0a1b7e2d (violation, sha256 5b1d...).
```

Hooks cost one interpreter start per matched call, plus a tree hash on
PostToolUse and Stop. Reads, searches and unmatched tools do not invoke the
hook. The installed timeout is 60 seconds; both hosts treat a timed-out hook
as no decision, so a slow hook is a warning, never enforcement.

Known native write targets outside scope are denied. Shell and other unknown
mutations may only be observed afterward; hooks cannot undo them. Completion
requests without current evidence get at most one continuation reminder per
stop chain. Hooks never execute acceptance tests or launch another model.

```sh
trailbun doctor --host codex --json
trailbun uninstall --host codex
```

`doctor` distinguishes configured hooks, recorded invocations, a handler that
starts, and settings that disable hooks (`disableAllHooks` in user, project or
local settings, with the local file winning). Those facts alone are not proof
that a native write was blocked. Inspect the
[live evidence boundary](EVIDENCE.md). Uninstall removes owned, unchanged
entries and skills; conflicts preserve the installation for review and retry.
Without a manifest, uninstall reports that there was nothing to remove.
Task state and receipts remain available after uninstall.

## Storage and limits

The project-local `.trailbun` runtime directory contains `state.json`,
write-once receipt files, installation manifests, minimal hook invocation
records and archived task states. Receipts are written once by `verify` and
never rewritten by Trailbun; any process with write access to the worktree,
including the agent's shell, can alter them, which is why `check` prints the
latest receipt's SHA-256 and each invocation record carries the state digest.
Linked worktrees have separate task state. The exact local exclude entries are
retained with the evidence after uninstall. Existing unowned runtime
directories are refused. Task-state writes use an atomic replacement and a
lock; busy or corrupt state is an explicit error. State has a 1 MiB bound.

Ignored files are excluded unless listed in the contract's `watch_ignored`.
Retained output is bounded to 16 KiB per check. Before truncation, Trailbun
redacts environment values whose names look like secrets, bearer and basic
authorization values, AWS access key IDs, OpenAI, GitHub and Slack token
shapes, JSON Web Tokens, PEM private keys, credentials inside URLs, and the
home and repository paths. Review receipts before sharing: arbitrary sensitive
content is not guaranteed to be recognized. A timeout stops the direct check
process; commands that spawn detached descendants need their own cleanup.
Filesystem inspection cannot attest external services or every transient write
between observations.

CLI JSON is schema version 1. Exit `0` means the operation is OK, `1` means a
violation, and `2` means incomplete or error. Inspect `completion` and
`verification_current` on `check`; operation success is not task completion.
Native hooks use their host's JSON protocol and exit separately.

Protocol references: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude Code hooks](https://code.claude.com/docs/en/hooks),
[Claude Code permissions](https://code.claude.com/docs/en/permissions),
[Python subprocess](https://docs.python.org/3/library/subprocess.html).
Host behavior statements in this document were checked on 2026-09-09 against
Codex 0.153.4 and Claude Code 2.1.263 documentation.

The runtime deliberately lives outside `.git`: Codex's Windows workspace
sandbox protects Git metadata and cannot reopen a writable child directory
inside it. See the [validated design correction](../notes/IMPLEMENTATION.md#validated-design-correction).

## Windows environment checks

Before a real task, confirm that the host can run the installed interpreter and
`trailbun --version`. A virtual environment still depends on its base Python.
In the recorded validation, an environment backed by a private uv-managed
Python failed inside the sandbox; a separate environment based on the existing
system Python resolved that interpreter error. The Codex Windows wrapper now
prints a `systemMessage` when the interpreter is missing instead of an empty
success. Choose an interpreter the host can read rather than broadening
filesystem permissions.

The benchmark runner explicitly selects the existing elevated Windows sandbox
when ignoring user configuration. This is a process-local setting; it does not
modify `~/.codex/config.toml`. Normal interactive setup follows the
[official Windows sandbox instructions](https://learn.chatgpt.com/docs/windows/windows-sandbox).
The [evidence register](EVIDENCE.md) records interpreter, ACL and hook-discovery
failures separately; a successful CLI invocation alone is not native protection.
