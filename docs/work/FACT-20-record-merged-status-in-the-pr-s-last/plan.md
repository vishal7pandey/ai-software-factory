# FACT-20 — Record merged status in the PR's last commit

Status: in-review · Risk: low · Jira: FACT-20
Created: 2026-10-05 · Slug: record-merged-status-in-the-pr-s-last · Spec: spec.md

## Summary

Document option (a) and make `factory status`/`next` understand its consequence: with no environment to release to,
`merged` is the end of the line. Update the repo's own stale items. Size: S.

## Current state

- `src/swfactory/work.py:194-216` `next_step`: `merged`/`released` route to `factory-release`; `in-review` hint says "merge the PR, then factory advance <id> merged".
- `src/swfactory/work.py` `collect_status` hides only `done` unless `--all`; `print_handoff` prints "Nothing to do: <id> is done." for any empty skill list.
- `.factory/factory.yaml › environments` is `{dev: null, test: null, prod: null}` in this repo; `installer.py:236` writes that default into adopted projects.
- `tests/test_work.py:555-585` `EXPECTED_NEXT` expects `merged -> factory-release` in a project with no environments key at all.
- Docs: ARCHITECTURE 3.2 and golden path; skills `factory-release`, `factory-workflow`, `factory-implement` step 10.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run factory lint`, `uv run factory sync --check .`.

## Approach

(a), as recommended: no new mechanism; a convention plus documentation. Flaw found and handled: (a) can only record
`merged`, never `done` (a release has not happened yet), so by itself `status` would still list finished items. A project
with no configured environment has nothing to release, so `status` treats `merged` there as complete. With environments,
`released`/`done` follow after the release via a docs-only PR (already exempt from the status check by verify rule 3).
Another honest limit: `merged` is written one step before the merge; mitigated by "only after review and green CI" and
"revert the commit if the PR is closed unmerged".

**Alternatives rejected**
- (b) `gh`-based status: needs network and auth in a read-only command.
- (c) post-merge Action: needs write permission to a protected branch and a new workflow.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | `environments_configured`, `next_step` for `merged` with no environments, hide in default status, `--all` note, "Nothing to do" text, in-review hint | `src/swfactory/work.py` | AC1, AC2, AC3 | work tests |
| T2 | Tests; fix `EXPECTED_NEXT` for `merged`/`released` by configuring an environment | `tests/test_work.py` | AC1, AC2, AC3 | pytest |
| T3 | Document the rule | `docs/ARCHITECTURE.md`, `skills/factory-release`, `skills/factory-workflow`, `skills/factory-implement` | AC4, AC6 | lint; re-read |
| T4 | `factory sync .` | managed copies | AC4 | `sync --check` |
| T5 | Set the repo's stale merged items to `merged` | `docs/work/FACT-{12,16,18,19,21}-*/item.yaml` | AC5 | `factory status --all` |

## Data, API and migration impact

No schema change. Behaviour change in `factory status` and `factory next` only for items at `merged` in projects without environments.

## Security and failure modes

None. Failure mode: an item says `merged` and the PR is then closed; the documented revert handles it, and `pr` plus GitHub remain the source of truth.

## Rollout and rollback

Merge the PR. Rollback: revert; `factory sync .`.

## Risks and open points

- Setting `merged` before the merge is a convention, not enforced; flagged to the owner in the ticket.
- Items already at `in-review` in adopted projects stay stale until someone updates them; not changed here (other repos).
