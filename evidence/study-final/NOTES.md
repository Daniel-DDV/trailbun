# Final controlled Codex workflow batch

This is a fresh batch after the retained installation diagnostics. Every cell
uses the same system-backed Python 3.12.10 environment, requested model
`gpt-6-astra`, Codex 0.153.4, a newly generated Git fixture, creator-only fixture
ACL provisioning on Windows, externally initialized `.trailbun` runtime,
process-only Windows sandbox selection and exact project-trust override.
No native hooks are installed in these workflow-study fixtures.

The scope pair for repeat 1 ran sequentially as infrastructure gates. Afterwards,
at most two streams ran concurrently: one completed scope repeat 2 and then
recovery, while the other completed resume. Within each task, repeat 1 ordered
plain then Trailbun; repeat 2 ordered Trailbun then plain. No failed cell is
silently replaced. A shared dispatcher stop flag prevents future cells after a
configuration/source change or unreadable runtime/export. Each host phase has
its original 120-second limit; timeouts remain recorded outcomes.

The plain and Trailbun conditions receive identical task requirements and
original acceptance checks. Their workflow instructions necessarily differ.
In particular, the generic plain instructions mention a diagnosis file for
recovery. A model may apply that instruction during initial test failure even
in the scope or resume task, producing `DIAGNOSIS.md` outside that fixture's predefined
artifact set. That metric is sensitive to our wording. An extra diagnostic
document is not by itself evidence of worse engineering or spontaneous drift.
Report functional acceptance, exact artifact policy and workflow compliance
separately; do not turn overall-score differences into an efficacy percentage.

The resume boundary is deliberately introduced and both conditions can read the
original acceptance file. Recovery failures are harness-seeded, with their real
outputs supplied equally to both conditions. These tasks establish whether the
instructed workflow can operate on small fixtures; they do not reproduce natural
context degradation or establish broad model reliability.

Each run records before/after source and user-configuration hashes. Configuration
contents are not exported. A configuration hash change after a phase prevents
the next session in that run. An unchanged hash establishes content invariance
at those observations, not that no file write of identical bytes ever occurred.
Read raw `run.json`, state and receipt files for exact coverage. Earlier probes
in the sibling directories retain their failures and observed side effects and
must not be pooled with this batch as identical repetitions.

Claude cells are unrun because the available Claude session was unauthenticated.
Their absence remains visible in the full 24-cell summary. These results do not
substitute for the separate native-hook rejection receipt.
