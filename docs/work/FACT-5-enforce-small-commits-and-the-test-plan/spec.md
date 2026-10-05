# FACT-5 — Enforce small commits and the test-plan Audit

Status: spec-approved · Risk: low · Jira: FACT-5
Created: 2026-10-05 · Slug: enforce-small-commits-and-the-test-plan

## Problem

The first end-to-end run (`docs/e2e-001.md`) found two rules that exist on paper but nothing makes happen:
`factory-implement` put two plan tasks in one commit despite "small commits", and `factory-test` left the
`## Audit (after implementation)` section of `test-plan.md` empty, with nothing noticing. The audit is what
proves a test fails when its behaviour breaks; an empty one means the proof was skipped.

## Users and context

Agents and humans on adopted projects. `src/swfactory/verify.py` (standalone gate, rule set in
ARCHITECTURE 3.3), `skills/factory-implement`, `skills/factory-test` (audit mode), `kit/work/test-plan.md`
(the template). The ticket asks for the smallest enforcement and says not to add checks the golden path
does not need.

## Goals and non-goals

**Goals**
- `verify` warns (never fails) when an item is at `in-review` or later and its test-plan Audit section is
  still the template placeholder.
- `factory-implement` states the concrete rule: one commit per plan task, never two tasks in one commit.

**Non-goals**
- Failing CI on an empty audit, or checking the quality of an audit.
- Enforcing commit granularity mechanically (no commit-history check).
- Warnings for other rules; a general warning framework beyond one line format.

## Requirements

- R1. For every valid work item with status `in-review` or later, if `test-plan.md` has an `## Audit`
  section whose content is empty once HTML comments and whitespace are removed, `verify` prints
  `WARN <id>: ...` naming the file.
- R2. Warnings do not change the exit code. With only warnings the last line is `verify: OK (N warning(s))`;
  with none it is exactly `verify: OK`; with problems it is still `verify: N problem(s)` (warnings listed
  above it).
- R3. No warning for items before `in-review`, for a filled Audit, or for a test-plan without an Audit
  heading.
- R4. `factory-implement` requires one commit per plan task (never two tasks in one commit), with the task
  id in the commit body.
- R5. `factory-test` audit mode and ARCHITECTURE 3.3 mention the warning.

## Acceptance criteria

- AC1. (R1, R3) An item at `in-review` whose Audit holds only the template comment yields one
  `WARN F-001: ...Audit...` line; the same item with a real Audit, an item at `implementing`, and a
  test-plan without an Audit heading yield none.
- AC2. (R2) Exit code is 0 with a warning only, the last line is `verify: OK (1 warning(s))`; a project
  with no warnings still prints exactly `verify: OK`; a project with a failure and a warning exits 1 and
  prints both.
- AC3. (R4) `skills/factory-implement/SKILL.md` contains the one-commit-per-plan-task rule; `factory lint`
  passes and managed copies are synced.
- AC4. (R5) ARCHITECTURE 3.3 and the `factory-test` skill mention the warning.
- AC5. The warning applies to the repo's own items correctly: no warning for FACT-12, 16, 18, 19, 20, 21
  (their Audits are filled).
