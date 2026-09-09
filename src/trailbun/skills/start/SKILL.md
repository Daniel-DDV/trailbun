---
name: trailbun-start
description: Start an explicit Trailbun task with a goal, bounded scope and acceptance checks.
disable-model-invocation: true
---

Read the user's requested outcome and the project instructions. Agree a concise
goal, exclusions, allowed file or directory paths and executable acceptance
checks. `trailbun start --help` prints the installed contract format. The
contract is one JSON object:

```json
{
  "goal": "Redirect signed-out users to /login",
  "exclusions": ["No new authentication framework"],
  "allowed_paths": ["src/redirect.py", "tests/test_redirect.py"],
  "checks": [{"id": "redirect", "argv": ["python", "-m", "pytest", "tests/test_redirect.py", "-q", "-p", "no:cacheprovider"], "timeout_seconds": 60}],
  "expected_red": [],
  "watch_ignored": []
}
```

Fields: `goal` (required text); `allowed_paths` (required, repository-relative
files or directories, no wildcards, `.` means the whole tree); `checks` (1 to
32 entries with a simple unique `id`, an `argv` array run without a shell and
an optional `timeout_seconds` from 1 to 600); `exclusions`, `expected_red` and
`watch_ignored` are optional.

Write it to `.trailbun/task.json` after setup has created the runtime, or
pass it on stdin with `--contract -`. Do not write it elsewhere in the
repository: an untracked file blocks start and later counts as drift. If start
reports a dirty worktree, list the paths from `git status --short` and stop.
Do not stash, reset or delete. Initial setup must create the owned `.trailbun`
runtime and its local Git exclude entry from an ordinary terminal before
sandboxed use. If that bootstrap is missing or blocked, report the required
setup; do not relax Git protections.

Run start with the explicit host and session binding shown by the SessionStart
hook: `--host claude|codex --session SESSION_ID`. Do not invent a session ID or
reuse one from another conversation. If no session identifier was shown,
explain that the task can be recorded but native guards are not bound; use
`trailbun doctor --host <host> --probe` to investigate.

Keep checkpoints current and invoke `trailbun verify` explicitly. Native hooks
cover only documented and tested tool paths; they are not a filesystem sandbox.
