# Initial Windows study batch

On 2026-09-08, 11 Codex cells started before the repeated execution-policy block
was diagnosed. Every started cell is retained, including failures. Three task
streams ran concurrently. Within each task, repeat 1 ordered plain then
Trailbun; repeat 2 ordered Trailbun then plain. The final resume/plain/repeat 2
cell was stopped before starting. Claude was not authenticated, so its 12 cells
were not run. No cell was rerun in this batch.

All 11 recorded cells failed original task acceptance and contained host tool
rejections. A process exit of zero means the host finished responding; it does
not mean the task was completed. Recovery's existing changed file came from the
two documented harness-seeded corrections, not successful model work. These
results establish an environment problem and support no product efficacy claim.

The exact original arguments are in every `run.json`. The initial harness used
`--ignore-user-config --sandbox workspace-write` without restoring the Windows
`windows.sandbox` setting. The original Trailbun runtime and contract were under
`.git`. Later source changes must not be confused with this initial batch.

The separate `windows-preflight/` contains one authorized model call with the
documented process-only `-c windows.sandbox="elevated"`. Host tools read and wrote
the ordinary fixture successfully and reported a successful byte check. The
independent parent read then raised `PermissionError`, so independent content
verification is unknown. Its receipt explicitly records that error and missing
duration. This preflight is excluded from the 24-cell matrix and matrix usage
totals; its own reported usage is retained in its receipt.

`windows-debug.json` is a no-model permission-render receipt. Debug cannot use
the same `--ignore-user-config` switch as `exec`, so it is limited evidence.
No sandbox bypass was used. A later configuration review found that the writable
preflight automatically caused Codex to persist trust for its temporary project
in user configuration. The preflight's original no-change metadata was incorrect
and has been corrected. No before/after configuration hash was captured for this
batch, so configuration invariance cannot be established retrospectively. The
underlying [thread-start source](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/app-server/src/request_processors/thread_processor.rs#L1334)
persists trust when the cwd is writable and project trust is unspecified.

After export, nested escaped source paths in 10 stderr files received an
additional privacy redaction. Error messages and outcome data were preserved.
No raw credential values or unredacted local paths are needed to reproduce the
failure. See the [harness](../../benchmarks/README.md) and official
[Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox).
