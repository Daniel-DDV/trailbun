# Changelog

## 0.2.1 (unreleased): review fixes

Changes from an adversarially verified review of 0.2.0. Each item names the
review finding it resolves; the findings themselves are listed in the
0.3.0 milestone once filed.

### Guard integrity and disclosure

- `amend`, `start --abandon-reason` and `diagnose` record the calling command,
  working directory, timestamp and host environment markers. The Stop reason,
  resume context and `check` text show the contract revision, the amendment
  count and the last reason, labelled recorded rather than enforced (A1).
- `check` and the Stop reason print the latest receipt's SHA-256; every hook
  invocation record carries the state digest; receipts are documented as
  write-once, with a sentence on who can alter them (A2).
- Host configuration files and installed skills are denied under a broad scope
  unless an allowed path names them exactly. `doctor` reads `disableAllHooks`
  from user, project and local settings with local precedence and names the
  file. The Stop hook compares the live hook configuration with the manifest
  and reports a difference (A3).
- Claude setup adds `Edit(...)` deny rules for `.trailbun/**` and the two
  settings files, recorded in the manifest and removed by uninstall (A4).
- A rewritten or unreachable baseline is an explicit error naming the two
  recovery commands; the Stop hook blocks once with that error; `amend
  --rebaseline` records HEAD as the new baseline and keeps the old one in the
  contract history (A5).
- The failure counter keys on file contents, so staging or committing the
  same failed correction is one attempt (A6).
- `amend` refuses a contract identical to the current one and resets only
  counters whose check definition changed (A7).
- A diagnosis for a blocked check needs a receipt whose status is `violation`
  or a file inside the worktree; the evidence kind and blocked checks are
  recorded (A8).
- The Codex Windows wrapper prints a `systemMessage` when the interpreter is
  missing instead of an empty success; `doctor --probe` starts the installed
  handler with a synthetic SessionStart payload (A9).
- Git, the host binaries and check commands resolve through PATH and PATHEXT
  only, never the working directory (A10).
- NotebookEdit is inspected through its documented `notebook_path` field (A11).

### Performance

- Installed hook groups carry matchers: Claude Code Edit, Write, NotebookEdit
  and Bash; Codex `apply_patch` on PreToolUse. The Git directory lookup is
  hoisted out of the per-path scope check, `verify` hashes the tree twice
  instead of four times, the runtime tracking check lists only `.trailbun`,
  and the installed hook timeout is 60 seconds (B1, first pass).

### First hour

- `setup` then `start` works: Claude hooks go to `.claude/settings.local.json`
  by default with `--shared` for the committed file, generated files are
  excluded through the Trailbun block in `.git/info/exclude` and recorded in
  the manifest, and setup prints the next command with the session flag (C1).
- Every command and option has help text; `start --help` and `amend --help`
  show a minimal contract, the path rules and the exit codes (C2).
- One contract location: `.trailbun/task.json` after setup, or `--contract -`
  before (C3).
- `amend`, `checkpoint` and `diagnose` refuse before creating the runtime when
  no task exists (C4).
- Error messages list the offending paths and a fix; missing or invalid
  contract files and corrupt state are messages, not tracebacks; `--export` is
  validated before state changes; hypotheses are deduplicated (C5).
- `check`, `verify`, `demo`, `doctor` and `setup` print text by default;
  `--json` keeps the full result (C6).
- USAGE has a "Who does what" list and the exact strings the agent sees (C7).
- `.cmd` and `.bat` checks run through `cmd.exe` on Windows and the receipt
  records `resolved_executable` (C8).
- stdout and stderr are reconfigured to UTF-8, so `resume` no longer crashes on
  a non-cp1252 character in a pipe (C9).
- Receipts list `changed_during_checks` (C10).
- `hook` is documented as host-invoked; `uninstall` without a manifest says so;
  `--json` is not offered on `hook` (C13).

### Privacy

- Receipts redact bearer and basic authorization values, AWS access key IDs,
  OpenAI, GitHub and Slack token shapes, JSON Web Tokens, PEM private keys,
  credentials inside URLs, secret-looking environment values and the home and
  repository paths, before truncation (D1).

### Tests, CI, packaging, release

- Windows ACL tests carry the `windows_acl` marker and run in a dedicated job;
  CI runs on pushes to `main` and tags, and on pull requests, with a
  concurrency group, `uv sync --locked`, ruff, coverage and per-test durations;
  actions are pinned by commit and updated by Dependabot (E1, E3).
- The version lives in `trailbun/__init__.py` only; the `resources` glob is
  gone; a release workflow builds, replays the tests from the source archive,
  writes `release-validation.json` and `SHA256SUMS` with the committed
  generator, attests provenance and publishes to PyPI through trusted
  publishing (E3).
- Setup tests run against a real repository; 35 regression tests cover the
  review findings (E2, first pass).
- The text scanner `checks/hook_exit_audit.py` and its tests are removed (E4).
- Hero images ship as WebP in the README `picture` element, the PNG originals
  stay, the social preview is a 1280 by 640 JPEG, and asset provenance names
  the generator recorded in the files (E5).

### Evidence and docs

- A claims table labels every claim ASSERTED, ENFORCED or MEASURED; the study
  label reads "acceptance and exact artifact set"; host-behavior sentences are
  dated; the GIF is described as rendered (F1, F2, F3, F6).
- Glossary in USAGE; inline definitions in the README (F4).
- `field-manual/`, `playbook/` and `templates/` moved under `docs/`;
  IMPLEMENTATION and LAUNCH moved to `notes/`; `evidence/README.md` describes
  each retained directory (F5).
- Em-dashes, contrast constructions and slogan triplets removed; the voice
  rule is in BRAND.md (F7).
- README opens with the Codex router rejection and names both hosts; one
  status box; one "What it does not do" section; the table leads with stale
  receipts and baseline drift and names the plain task file it must beat
  (G1, G2, G6, G7).
- Shorter demo GIF rendered from the text renderer output; static final frame;
  topics and badges follow once main is green (G3, G4, G8).

### Pending

- Live Claude Code probe (G2, Phase 1). The README's Claude row changes only
  after receipts exist.
- Incremental inspection from `git status --porcelain=v2` (B1, second pass).
- PyPI registration of the name, tag signing, rulesets and immutable releases
  are repository settings outside this changelog.

## 0.2.0: Trailbun preview

The evidence-first handbook becomes an executable task workflow: Trailbun,
keep your agent on the trail. Existing laws and receipt templates remain
available.

- Add per-worktree task contracts, fixed-baseline scope inspection, compact
  checkpoints and explicit amendments.
- Bind verification receipts to check definitions and actual artifact contents;
  retain failed and incomplete checks as evidence.
- Require evidence-backed diagnosis after repeated failed corrections.
- Add explicit session binding and reversible project-local Claude Code/Codex
  adapters, with bounded stop reminders and documented coverage limits.
- Ship an installable Python CLI, three bundled skills, regression tests,
  cross-platform CI, an isolated demo and reproducible measurement scripts.
- Add original rabbit artwork, terminal demo and source-grounded research notes.
- Retain live Codex patch-rejection and manual-compaction receipts, twelve
  controlled Codex workflow runs, and explicit gaps for unauthenticated Claude.
- Make scanner read failures and empty inputs explicit (the scanner was removed
  in 0.2.1).

See the [evidence register](docs/EVIDENCE.md) for tested versions, live outcomes
and remaining gaps. No general agent-effectiveness percentage is claimed.
