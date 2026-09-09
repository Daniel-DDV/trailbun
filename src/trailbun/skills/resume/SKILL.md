---
name: trailbun-resume
description: Explicitly restore a saved Trailbun task and bind this session to it.
disable-model-invocation: true
---

Run `trailbun resume` with the host and session binding shown by SessionStart:
`trailbun resume --host claude|codex --session SESSION_ID`. Read the restored
goal, scope, checkpoint, contract revision, open findings and verification
status before editing. Do not treat a saved completion claim as fresh evidence;
the context names the latest receipt and its digest so you can check it.

If the user's current request changes the outcome or allowed paths, explain
the change and use `trailbun amend --reason "..."` explicitly. An amendment is
recorded with its reason and the command that made it; it is not blocked, so
state it to the user. Do not silently expand scope. Do not pass `--rebaseline`
unless the task's starting commit was rewritten and the user has reviewed the
commits in between. Missing or corrupt state requires an actionable report,
not an invented task. A different session remains unguarded until explicitly
bound.
