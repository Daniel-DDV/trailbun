# 0.2.1 release checklist

Everything below is outward-facing and runs only on an explicit go. Commands
assume `gh` is logged in as the repository owner and the branch
`review/0.2.1` holds the review changes.

## 1. Pull request and green main

```sh
git push -u origin review/0.2.1
gh pr create --base main --head review/0.2.1 --title "0.2.1: review fixes" --body-file notes/PR_BODY.md
# wait for the lint, test and windows-acl jobs; merge only when all are green
gh pr merge --squash --delete-branch
gh run list --branch main --limit 3
```

## 2. Repository settings

```sh
gh repo edit --description "Keep your agent on the trail. Task contracts, scope checks and verification receipts for Codex and Claude Code hooks." \
  --add-topic claude-code-hooks --add-topic codex-cli --add-topic coding-agents --add-topic agent-skills \
  --add-topic hooks --add-topic git --add-topic cli --add-topic python \
  --enable-wiki=false --enable-projects=false
gh api -X PATCH repos/Daniel-DDV/trailbun -f delete_branch_on_merge=true
gh api -X PUT repos/Daniel-DDV/trailbun/automated-security-fixes
gh api -X PUT repos/Daniel-DDV/trailbun/vulnerability-alerts
gh api -X PUT repos/Daniel-DDV/trailbun/private-vulnerability-reporting
git push origin --delete feat/trailbun
```

Upload `assets/social-preview.jpg` (1280 by 640, 131 KB) under Settings,
Social preview; there is no API for it. Confirm with:

```sh
curl -s https://github.com/Daniel-DDV/trailbun | grep -o 'og:image" content="[^"]*'
```

Ruleset for `main` and tags (Settings, Rules): require the `lint`, `test` and
`windows-acl` status checks before merge; block force pushes and deletions;
block tag updates and deletions for `v*`. Enable immutable releases under
Settings, General, Releases.

## 3. PyPI

1. Create the `trailbun` project on PyPI through a pending trusted publisher:
   owner `Daniel-DDV`, repository `trailbun`, workflow `release.yml`,
   environment `pypi`.
2. Create the `pypi` environment in the repository (Settings, Environments)
   and restrict it to tags matching `v*`.
3. Sign and push the tag; the release workflow builds, replays the tests from
   the source archive, writes `release-validation.json` and `SHA256SUMS`,
   attests provenance, publishes to PyPI and creates the GitHub release.

```sh
git tag -s v0.2.1 -m "Trailbun 0.2.1"
git push origin v0.2.1
gh run watch
gh release view v0.2.1
gh api repos/Daniel-DDV/trailbun/releases/tags/v0.2.1 --jq .immutable
gh attestation verify dist/trailbun-0.2.1-py3-none-any.whl --owner Daniel-DDV
uvx trailbun demo
```

`uv` resolves a pre-release when no stable release exists, so `uvx trailbun
demo` works as soon as 0.2.1 is on PyPI. If you want the PyPI page to render
images, make the README image URLs absolute first.

## 4. Milestone and issues

Create the `0.3.0` milestone and file one issue per pending item from
`CHANGELOG.md`'s "Pending" list plus the Phase 1 and Phase 2 rows of the
review: the Claude Code probe, incremental inspection, end-to-end hook tests
through the real CLI, submodule handling, checks outside the lock, provenance
delimiters, the study redesign, executable diagnosis, receipts with an
audience (`receipt --last`, a pre-push hook, a merge-gating action) and the
plugin manifest. Label each with the review ID.

## 5. Claude Code probe (Phase 1, gates the launch)

Add `--host claude` to `scripts/native_smoke.py` and
`scripts/native_compact.py`, authenticate, run the cells listed in the
review (permitted Edit, denied Edit outside scope, subagent Edit, Bash
redirect outside scope, Stop block with `stop_hook_active`, PostToolUseFailure,
SessionStart compact, PreToolUse deny under bypassPermissions, a
`disableAllHooks` write to `settings.local.json`), publish the receipts with
the same reassessment discipline, then rewrite the README's Claude row with
the version and OS.
