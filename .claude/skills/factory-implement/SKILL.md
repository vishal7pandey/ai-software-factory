---
name: factory-implement
description: Use when a work item has an approved plan (status plan-approved or implementing, plan approval waived only for trusted low-risk items) and a test-plan.md, and you must write the code and tests task by task, commit, open the PR and move the item to in-review. Not for specifying or planning (factory-spec, factory-plan), not for writing the AC-to-test mapping from scratch (factory-test), not for reviewing (factory-review), and not for exempt chores.
---

# factory-implement — execute the approved plan

## When to use
- `item.yaml` is `plan-approved` (you will set `implementing`) or `implementing` (you are resuming), and `spec.md`, `plan.md` and `test-plan.md` are non-empty.
- Review found problems and the item is bounced back from `in-review`: fix them here, on the same branch.
- Not when a required approval is missing, `test-plan.md` does not exist (use `factory-test` first), or the plan is known to be wrong (see Steps 1 and 7).

## Inputs
- `docs/work/<id>-<slug>/`: `item.yaml` (branch, risk, approvals), `spec.md` (R/AC ids), `plan.md` (task table), `test-plan.md`, `notes.md`.
- `AGENTS.md` and `.factory/policies/` (`git.md`, `testing.md`, `security.md`). Follow them over any habit.
- The project's own commands for lint, format, type-check and tests: from AGENTS.md, `pyproject.toml`, `package.json`, `Makefile`, `.github/workflows/ci.yml`. Run what CI runs.
- `.github/pull_request_template.md` for the PR body.

## Steps
1. **Gate check.** Required approvals present in `item.yaml › approvals`: spec and plan under `supervised`; spec only for `trusted` with `risk: low`. If missing, stop and say which. If `test-plan.md` is absent, do `factory-test` first. Waivers come from `autonomy.md`/the human, never from you.
2. **Branch.** Check out `item.yaml › branch` (create it from the up-to-date default branch if it does not exist). Never commit to `main`. `git status` must be clean or contain only this item's files. Set `status: implementing` in `item.yaml` (or `factory advance <id> implementing`), commit that with the first task.
3. **Run the baseline.** Run the full lint + test commands before touching code. If they fail already, record it in `notes.md` and tell the human before proceeding; do not fix unrelated failures silently.
4. **Work task by task**, in plan order. For each task in `plan.md`:
   1. Re-read the ACs it `Serves` and its `Verify by`.
   2. **Test first where a test can be written:** write the failing test (red), watch it fail for the right reason, write the minimal code (green), then refactor with tests green. Where test-first is impractical (config, wiring, docs, UI polish), say why in the commit body and add the test after.
   3. Run lint/format and the relevant tests, then the full suite; all green before committing.
   4. Update `test-plan.md`: fill the row for each AC served with the actual test name(s)/file and status. Tick the task off in `plan.md` (checkbox or "done" note).
   5. Commit: one logical change, conventional message referencing the id, e.g. `feat(F-001): reject expired tokens` with body "Serves AC2, AC3". Include code, tests and the doc updates in the same commit.
5. **Stay in scope.** Diff only what the task needs. Unrelated bugs, smells, upgrades or TODOs you notice go in `notes.md` as one line each (file, what, why), not into this diff. No drive-by reformatting. No new dependency unless the plan names it.
6. **Tests are sacred.** Never weaken, skip, loosen or delete a test or assertion to get green, and never mock away the thing under test. If a test fails, find out why: your code is wrong, the test was wrong (justify it in the commit body and `notes.md`), or the spec changed (step 7). No secrets, tokens or real personal data in code, fixtures, logs or commits.
7. **Blocked, or plan proves wrong?** If a task is impossible, much bigger than planned, or contradicts the spec: stop coding. Record what you found and the options in `notes.md`, commit the state, and ask the human. Amend `plan.md` (or the spec via `factory-spec`) and ask for re-approval; do not continue on a divergent plan. Small deviations that keep every AC intact (e.g. a helper renamed): note them in `plan.md` and the commit.
8. **Finish.** When all tasks are done: run the full lint, format, type-check and test suite; walk `test-plan.md` and confirm every AC row has a passing test (no empty rows); skim `git diff <default-branch>...HEAD` for stray debug code, secrets, unrelated changes, and files outside the plan.
9. **Open the PR.** Push the branch. Title `<ID>: <title>`. Body (use the PR template): links to `spec.md`, `plan.md`, `test-plan.md` in the branch; a table AC → test name; risk and rollback in two lines; unrelated findings from `notes.md`; deviations from the plan. Record the URL in `item.yaml › pr` and set `status: in-review` (or `factory advance <id> in-review`); commit and push.
10. **Hand off.** Tell the human the PR is open and in review; continue with `factory-review` (independent pass against the spec). Merging is the human's call. After merge, `factory-release` takes over.

## Output
- Commits on the item branch: code, tests, and updated `test-plan.md`/`plan.md`/`notes.md`.
- An open PR titled `<ID>: <title>` with AC → test mapping; `item.yaml` with `pr` set and `status: in-review`.

## Definition of done
- Every plan task is done and committed; every AC row in `test-plan.md` names a test that passes.
- Lint, format, type-check and the full test suite pass locally (and CI is green or being watched).
- The diff contains nothing outside the plan; unrelated findings are in `notes.md`.
- No test was weakened, skipped or deleted to pass; no secrets committed.
- PR opened, `pr` recorded, status `in-review`.

## Never
- Never start without the required approvals in `item.yaml`; never run `factory approve` or write `approvals:`. If an approval is missing, ask the human to approve the artifact and stop.
- Never merge the PR, push to `main`, or deploy; those are human gates.
- Never use `--no-verify`, force-push shared branches, or bypass hooks/CI.
- Never fix unrelated things in the same diff.
- Never carry on when the plan or spec proves wrong; stop, record, ask.
