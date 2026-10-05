# FACT-5 — Plan: Enforce small commits and the test-plan Audit

Status: plan-approved · Risk: low · Jira: FACT-5
Created: 2026-10-05 · Slug: enforce-small-commits-and-the-test-plan · Spec: spec.md

## Summary

Add `audit_is_placeholder()` and `warn_project()` to the standalone `verify.py` and print its lines from
`run()`; tighten one sentence in `factory-implement`; mention the warning in `factory-test` and
ARCHITECTURE 3.3. **Size:** S.

## Current state

- `src/swfactory/verify.py`: `check_project` (rules 1-3, returns problems), `run` prints `FAIL ...` and
  `verify: OK` or `verify: N problem(s)`; `load_item`, `validate_item`, `STATUSES` are reusable.
- `tests/test_verify.py`: exact-output tests around lines ~290-300 and ~346-367 (`test_main_output_and_exit_codes`,
  `test_standalone_script_runs_without_swfactory`) assert the final lines and exit codes; helpers
  `make_item`, `write_item` (which writes `test-plan.md` with "content\n", no Audit heading).
- `kit/work/test-plan.md`: the Audit heading followed by an HTML comment placeholder.
- `skills/factory-implement/SKILL.md` step 4.6 (commit): "one logical change"; no per-task rule.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run factory lint`, `uv run factory sync --check .`.

## Approach

`audit_is_placeholder(text)` finds the first `## Audit` line, takes the text up to the next `## ` line (or
EOF), strips `<!-- ... -->` comments, and returns whether nothing but whitespace remains. `warn_project(root)`
loads each item like `check_project` (skipping invalid ones), and for status ≥ `in-review` reads
`test-plan.md` and calls `audit_is_placeholder`. `run()` prints `WARN ...` lines before the `FAIL ...`
lines and picks the final-line form accordingly. `check_project` itself is untouched, so every existing
caller (including other tools that may call it directly) keeps its exact behaviour. The skill wording is a
one-sentence tightening, not new tooling.

**Alternatives rejected**
- A commit-history check in `verify`: needs git history and a task-id convention; the ticket says keep it
  small.
- Failing on an empty audit: the ticket asks for a warning; legacy items would break.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | `audit_is_placeholder`, `warn_project`, `run()` output, synced to `.factory/verify.py` | `src/swfactory/verify.py` | AC1, AC2 | verify tests |
| T2 | Tests: warn / no-warn cases, exit code and last lines | `tests/test_verify.py` | AC1, AC2 | pytest; mutations |
| T3 | Skill wording and docs | `skills/factory-implement/SKILL.md`, `skills/factory-test/SKILL.md`, `docs/ARCHITECTURE.md` | AC3, AC4 | lint; re-read |
| T4 | `factory sync .`; run `verify` on the repo | managed copies | AC3, AC5 | `sync --check`; no WARN lines |

## Data, API and migration impact

New output line format `WARN <id>: <reason>` and last line `verify: OK (N warning(s))` only when warnings
exist. No schema change.

## Security and failure modes

None. An unreadable or missing `test-plan.md` yields no warning (caught alongside the existing
`(ValueError, OSError, UnicodeDecodeError)` handling already used by `check_project`).

## Rollout and rollback

Merge the PR. Adopted projects get the new `verify.py` on their next `factory sync`. Rollback: revert,
`factory sync .`.

## Risks and open points

- A tool parsing the last line `verify: OK` exactly would see `verify: OK (1 warning(s))` once an item
  triggers a warning; none in this repo does (CI uses the exit code, not the text).
