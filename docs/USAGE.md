# Use Trailbun

Trailbun keeps one task per Git worktree. Start from a committed baseline, write
down the intended change, and verify the resulting files against named checks.
The CLI also works without a coding-agent integration.

## Start a task

Install the CLI as shown in the [README](../README.md). Save this example as
`../redirect-task.json`, outside the project. Adapt the paths and check command
to your project before executing it:

```json
{
  "goal": "Redirect signed-out users to /login without changing signed-in behavior",
  "exclusions": ["No new authentication framework", "No dependency changes"],
  "allowed_paths": ["src/redirect.py", "tests/test_redirect.py"],
  "checks": [
    {
      "id": "redirect",
      "argv": ["python", "-m", "pytest", "tests/test_redirect.py", "-q"],
      "timeout_seconds": 60
    }
  ]
}
```

```sh
git status --short
trailbun start --contract ../redirect-task.json --project .
trailbun check --project .
```

`start` refuses a dirty worktree. Commit or isolate existing work yourself.
Paths are repository-relative literal files or directories, with no wildcards.
`.` permits the project tree; use narrower paths when the task permits it.
Git metadata and paths escaping the project are excluded. Submodules and
unsupported artifact types produce an incomplete result.

Checks are argument arrays executed in the repository root, without an implicit
shell. Use the interpreter/environment that has your project's test dependencies.
Timeouts default to 60 seconds and may range from 1 to 600 seconds.

## Save and restore progress

```sh
trailbun checkpoint --summary "Found the fallback redirect in src/redirect.py" --next-action "Add a signed-out regression and fix the fallback"
trailbun resume
```

Add `--failed-hypothesis "The session cookie was not the cause"` to retain a
disproven hypothesis. This flag is repeatable. A checkpoint changes progress;
it does not change the task's scope or acceptance checks.

`resume` prints the goal, scope, exclusions, checks, progress, hypotheses and
verification status. `--export ../handoff.txt` writes a new file without
overwriting an existing one. Supply that text to a fresh session. Updates that
would exceed 6 KiB of resume context are rejected; submit a shorter update.

## Verify, amend and diagnose

```sh
trailbun check
trailbun verify --json
```

`check` compares committed, staged, unstaged and untracked paths with the fixed
starting commit. `verify` first checks scope, then executes all contracted
checks. A receipt records the commands, bounded output, exit status, duration,
contract revision and artifact fingerprints. Changed check definitions or file
contents make the previous receipt stale. Changes during verification yield an
incomplete receipt. A scope match alone does not establish completion.

For deliberate TDD, declare `"expected_red": ["redirect"]` in the contract and
run `trailbun verify --baseline` before editing. This is a one-time declaration
of the expected initial failures; it is not a passing completion receipt.

When inspection reveals a necessary scope change, edit the external contract:

```sh
trailbun amend --contract ../redirect-task.json --reason "The redirect is selected in src/routes.py; include that exact file"
```

Amendments retain the original Git baseline and record the previous contract.
They invalidate verification and restart failure counters for the revised checks.

Two distinct failed corrective artifacts for one check require diagnosis.
Repeating the same failed artifact does not increment the counter. A diagnosis
must name a nonempty local evidence file or a retained `receipt:<id>`:

```sh
trailbun diagnose --reproduction "Run the redirect check with a signed-out request" --cause "The fallback is chosen before the authentication branch" --evidence ../redirect-reproduction.txt --next-action "Move fallback selection after the branch and rerun the regression"
```

Trailbun records the evidence hash and retains the previous failure counters.
The diagnosis allows a new correction budget; reusing the same evidence cannot
reset it repeatedly. A hash establishes that evidence exists, not that the
proposed cause is correct. Check the diagnosis before acting on it.

A new task may replace a verified, clean task. To deliberately abandon an
incomplete one, use `start --abandon-reason "..."`; the previous run is archived.
Trailbun never stashes, resets or commits your work.

## Native sessions

```sh
trailbun setup --host codex
# Or: trailbun setup --host claude
```

Setup adds project-local hook definitions and three small skills. Review the
generated files and restart the host. Codex requires review/trust of hook
definitions through its native workflow. Setup does not edit global settings.
The generated command points to the installed Python environment; rerun setup
after moving that environment.

Installation files participate in Git's normal cleanliness rules. Before
starting a task, inspect `git status --short`. Keep machine-specific untracked
installation files local using the project's usual ignore policy or Git's local
`info/exclude`; do not blanket-ignore source files to obtain a clean result.
Existing tracked configuration changes need normal review and a commit.

The session-start hook supplies the current session ID. Explicitly bind it:

```sh
trailbun resume --host codex --session SESSION_ID
# Or use start --contract ../redirect-task.json --host codex --session SESSION_ID
```

Use `--host claude` in Claude Code. An unbound session has no active guard.
Compaction/resumption reinjection depends on the host preserving the bound
session and actually invoking its hooks. A new or cleared session needs an
explicit binding.

Known native write targets outside scope are denied. Shell and other unknown
mutations may only be observed afterward; hooks cannot undo them. Completion
requests without current evidence get at most one continuation reminder per
stop chain. Hooks never execute acceptance tests or launch another model.

```sh
trailbun doctor --host codex --json
trailbun uninstall --host codex
```

`doctor` distinguishes configured hooks and recorded invocations. Those facts
alone are not proof that a native write was blocked. Inspect the
[live evidence boundary](EVIDENCE.md). Uninstall removes owned, unchanged
entries and skills; conflicts preserve the installation for review and retry.
Task state and receipts remain available after uninstall.

## Storage and limits

Find the runtime directory with `git rev-parse --git-path trailbun`. It contains
`state.json`, immutable receipt files, installation manifests, minimal hook
invocation records and archived task states. Linked worktrees have separate task
state. Task-state writes use an atomic replacement and a lock; busy or corrupt state is an
explicit error. State has a 1 MiB bound.

Ignored files are excluded unless listed in the contract's `watch_ignored`.
Retained output is bounded to 16 KiB per check and redacts common environment
secret values and bearer tokens. Review receipts before sharing: arbitrary
sensitive content is not guaranteed to be recognized. Temporary output capture
can grow until the command exits or times out. A timeout stops the
direct check process; commands that spawn detached descendants need their own
cleanup. Filesystem inspection cannot attest external services or every
transient write between observations.

CLI JSON is schema version 1. Exit `0` means the operation is OK, `1` means a
violation, and `2` means incomplete/error. Inspect `completion` and
`verification_current` on `check`; operation success is not task completion.
Native hooks use their host's JSON protocol and exit separately.

Protocol references: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude Code hooks](https://code.claude.com/docs/en/hooks),
[Python subprocess](https://docs.python.org/3/library/subprocess.html).
