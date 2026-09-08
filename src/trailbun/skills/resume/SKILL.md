---
name: trailbun-resume
description: Explicitly restore a saved Trailbun task and bind this session to it.
disable-model-invocation: true
---

Run `trailbun resume` with the host/session binding shown by SessionStart. Read
the restored goal, scope, checkpoint, open findings and verification status
before editing. Do not treat a saved completion claim as fresh evidence.

If the user's current request changes the outcome or allowed paths, explain the
change and use `trailbun amend` explicitly. Do not silently expand scope or reset
the baseline. Missing or corrupt state requires an actionable report, not an
invented task. A different session remains unguarded until explicitly bound.
