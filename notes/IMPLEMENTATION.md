# Trailbun implementation contract

Trailbun keeps an explicit task, scope, checkpoints and verification receipts per
Git worktree. It restores compact task context, reports artifact drift from a
fixed baseline, and intervenes only on tested native tool paths. Success means a
working Python distribution, deterministic regression coverage, real host
receipts, a reproducible demo and honest measured results. It is not a sandbox.

Brand: **Trailbun. Keep your agent on the trail.** English throughout.

## Delivery order

1. Repair the existing text scanner and establish packaging/CI.
2. Implement contract, Git checks, serialized state and checkpoints.
3. Implement verification, diagnosis, CLI and isolated demo.
4. Integrate Claude Code and Codex with reversible project-local setup.
5. Add original rabbit artwork, documentation, recorded demo and evidence.
6. Independently review, run release checks, rename the repository and release 0.2.0.

Each executable slice needs a failing regression, implementation and passing
verification. Reviewers report correctness/requirements gaps, not speculative
features. Keep commits small and scope them to one behavior.

## Public behavior

- Commands: start, amend, checkpoint, resume, check, verify, diagnose, doctor,
  setup, uninstall, demo. JSON output is versioned; 0=ok, 1=violation,
  2=incomplete/error. Native hooks translate these outcomes to host JSON.
- One active task per worktree; runtime data lives in an owned, locally ignored
  `.trailbun` directory. Start requires a clean worktree. Never automatically stash/reset.
- Contract: goal, exclusions, allowed file/directory paths, acceptance checks,
  and an optional explicitly declared expected-red check. Amend retains baseline.
- Check staged/unstaged/committed/untracked paths; watched ignored paths are
  explicit. Scopes have no glob syntax. Resolve symlinks and both rename ends.
- Receipts bind contract revision, check definitions and actual artifact contents.
  Changes during or after verification invalidate completion.
- Two distinct failed corrective artifacts for the same check trigger diagnosis;
  duplicate notifications and explicitly declared initial TDD red do not count.
- Session restoration is explicit. Unbound sessions have no active guard.
- Stop emits at most one reminder per completion chain, leaving task incomplete.
- No shell-language policy engine, daemon, database, model calls in hooks or
  global configuration edits. Grok is deferred.

## Evidence

Core CI: Windows/Linux/macOS, Python 3.11–3.14. Live host coverage is separately
reported by exact host/version/OS and requires an actual rejected write.
Study: 3 tasks x 2 repeats x 2 hosts x 2 conditions = 24 runs. Publish all outcomes.
Top risks: false enforcement claims from hook failure/bypasses; stale receipts
passing after the checked artifact changes. Both require regression fixtures.

## Grounding

- https://learn.chatgpt.com/docs/hooks
- https://code.claude.com/docs/en/hooks
- https://git-scm.com/docs/git-diff
- https://git-scm.com/docs/git-ls-files
- https://setuptools.pypa.io/en/stable/userguide/package_discovery.html
- https://www.trychroma.com/research/context-rot
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## Validated design correction

The initial design placed runtime state below `.git`. Live Windows validation
and the tagged Codex source showed that its normal workspace sandbox protects
Git metadata and rejects writable child exceptions. Runtime therefore moves to
an owned `.trailbun` directory per worktree, excluded locally during external
setup. Scope checks also protect this runtime directory. This preserves normal
Git-metadata protection; it does not require broader sandbox permissions.
[Codex Windows sandbox implementation, 0.153.4](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/sandboxing/src/windows.rs)
