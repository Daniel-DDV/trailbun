---
name: trailbun-diagnose
description: Investigate repeated corrective failures before another Trailbun edit.
---

Inspect the failed acceptance check and retained evidence. State the observed
failure, the cause investigated and the next check that distinguishes competing
explanations. Use `trailbun diagnose --help` to record that diagnosis and the next
recovery step. Do not weaken acceptance checks merely to clear the failure state.
Pass `--evidence` an existing nonempty local diagnostic file or a retained
`receipt:<id>`. Trailbun hashes it and rejects previously used evidence; a new
claim alone does not reset the correction budget.

Use read-only inspection while diagnosis is pending. After diagnosis releases a
recovery attempt, make the smallest supported correction and verify explicitly.
If an external prerequisite is unavailable, report the task as incomplete.
