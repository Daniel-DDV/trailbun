---
name: trailbun-diagnose
description: Investigate repeated corrective failures before another Trailbun edit.
---

Inspect the failed acceptance check and retained evidence. State the observed
failure, the cause investigated and the next check that distinguishes competing
explanations. Use `trailbun diagnose --help` to record that diagnosis and the
next recovery step. Do not weaken acceptance checks merely to clear the
failure state.

Pass `--evidence` a nonempty file inside the worktree (for example a saved
reproduction log under an allowed path) or a retained `receipt:<id>` whose
status is `violation`. Trailbun hashes it and rejects previously used
evidence, passing receipts and files outside the worktree while a check is
blocked; a new claim alone does not reset the correction budget. The diagnosis
is recorded with the command that made it and shown in later resume context.

Use read-only inspection while diagnosis is pending. After diagnosis releases a
recovery attempt, make the smallest supported correction and verify explicitly.
If an external prerequisite is unavailable, report the task as incomplete.
