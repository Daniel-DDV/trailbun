---
name: Useful failure
about: A detour Trailbun missed, a valid task it blocked, or a receipt that was wrong
title: ""
labels: failure-receipt
---

## Claim being tested

One sentence. Example: "An out-of-scope shell write is reported by the next check."

## Status you observed

`ASSERTED | ENFORCED | MEASURED` as documented, and what actually happened.

## Scope

- Trailbun version (`trailbun --version`):
- Host and version (`codex --version` or `claude --version`):
- Operating system:
- Contract (goal, allowed paths, checks), redacted as needed:

## Procedure

```text
Exact commands or steps, in order
```

## Result

Exit codes, the hook output or the receipt, the paths that changed. Attach
`trailbun check --json` and the relevant `.trailbun/receipts/*.json` if you
can; redact anything private first.

## Missing receipts

What you could not capture, and any bypass path you suspect.

## Next check

The smallest test or mechanism that would have caught this.
