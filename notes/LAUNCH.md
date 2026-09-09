# Trailbun launch notes

Prepared copy and sequence, not a record of messages sent. Every sentence
describes shipped behavior or is marked as pending. Plain sentences, no
em-dashes, no contrast constructions, no three-beat slogans, no hype
adjectives, no emoji.

## Gate

Before any post: `main` is green, the 0.2.1 pre-release is on PyPI so that
`uvx trailbun demo` works from a clean directory, the README shows the router
line and the status box, the social preview is uploaded, and the Claude Code
probe has run and its receipts are published. Until the probe runs, nothing
below claims Claude Code support.

## Tagline and description

Brand line: **Keep your agent on the trail.**

Sub-line under the h1: "Task contracts, scope checks and verification receipts
for coding agents. Live receipt on Codex 0.153.4 (Windows); the Claude Code
adapter has fixtures and no live receipt yet."

Repository description: "Keep your agent on the trail. Task contracts, scope
checks and verification receipts for Codex and Claude Code hooks."

Topics: `claude-code-hooks`, `codex-cli`, `coding-agents`, `agent-skills`,
`hooks`, `git`, `cli`, `python`.

## Shareable asset

One session only, never a composite:

```text
apply_patch
*** Update File: protected/outside.txt
-TRAILBUN_SENTINEL_UNCHANGED
+TRAILBUN_SENTINEL_CHANGED
ERROR codex_core::tools::router: Command blocked by PreToolUse hook:
Trailbun scope violation: protected/outside.txt
agent: The protected patch was rejected by the PreToolUse hook. No verification run; task remains incomplete.
```

Caption: "Codex 0.153.4, Windows 11, apply_patch. The session ended incomplete
by design; the attempted patch, hook receipt and unchanged file hash are in the
repo." Plum background, chartreuse for the violation line.

Second asset for reach: the rabbit-in-the-hole cartoon captioned "Three failed
fixes later." A Claude variant only after the Claude probe.

## Short announcement

Your agent started with a small bug. Three failed fixes later it is building a
framework, and the original task has scrolled out of its context.

I built Trailbun to keep the task outside the conversation: a contract with
the goal, the allowed paths and the acceptance checks; a scope check against
the Git commit the task started from; and a verification receipt that goes
stale the moment any checked file changes. On Codex it returns a native deny
for an out-of-scope patch, with the receipt in the repo.

```sh
uvx trailbun demo
```

The demo runs in a temporary Git repository with no model. Native coverage and
measurements are reported separately, with receipts and the gaps left visible.

## Show HN

Title: "Show HN: Trailbun, a Git-checked task contract for coding agents"

First paragraph: "I kept watching the same failure: an agent takes a small bug,
fails to fix it twice, and starts building a framework. By then the original
task has scrolled out of its context. Trailbun writes the task down outside
the conversation (goal, allowed paths, acceptance commands), diffs every change
against the Git commit the task started from, including work already
committed, and uses the host hook protocol to deny writes outside those paths:
apply_patch on Codex 0.153.4 has a retained live receipt; Edit and Write on
Claude Code pass adapter fixtures only. A passing verification is bound to a
hash of the checked files, so any later edit makes it stale and the Stop hook
asks for a rerun once. It checks file scope only; it cannot tell whether a
change is what you meant, and shell or MCP writes are only seen afterwards. I
would like reproductions where it got in the way or where a valid task needed
a wider scope."

Self-posted first comment: the six limits from the README's "What it does not
do" section and a request for reproductions with the issue template.

## Sequence

- Days 3 to 4: one post on X and LinkedIn with the single-session card and
  `uvx trailbun demo`; submission issues on hesreallyhim/awesome-claude-code
  and the main awesome-codex list.
- Day 5 (Tuesday to Thursday, morning US Eastern): Show HN with the first
  comment above.
- Days 5 to 7: answer every comment with a receipt link.
- Days 8 to 10: r/ClaudeAI and r/ChatGPTCoding with the failure story as the
  title; a two-line note to two or three people who cover hooks.
- Days 11 to 14: publish the first external failure receipt received.

## Never claim

Any percentage. "Prevents context rot." "Sandbox" or "secure." "Works with
Claude Code" before a live receipt. "Enforced" for shell or MCP paths.
"Faster" or "cheaper."

## Comparative context (fetched 2026-09-09)

Repositories with a recognizable example in the first screen, a one-command
install in the host's idiom and a distribution surface reach readers that
Trailbun does not yet. Trailbun has what they lack: a retained receipt of a
host refusing a write, a study matrix showing unrun cells, and a tested CLI
with cross-platform CI. The launch leads with the receipt.
