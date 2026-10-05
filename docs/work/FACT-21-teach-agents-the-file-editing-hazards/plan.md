# FACT-21 — Teach agents the file-editing hazards

Status: in-review · Risk: low · Jira: FACT-21
Created: 2026-10-05 · Slug: teach-agents-the-file-editing-hazards · Spec: spec.md

## Summary

Add one step and two Never bullets to `skills/factory-implement/SKILL.md`, add a required-rules check for that
skill in `src/swfactory/checks.py`, test it in `tests/test_lint.py`, and sync the repo's managed copies. Size: S.

## Current state

- `skills/factory-implement/SKILL.md`: 52 lines, step 4 (work task by task) with sub-items 1 to 5, a `## Never` list.
- `src/swfactory/checks.py:62-135`: `_skill_findings` (frontmatter, length, sections, approve wording, links).
- `tests/test_lint.py`: `skill_text`/`put_skill`/`reasons` helpers; per-rule tests.
- Managed copies: `.claude/skills/factory-implement/SKILL.md`, `.github/skills/factory-implement/SKILL.md`, hashes in `.factory/factory.yaml`.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run factory lint`, `uv run factory sync --check .`.

## Approach

A small table `REQUIRED_RULES = {"factory-implement": [(label, regex), ...]}` in `checks.py`; `_skill_findings`
adds a FAIL per rule whose regex does not match the skill text (case-insensitive). Rule 1: an `inline script`
mention (the "never rewrite files with inline scripts" sentence). Rule 2: a `git add -A` mention. Mechanical
phrase matching is crude but is exactly what the ticket asks ("a lint check that a skill mentions both rules").

**Alternatives rejected**
- Put the rules in `AGENTS.md` block: the skill is what the implementing agent reads at the moment it edits.
- Hook that blocks `git add -A`: environment-specific, out of scope.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Add the editing step and the staging rule (step 4 sub-items, Never bullets) | `skills/factory-implement/SKILL.md` | AC1 | `factory lint`; re-read |
| T2 | Required-rules check for `factory-implement` | `src/swfactory/checks.py` | AC2 | lint tests |
| T3 | Tests: real skill passes; each missing rule fails; other skills exempt | `tests/test_lint.py` | AC2 | pytest; mutations |
| T4 | `factory sync .` for the managed copies | `.claude/skills/`, `.github/skills/`, `.factory/factory.yaml` | AC3 | `factory sync --check .` |
| T5 | Full local gate | repo | AC4 | lint, ruff, pytest |

## Data, API and migration impact

None. Adopted projects receive the wording on their next `factory sync`.

## Security and failure modes

None. A lint failure message names the missing rule.

## Rollout and rollback

Merge the PR. Rollback: revert the commit and re-run `factory sync .`.

## Risks and open points

- Phrase matching can be satisfied by an unrelated sentence containing the words; accepted, the review reads the skill.
