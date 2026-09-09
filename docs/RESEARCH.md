# Research behind Trailbun

Reviewed 2026-09-08. This page records the evidence informing the design;
it does not substitute for measurements of Trailbun itself. Project results
belong in [EVIDENCE.md](EVIDENCE.md).

## The actual problem

The task starts clearly. Repeated fixes, tool output and compaction can leave the
agent with an incomplete picture of what it was meant to accomplish. The useful
response is to preserve the task and compare it with observable artifacts.

Chroma's July 2025 study evaluated 18 models on controlled long-context tasks.
Performance varied with input length, distractors and task construction; focused
inputs outperformed full histories in its LongMemEval comparison. This supports
testing compact relevant context. It does **not** establish a universal token
percentage or elapsed-time threshold for coding sessions. Its finding that
shuffled haystacks sometimes helped also cautions against treating well-organized
text as sufficient protection. [Chroma report and reproducible research](https://www.trychroma.com/research/context-rot)

Anthropic's long-running-agent experiments describe agents attempting too much
at once, leaving incomplete work for the next session and declaring completion
too early. Progress artifacts, incremental features and actual application
checks improved that particular harness. Trailbun adopts the operational idea
of a recoverable handoff and explicit verification. The study does not prove
that this implementation improves every host or workload; JSON's observed
resistance to inappropriate edits is not a security property.
[Anthropic engineering report](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

## Four claims that need different evidence

| Claim | What would substantiate it |
| --- | --- |
| The plan can be restored | A checkpoint/resume fixture reproducing the goal, constraints, evidence and next action. |
| Scope drift is detected | A Git fixture containing committed and working-tree changes, including rename and path edge cases. |
| A native action is blocked | A real host run showing the attempt, actual rejection, unchanged target and invocation receipt. |
| Agents perform better | Paired tasks with and without Trailbun, retained outcomes and host/model/version/sample limitations. |

These claims are independent. Restored text is not demonstrated model adherence.
A hook's JSON output is not demonstrated runtime enforcement. Passing acceptance
checks is not universal correctness.

## Why the artifact baseline matters

`git diff HEAD` concerns changes relative to the current commit. It cannot serve
as a complete record of work already committed since task start. Trailbun
therefore retains the task's original base commit and includes relevant
working-tree and index state. Untracked files need their own enumeration;
standard exclude rules also affect ignored files. Path handling and rename
coverage need executable fixtures. Assumptions about a convenient glob are not enough.
[git diff](https://git-scm.com/docs/git-diff), [git ls-files](https://git-scm.com/docs/git-ls-files)

A passing receipt must describe the artifact actually checked. Changing files,
the contract or its check definitions can invalidate the earlier result. These
are Trailbun design decisions verified by its own regression suite; they are not
claims that Git or a text scanner can judge semantic intent.

## Hooks are host interfaces

Claude Code documents event-specific exit and JSON behavior. A successful hook
process can return a denial decision; an error exit and a blocking exit are not
interchangeable. Stop continuation also needs loop control. Reading explicit
`exit 1` or `exit 2` statements from a script therefore cannot determine whether
a particular installation rejects an action. [Claude Code hook reference](https://code.claude.com/docs/en/hooks)

Codex documents its own hook events, input/output contract and trust/setup
requirements. Native adapters must be checked against the actual installed
host version and exercised with the tool path they claim to cover. Shared
policy does not establish shared lifecycle semantics.
[Codex hook reference](https://learn.chatgpt.com/docs/hooks)

Trailbun confines pre-action inspection to recognized edit formats. It does not
attempt to parse arbitrary shell programs into an authorization policy. A
post-action workspace finding records a change that already happened. Failure
to load a hook, malformed events and unavailable tools must remain visible
limitations rather than silently promoted enforcement claims.

## Measuring the benefit

The planned initial study is 3 tasks × 2 repeats × 2 hosts × 2 conditions:
24 runs. Conditions use the same task and acceptance checks, with and without
Trailbun. Publish every outcome, including no improvement, interruptions,
false-positive interventions and incomplete runs. Keep direct measurements
(time, checks, changed files, retries) separate from judgments about code quality.

This is a small diagnostic study. It can identify useful and harmful behavior;
it cannot justify a universal percentage, model ranking or causal claim about
all context rot. The deterministic demo is a separate artifact and must stay
labelled as such. Results and missing receipts are in [EVIDENCE.md](EVIDENCE.md).

## Presentation

Ponytail makes a familiar overengineering problem concrete with a character,
a small before/after example and links to reproduction. Its current benchmark
writeup corrects an earlier comparison that overstated average savings. The
useful lesson is that a memorable promise should lead to an inspectable result.
Trailbun does not reuse its identity or inherit its measurements.
[Ponytail](https://github.com/DietrichGebert/ponytail),
[corrected agentic benchmark](https://github.com/DietrichGebert/ponytail/blob/main/benchmarks/results/2026-06-18-agentic.md)

Matt Pocock's skills organize entrypoints around recognizable engineering
failures and distinguish managed installation from editable copies. Trailbun
uses the same practical principle: explain the user's problem, name the next
action and make installation consequences clear. Popularity is not evidence
that a visual treatment or workflow caused growth.
[Matt Pocock's skills](https://github.com/mattpocock/skills)
