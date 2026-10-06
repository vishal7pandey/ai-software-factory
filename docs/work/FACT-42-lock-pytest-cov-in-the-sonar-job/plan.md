# FACT-42 — Lock pytest-cov in the sonar job

Status: draft · Risk: low · Jira: FACT-42
Created: 2026-10-06 · Spec: spec.md

## Summary

Add `pytest-cov` to the `dev` dependency group (locked in `uv.lock`) and run the coverage step of this
repo's `sonar.yml` without `--with`.

**Size:** S.

## Current state

* `.github/workflows/sonar.yml:58`: `uv run --with pytest-cov python -m pytest -q --cov=src/swfactory
  --cov-branch --cov-report=xml:coverage.xml`; the install step is `uv sync --all-extras --all-groups`,
  so a locked dev dependency is present before the test step.
* `pyproject.toml`: `[dependency-groups] dev = ["pytest>=8", "ruff>=0.6"]`; `uv.lock` present.
* Commands: `uv run python -m pytest -q`, ruff check/format, `factory lint`, `factory sync --check .`.

## Approach

`uv add --dev pytest-cov` updates `pyproject.toml` and `uv.lock` (only new packages `pytest-cov` and
`coverage`); the workflow step becomes `uv run python -m pytest ...`. `ci.yml` runs `uv sync`, which
installs the dev group too, so CI gains the package without a change.

**Alternatives rejected**
- Pin `--with pytest-cov==X`: still outside the lockfile and hashes.
- Suppress or dismiss the Sonar issue: forbidden without the owner's approval and hides the cause.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | failing regression test | tests/test_sonar_self.py | AC1 | fails on current code (done) |
| T2 | `uv add --dev pytest-cov`, edit the step | pyproject.toml, uv.lock, .github/workflows/sonar.yml | AC1, AC2 | test passes; full suite; the exact CI command writes coverage.xml |
| T3 | PR: scan runs, no S8544 on the PR | PR | AC2 | `gh pr checks`, SonarQube tool issues of the PR |
| T4 | closure after merge | SonarCloud API | AC3 | issue closed/resolved, or recorded blocker |

## Data, API and migration impact

None (lockfile gains two dev-only packages).

## Security and failure modes

Reduces the unlocked install surface in CI. Failure shows as a red `sonar` or `test` job.

## Rollout and rollback

Merge; revert the commit to undo.

## Risks and open points

The closure check depends on SonarCloud's main branch naming (spec, Risks).
