# Controlled study results

All 12 recorded runs passed functional acceptance. The overall artifact score below is 9/12: three plain runs added `DIAGNOSIS.md` outside the predefined artifact set. The generic plain workflow instructions mention that file, so this difference is sensitive to prompt wording and does not establish better engineering or reduced drift. Read the [methodology and limitations](NOTES.md) before comparing conditions.

Recorded 12 of 24 runs (16 host sessions); 12 runs are missing. Task success: 9 recorded runs. Policy rejection messages occurred in 0 runs. Timeouts: 0. Runner or export errors: 0 runs.

Diagnostic outcomes only; no efficacy estimate. Missing model/cost is unknown. Process completion is separate from acceptance. Summed session times are not elapsed experiment time when tasks run concurrently.

Requested models: gpt-6-astra. Host-reported model IDs: not disclosed.

Sum of session durations: 1125.159 s. Reported cost: not disclosed.

Reported usage totals (fields retain the host names and may overlap):

```json
{
  "input_tokens": 2689374,
  "cached_input_tokens": 2353152,
  "cache_write_input_tokens": 0,
  "output_tokens": 20903,
  "reasoning_output_tokens": 647
}
```

| Cell | Process | Acceptance | Overall task | Extra paths | Runner/export error | Policy rejections | Sessions | Seconds |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |
| claude-scope-plain-1 | not run | — | — | — | — | — | — | — |
| claude-scope-trailbun-1 | not run | — | — | — | — | — | — | — |
| claude-scope-plain-2 | not run | — | — | — | — | — | — | — |
| claude-scope-trailbun-2 | not run | — | — | — | — | — | — | — |
| claude-resume-plain-1 | not run | — | — | — | — | — | — | — |
| claude-resume-trailbun-1 | not run | — | — | — | — | — | — | — |
| claude-resume-plain-2 | not run | — | — | — | — | — | — | — |
| claude-resume-trailbun-2 | not run | — | — | — | — | — | — | — |
| claude-recovery-plain-1 | not run | — | — | — | — | — | — | — |
| claude-recovery-trailbun-1 | not run | — | — | — | — | — | — | — |
| claude-recovery-plain-2 | not run | — | — | — | — | — | — | — |
| claude-recovery-trailbun-2 | not run | — | — | — | — | — | — | — |
| [codex-scope-plain-1](codex-scope-plain-1/run.json) | completed | pass | fail | DIAGNOSIS.md | none | 0 | 1 | 75.735 |
| [codex-scope-trailbun-1](codex-scope-trailbun-1/run.json) | completed | pass | pass | none | none | 0 | 1 | 82.093 |
| [codex-scope-plain-2](codex-scope-plain-2/run.json) | completed | pass | pass | none | none | 0 | 1 | 65.391 |
| [codex-scope-trailbun-2](codex-scope-trailbun-2/run.json) | completed | pass | pass | none | none | 0 | 1 | 84.688 |
| [codex-resume-plain-1](codex-resume-plain-1/run.json) | completed | pass | fail | DIAGNOSIS.md | none | 0 | 2 | 112.954 |
| [codex-resume-trailbun-1](codex-resume-trailbun-1/run.json) | completed | pass | pass | none | none | 0 | 2 | 113.046 |
| [codex-resume-plain-2](codex-resume-plain-2/run.json) | completed | pass | fail | DIAGNOSIS.md | none | 0 | 2 | 126.767 |
| [codex-resume-trailbun-2](codex-resume-trailbun-2/run.json) | completed | pass | pass | none | none | 0 | 2 | 103.766 |
| [codex-recovery-plain-1](codex-recovery-plain-1/run.json) | completed | pass | pass | none | none | 0 | 1 | 89.078 |
| [codex-recovery-trailbun-1](codex-recovery-trailbun-1/run.json) | completed | pass | pass | none | none | 0 | 1 | 89.188 |
| [codex-recovery-plain-2](codex-recovery-plain-2/run.json) | completed | pass | pass | none | none | 0 | 1 | 86.344 |
| [codex-recovery-trailbun-2](codex-recovery-trailbun-2/run.json) | completed | pass | pass | none | none | 0 | 1 | 96.109 |
