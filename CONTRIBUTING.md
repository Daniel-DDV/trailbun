# Contributing

Contributions are in English and strengthen one specific claim.

## The most useful contribution: a failure with a receipt

Trailbun is only as good as the detours it catches. Open an issue with the
[useful failure template](.github/ISSUE_TEMPLATE/useful-failure.md) and fill in:

1. The intended task: the contract you used, or the goal and allowed paths.
2. What actually happened: the command, the exit code, the hook output or the
   receipt, and the paths that changed. `trailbun check --json` and the files in
   `.trailbun/` carry most of this; redact anything private before pasting.
3. The host and version (`codex --version`, `claude --version`), the operating
   system and the Trailbun version.
4. The next check that would have caught it, if you can name one.

A valid task that needed a wider scope than the contract allowed is as useful
as a detour that slipped through.

## Code changes

1. Pick one claim from the [claims table](docs/EVIDENCE.md#claims). ASSERTED
   claims want a mechanism or a receipt; MEASURED claims want a stronger
   measurement.
2. Add a deterministic test for every executable change. The suite runs on
   Windows, Ubuntu and macOS; PowerShell-backed Windows tests take the
   `windows_acl` marker.
3. Run `uv run pytest -ra` and `uv run ruff check .` before opening the pull
   request. Keep commits small and scoped to one behavior.
4. Document scope, host and version assumptions, bypass paths and failure
   modes in the pull request, following the [Receipt Card](docs/RECEIPT.md).
5. After a host upgrade, rerun `scripts/native_smoke.py` and
   `scripts/native_compact.py` before changing any host-behavior sentence, and
   date the sentence.

Do not broaden claims beyond the supplied evidence, and do not weaken a test,
acceptance criterion or status label to make a change pass. A smaller honest
claim is preferable to a universal claim supported by one successful run. The
[Nine Laws](docs/LAWS.md) explain why.

## Copy

Plain sentences. No em-dashes. State a limit as its own sentence rather than
as a contrast. No three-beat slogans in text or images. Every sentence about
behavior describes something shipped or is marked as pending.
