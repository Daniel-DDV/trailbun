## 0.2.1: review fixes

Changes from an adversarially verified review of 0.2.0 (five reviewers, each
followed by a verifier that tried to refute every finding, then a completeness
critic). The full list with review IDs is in `CHANGELOG.md`.

### What changes for a user

- `setup` then `start` works on a fresh clone. Claude hooks go to
  `.claude/settings.local.json` by default (`--shared` for the committed
  file); generated files are excluded through the Trailbun block in
  `.git/info/exclude`; setup prints the next command.
- Hooks carry matchers, so reads and searches no longer spawn the handler;
  the timeout is 60 seconds; the Codex Windows wrapper reports a missing
  interpreter; `doctor --probe` starts the handler.
- A rewritten baseline is an explicit error with two recovery commands, and
  `amend --rebaseline` records the new baseline.
- Staging or committing the same failed correction is one attempt; an
  unchanged contract cannot be amended; amendments, abandonment and diagnosis
  record the calling command and are disclosed in the Stop reason, resume
  context and `check` text as recorded, never enforced.
- Host configuration files are denied under a broad scope; Claude setup adds
  `Edit(...)` deny rules for `.trailbun` and the settings files.
- Every command has help text; default output is text; `.cmd` checks run on
  Windows; UTF-8 output; receipts redact secret shapes and paths before
  truncation and list files changed during checks.

### Tests and CI

- 35 regression tests in `tests/test_regressions.py`, one per finding; setup
  tests run against a real repository. Local run: 174 passed, 1 skipped, on
  Windows 11 / Python 3.12, including the ACL tests.
- CI: lint job, test matrix without the ACL tests, dedicated `windows-acl`
  job, concurrency group, push filter, pinned actions, Dependabot.
- Release workflow with the committed validation generator, provenance
  attestation and PyPI trusted publishing (needs the PyPI publisher and the
  `pypi` environment configured first; see `notes/RELEASE_CHECKLIST.md`).

### Docs

- README leads with the Codex router rejection, names both hosts, one status
  box, one limits section. Claims table in `docs/EVIDENCE.md`. Glossary,
  "Who does what" and the exact hook strings in `docs/USAGE.md`.
  `field-manual/`, `playbook/`, `templates/` folded under `docs/`;
  IMPLEMENTATION and LAUNCH moved to `notes/`.
- New 8-second demo GIF and final frame rendered from the CLI's own text;
  WebP heroes; 1280 by 640 social preview.

### Not in this PR

The live Claude Code probe, incremental inspection, submodule handling and
the study redesign are Phase 1 and 2 items; they are listed as pending in the
changelog and in the release checklist.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
