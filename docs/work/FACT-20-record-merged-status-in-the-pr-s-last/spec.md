# FACT-20 — Record merged status in the PR's last commit

Status: in-review · Risk: low · Jira: FACT-20
Created: 2026-10-05 · Slug: record-merged-status-in-the-pr-s-last

## Problem

After a PR merges, the work item's status (`merged`, `released`, `done`) needs another commit, which on a protected
branch needs another PR. In practice nobody makes it, so finished items sit at `in-review` on `main` forever and
`factory status` shows completed work as open. `verify` is fine with that, so nothing flags it.

## Users and context

Anyone reading `factory status` on `main`; agents following `factory-implement`, `factory-workflow` and
`factory-release`. Code: `src/swfactory/work.py` (`next_step`, `collect_status`, `print_handoff`). Docs: ARCHITECTURE 3.2
and the skills above. The ticket's options were (a) a final status commit inside the same PR, (b) `status` and `verify`
asking `gh`, (c) a post-merge Action that opens a PR. The recommendation was (a).

## Goals and non-goals

**Goals**
- A defined, documented moment and actor for recording `merged`: the last commit on the PR branch, once review is done and CI is green.
- `factory status` on `main` stops showing finished work as open.
- The repo's own merged items are brought up to date.

**Non-goals**
- Calling `gh` from `status` or `verify` (option b), or a post-merge Action (option c): more machinery than needed.
- Recording `released`/`done` before a release has happened (they stay after-the-fact, via a docs-only PR).

## Requirements

- R1. ARCHITECTURE 3.2, `factory-release`, `factory-workflow` and the `factory-implement` hand-off say that the last commit
  on the PR branch sets `status: merged` (after review and green CI), that the merge is the next event, and that the commit is
  reverted if the PR is closed unmerged.
- R2. `factory status` treats an item at `merged` as complete when the project has no environment configured
  (`.factory/factory.yaml › environments` all null or absent): omitted from the default listing, listed by `--all`
  with nothing left to do. With at least one environment configured, `merged` still routes to `factory-release`.
- R3. `factory next` for such an item says there is nothing to do; its human-step hint for `in-review` names the
  last-commit rule.
- R4. The repo's own items that merged while left at `in-review` are set to `merged`.

## Acceptance criteria

- AC1. (R2) In a project with no environments, `factory status` omits an item at `merged` and `status --all` lists it
  with next `-` and a note that nothing is left (no environments); an item at `done` behaves as before.
- AC2. (R2) In a project with `environments: {dev: <something>}`, an item at `merged` is listed by default with next `factory-release`.
- AC3. (R3) `factory next` on a `merged` item with no environments prints "Nothing to do"; on `in-review` the human step
  starts "merge the PR" and names `factory advance <id> merged` as the last commit.
- AC4. (R1) The four documents carry the rule (checked by reading; `factory lint` and `factory sync --check .` pass).
- AC5. (R4) After the PR, `factory status --all` on `main` lists FACT-12, 16, 18, 19, 21 as `merged` and no item as `in-review`
  except items genuinely still under review.
- AC6. (R1) The "ready to merge" claim is not a lie: `verify` still passes for an item at `merged` whose PR is open, and a
  non-green or unmerged PR is handled by the documented revert (checked by reading).
