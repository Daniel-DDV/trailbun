# Windows setup correction gate

This batch contains only `codex-scope-plain-1`. It is separate from the initial
11-cell batch. The command adds the documented Windows `elevated` sandbox
setting and prepares the new `.trailbun` runtime outside the host session.

The model changed exactly the two authorized application files. Independent
original acceptance passed, protected files remained unchanged, and the artifact
export succeeded. Session duration was 64.422 seconds. There is no matching
Trailbun cell and no comparison result.

The prescribed virtual-environment interpreter could not start inside the
sandbox: its base Python lives under a user-profile installation. The model
reported the exact `No Python at ...` error and successfully used the available
system Python for acceptance instead. The missing `rg` command also led to a
normal PowerShell fallback; an independent model-review attempt failed to start.
All events are retained in `phase-1-stdout.jsonl` and `phase-1-stderr.txt`.

The operator stopped before the guarded cell because an inaccessible prescribed
interpreter would prevent the core Trailbun workflow. A later run with a changed
Python environment must retain its own configuration and cannot silently replace
this receipt or be presented as an identical paired comparison.

Codex automatically persisted this temporary project's trust in user
configuration; a later review detected that side effect. This run had no
before/after configuration hashes. Later runners use explicit process trust
and configuration fingerprints. No sandbox bypass was used. This is one passing
toy task and an installation diagnostic, not a product efficacy result.
