# Retained evidence

One line per entry. Files are retained byte for byte; several are failures kept
on purpose. The [evidence register](../docs/EVIDENCE.md) explains what each one
does and does not establish.

| Entry | What it is | Tag |
| --- | --- | --- |
| `native-codex-corrected-trust.*` | Codex 0.153.4 on Windows 11: permitted `apply_patch` succeeds, out-of-scope `apply_patch` rejected by the PreToolUse hook. Report, stream, stderr, probe script and offline reassessment. | live receipt |
| `native-codex-manual-compact.*` | Codex 0.153.4: manual compaction followed by the SessionStart hook returning the saved checkpoint. Report, filtered events and probe script. | live receipt |
| `native-codex.*` | First probe. The hook interpreter was missing, so the wrapper returned an empty success. | retained failure |
| `native-codex-system-python.*` | Second probe with a system Python. The trust override was ineffective. | retained failure |
| `native-config-probe.json` | Model-free check of Codex project trust resolution and hook discovery. | configuration probe |
| `demo/demo.json` | The deterministic demonstration output the GIF is rendered from. No model. | demonstration |
| `performance-1000*.json`, `performance-10000*.json` | Ten repeated inspections of 1,000 and 10,000 small files on 0.2.0; `-final` are the post-migration runs. | measurement |
| `study-final/` | Twelve Codex cells of the controlled workflow study, all passing acceptance in both conditions. Summary, notes, per-cell streams, receipts and artifacts. | study, null result |
| `study/` | First study batch. Every cell hit an execution-policy rejection before the workflow ran. | retained failure |
| `study-system-python/` | One cell with a system Python; runner export error. | retained failure |
| `study-windows-corrected/` | One cell after the Windows sandbox correction; used to validate the runner before the final batch. | retained failure |

Nothing in this directory is a Claude Code receipt. That probe has not run.
