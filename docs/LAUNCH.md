# Trailbun launch copy

Prepared copy, not a record of messages sent. Use after the release command works
from a clean environment and the linked [evidence](EVIDENCE.md) is published.
Read the actual results before adding any performance claim.

## Short announcement

Your agent started with a bug fix. It is now designing a framework.

I built **Trailbun** to keep the original task in view: compact checkpoints,
Git scope checks, evidence tied to the current files, and a fresh start when
another speculative patch is not helping.

It has a slightly tired rabbit. It also has a demo you can run:

```sh
uvx --from git+https://github.com/Daniel-DDV/trailbun@v0.2.0 trailbun demo
```

That demo exercises a real temporary Git repository. It is a deterministic
demonstration, not an AI benchmark. Native coverage and measurements are reported
separately, with receipts and the gaps left visible.

**Trailbun — Keep your agent on the trail.**

[Repository](https://github.com/Daniel-DDV/trailbun)

## Show HN draft

Title: **Show HN: Trailbun — checkpoints and drift checks for AI coding agents**

I kept seeing the same failure: an agent had a reasonable plan, hit a difficult
bug, and gradually started solving a larger, different problem.

Trailbun stores a small task contract outside the conversation and compares the
actual artifact with the baseline from task start. That includes already
committed work. It can restore a compact handoff and makes passing verification
stale when the checked files or contract change. A repeated correction needs
new evidence, not just a third variation of the same patch.

The README has a local demo, project-local setup for Claude Code and Codex, and
an evidence register that distinguishes core tests from actual host behavior.
It is not a sandbox, and file-scope checks cannot prove semantic alignment.

I would particularly value small reproductions where the intervention was
unhelpful or where a valid task needed a wider scope. Those are useful inputs
for the next version.

## Release description

Trailbun 0.2.0 turns the original evidence-first field manual into a task
continuity tool: contracts, checkpoints, baseline-aware artifact checks,
verification receipts and bounded diagnosis. It adds explicit project-local
Claude Code and Codex integration, an isolated demonstration and the Trailbun
rabbit identity.

Include links to the exact release validation and host receipts. State any
unverified platforms or incomplete study runs directly. Do not describe a
planned matrix as completed test coverage.

## Assets and follow-through

- Pair the announcement with [social-preview.png](../assets/social-preview.png).
- Pair the first technical follow-up with the real recorded demo and its JSON.
- Publish one complete failure receipt before asking others to contribute one.
- Report corrections as clearly as improvements; retain the earlier claim and
  explain what the better measurement changed.
- Use the published repo URL consistently after the rename.

Assess distribution with observable results: visits to the repository, demo
reproductions reported by users, actionable issues and returning contributors.
Stars are a useful secondary signal; the project makes no promise of virality.
