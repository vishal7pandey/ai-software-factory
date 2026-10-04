---
name: factory-plan
description: Use when a work item's spec is approved (status spec-approved) and you must write docs/work/<id>-<slug>/plan.md with a grounded approach, ordered verifiable tasks mapped to acceptance criteria, data/security/rollout impact and a size estimate. Also use after a bug's spec (from factory-diagnose) is approved. Not for specifying what to build (factory-spec), not for writing code (factory-implement), and not when the spec is unapproved or wrong.
---

# factory-plan — approved spec to executable plan

## When to use
- `item.yaml` says `status: spec-approved` and `plan.md` is missing, empty, or still the template.
- A bug item whose regression-criterion spec has been approved.
- A human asked for plan revisions, or a plan must be amended because implementation disproved it.
- Not when the spec is unapproved (stop, route to `factory-spec`), and not to write code.

## Inputs
- `docs/work/<id>-<slug>/spec.md` (approved text: R and AC ids), `item.yaml`, `notes.md`.
- `AGENTS.md`, `.factory/policies/security.md`, `testing.md`, `production.md`, `git.md`.
- The codebase around the change: entry points, modules, tests, migrations, config, CI, and how the project runs lint and tests (AGENTS.md, `pyproject.toml`, `package.json`, `Makefile`, CI workflow).
- Template structure: Summary + size, Current state, Approach + alternatives rejected, Tasks table (# / Task / Files / Serves / Verify by), Data/API/migration impact, Security and failure modes, Rollout and rollback, Risks. Header: `Status: draft · Risk: <risk> · Jira: <key or null>`.

## Steps
1. **Confirm the gate.** `status` must be `spec-approved` (or later, when amending). Otherwise stop and say which approval is missing. Re-read `spec.md` fully; list its R and AC ids: that list is your coverage checklist.
2. **Ground the plan in code.** Before writing, read the actual files you would touch: find the entry point, follow the data flow, locate the nearest existing pattern to copy, find existing tests for the area, check migrations and config. Every file path in the plan must exist (or be explicitly marked "new" with its parent directory). Write what you found under Current state, including the exact lint and test commands.
3. **Check the spec against reality.** If exploring shows an AC is impossible, ambiguous, contradicts existing behaviour, or hides a bigger scope: stop. Do not paper over it in the plan. Record it in `notes.md`, say plainly "the spec needs amending: <what and why>", hand back to `factory-spec` (or `factory-diagnose` for bugs), and ask the human to re-approve the amended spec. Plan afterwards.
4. **Choose the approach.** Prefer the smallest change that satisfies every AC and follows existing patterns. Write it in a short paragraph, then 1-3 rejected alternatives, each with 1-3 lines on why not (cost, risk, scope). No alternatives listed means you have not looked.
5. **Break into tasks.** Ordered small to large, safe to merge in order. Each task: one coherent change; names its files; lists the AC ids it serves (`Serves`); has a concrete `Verify by` (a test name, command with expected result, or observable behaviour). A task that cannot be verified independently is too big or wrongly cut. Put enabling work (migration, flag, test fixtures, refactor-for-testability) first. Every AC from the spec appears in at least one task's `Serves`; refactor tasks must keep existing tests green and say so.
6. **Impact sections.** Data/API/migration: schema changes, new or changed endpoints/flags/env vars, backwards compatibility, whether each migration is reversible; "none" if none. Security: authn/authz, input validation, secrets, personal data, new dependencies (per `security.md`). Failure modes: what can fail, how you will see it (logs/metrics/errors), what the user sees.
7. **Rollout and rollback.** How it reaches each environment (see `environments` in `.factory/factory.yaml`), order of deploys vs migrations, feature flag or not, how to verify in each, exact rollback steps, and any point of no return. Higher `risk` needs a concrete rollback, not "revert the PR".
8. **Estimate size.** S (under about half a day), M (1-2 days), L (3-5 days). Larger than L: recommend a split into separate items, each independently shippable, and say where the seam is. Do not hide a XL behind 30 tasks.
9. **Self-review.** Plan does not contradict spec (R/AC wording, non-goals respected); AC coverage complete (cross-check your checklist from step 1); every path real; verify steps concrete; no scope the spec did not ask for; no template comments or NEEDS CLARIFICATION marker left; test strategy is consistent with `testing.md`.
10. **Hand over.** Leave `status: spec-approved` (supervised) and commit `plan.md` on the item branch (`docs(<id>): add plan`). Post a short summary: approach, size, riskiest task, rollout in one line. Ask the human to approve the plan, then stop. Under `trusted` autonomy with `risk: low`, the plan approval is waived, but still hand over the summary and proceed per `factory-workflow`.

## Output
- `docs/work/<id>-<slug>/plan.md`, complete and committed.
- A `notes.md` entry for any spec gap found, with the amended spec re-submitted for approval.
- Approval requested; `item.yaml` untouched.

## Definition of done
- Every AC id from `spec.md` is served by at least one task, and every task serves at least one AC (or is explicitly enabling work).
- Tasks are ordered, small, each with a concrete `Verify by`, each naming real files.
- Alternatives, data/API/migration impact, security and failure modes, rollout and rollback, and a size estimate are filled in.
- The plan contradicts nothing in the spec; no template comments or marker remain.
- The human has been asked to approve and you have stopped.

## Never
- Never run `factory approve` or edit `approvals:`. Finish the plan, then ask the human to approve it.
- Never plan against an unapproved or known-wrong spec; amend the spec first and say so in `notes.md`.
- Never invent files, modules or APIs you did not read.
- Never expand scope beyond the spec's requirements; list ideas in `notes.md` instead.
- Never start implementing in this skill.
