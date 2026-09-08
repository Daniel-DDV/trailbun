---
name: trailbun-start
description: Start an explicit Trailbun task with a goal, bounded scope and acceptance checks.
disable-model-invocation: true
---

Read the user's requested outcome and the project instructions. Agree a concise
goal, exclusions, allowed file/directory paths and executable acceptance checks.
Use `trailbun start --help` for the installed contract format. Start requires a
clean worktree; report existing changes without stashing, resetting or deleting.
Initial setup must create the owned `.trailbun` runtime and its local Git ignore
entry from an ordinary terminal before sandboxed use. If that bootstrap is
missing or blocked, report the required setup; do not relax Git protections.

Run start with the explicit host/session binding shown by the SessionStart hook:
`--host claude|codex --session SESSION_ID`. Do not invent a session ID or reuse one
from another conversation. If no session identifier was shown, explain that the
task can be recorded but native guards are not bound; use doctor to investigate.

Keep checkpoints current and invoke `trailbun verify` explicitly. Native hooks
cover only documented and tested tool paths; they are not a filesystem sandbox.
