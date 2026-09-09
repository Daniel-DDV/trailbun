# The 15-Minute Reality Check

Answer each question with `ASSERTED`, `ENFORCED`, or `MEASURED`, and attach a receipt.

1. Can the task be restated as observable outcomes, exclusions, and stop conditions?
2. Can the agent write outside the declared scope through any available tool or shell path?
3. What happens when a guard script is missing, times out, emits invalid output, or exits unexpectedly?
4. Does verification inspect committed changes as well as staged, unstaged, untracked, and relevant ignored files?
5. Is the reviewer isolated from the builder's context and unable to silently repair the artifact?
6. Can you reconstruct tool calls, retries, changed files, checks, duration, and stop reason without exposing secrets?
7. Has the same reference task been run with and without the mechanism, with the delta recorded?

## Decision

- Any unanswered question remains `ASSERTED`.
- A deterministic block may be `ENFORCED`, but only for documented paths.
- A reproducible observation with retained evidence may be `MEASURED`.
- Do not increase autonomy while critical claims remain asserted.
