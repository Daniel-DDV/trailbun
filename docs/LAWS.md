# The Nine Laws

## 1. Define work before execution
State intent, exclusions, acceptance criteria, evidence, and stop conditions before the agent changes anything.

## 2. Context is a degrading budget
Load the smallest high-signal context required for the next decision. Reinject durable state after compaction and isolate independent review.

## 3. Permission text is not a boundary
Prompts advise. Sandboxes, permissions, hooks, wrappers, and CI constrain. Document uncovered paths.

## 4. Every run needs budgets
Cap time, retries, context, changed files, and side effects. A budget without a stop mechanism is a suggestion.

## 5. Output is not evidence
Judge the artifact with independent checks. Preserve the exact command, result, environment, and limitations.

## 6. Autonomy follows recoverability
Increase autonomy only when actions are observable, bounded, reversible, and attributable.

## 7. Builders do not grade themselves
Give a fresh-context reviewer the artifact and acceptance criteria, not the builder's narrative. Withhold repair tools when the role is review-only.

## 8. Promote repeated lessons into mechanisms
Move recurring uncertainty into the narrowest durable control: instruction, skill, wrapper, hook, test, or policy.

## 9. Audit the setup before trusting it
Verify discovery, precedence, permissions, exit behavior, failure modes, and bypass paths on the named host and version.
