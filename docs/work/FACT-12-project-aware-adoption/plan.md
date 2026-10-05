# FACT-12 — Project-aware adoption

Status: in-review · Risk: medium · Jira: FACT-12
Created: 2026-10-05 · Slug: project-aware-adoption · Spec: spec.md

## Summary

One new small module, `src/swfactory/adopt_inspect.py`, holds the project inspection (default branch,
workflow triggers, commands section, detected commands, running CI steps). `installer.py` calls it from
`adopt` and gains `sync --check`; `verify.py` gains the docs-only rule; two kit files change. No framework:
plain functions with an injectable command runner for tests.

**Size:** M

## Current state

- `installer.py`: `adopt()` resolves config and calls `_install(root, config, existing, force, dry_run)`,
  which plans every kit item with `_plan_item` (modes create/managed/block), prints, writes, then
  `_register_adopted`. `sync()` calls `_install` too. `commands/install.py` is argparse wiring only.
- `kit/ci/python.yml` has `uv sync`; `push: branches: [main]` is hard-coded in all three CI templates.
- `verify.py`: `check_project(root, branch)`; rule 3 compares item status with `implementing`;
  `--changed-files-from` is accepted and ignored. `kit/workflows/factory-verify.yml` runs verify with
  `fetch-depth: 0`.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run factory lint`. Tests use fixture factory roots in `tmp_path` (`tests/test_install.py`).

## Approach

- `inspect_project(root)` returns a small dataclass: default branch (`git symbolic-ref
  refs/remotes/origin/HEAD`, else the current branch), trigger findings (parse each workflow except
  `factory-verify.yml`; PyYAML reads `on:` as `True`, handled), commands-section flag (heading regex on
  the `AGENTS.md` text outside the factory block), detected commands (Makefile targets from a fixed list,
  `package.json` scripts, pyproject `[tool.ruff]` / `[tool.pytest]` / `uv.lock`).
- `adapt_ci(content, default_branch, root, runner, check)` takes the template text, swaps the push branch,
  runs the `run:` lines in order through `runner(cmd, cwd) -> (code, output)` (default: `subprocess.run`
  with `shell=True`, 10-minute timeout; the commands are fixed template strings), removes failing steps
  and returns the new text plus a report. Install steps (`uv sync`, `npm ci`) are never dropped.
- `_install` takes an optional pre-computed adaptation: it replaces the content of a new `ci.yml` item
  before planning and, for a new or appended AGENTS.md block, inserts the TODO section before the block
  markers. Both only apply when the file is being created or the block appended, which keeps sync
  untouched and adopt idempotent.
- `sync --check`: plan with `dry_run=True`, count actions with a ledger key (managed/block) and status
  CREATE/UPDATE/BLOCK/CONFLICT, list them, return 1 if any.
- `verify`: when `--changed-files-from` is readable and every path starts with `docs/work/`, rule 3 skips
  the status comparison (item must still exist). The workflow computes the list with `git diff --name-only`.

**Alternatives rejected**

- Run checks in `--dry-run` as well: dry-run must stay free of side effects (`uv sync` writes `.venv`).
- A generic "detector" plugin interface: forbidden by R8 and the scope rule.
- Parse and rewrite existing CI to fix triggers: we only report; the project owns that file.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Python template: `uv sync --all-extras --all-groups` | `kit/ci/python.yml` | AC1 | template test |
| T2 | `adopt_inspect.py`: default branch, workflow triggers, commands section, detected commands | `src/swfactory/adopt_inspect.py`, `tests/test_adopt_inspect.py` | AC2, AC3 | unit tests on fixtures |
| T3 | `adapt_ci`: branch swap, run steps, drop failing, report | same | AC1, AC4, AC5 | unit tests with fake runner |
| T4 | Wire into `adopt`: findings before, TODO insert, adapted CI, report after; `--no-check` | `installer.py`, `commands/install.py`, `tests/test_install.py` | AC2-AC5 | adopt tests (idempotent, dry-run, no-check) |
| T5 | `sync --check` | `installer.py`, `commands/install.py` | AC6 | tests on fixture project |
| T6 | verify docs-only rule; workflow passes changed files; update the old "ignored" test | `verify.py`, `kit/workflows/factory-verify.yml`, `tests/test_verify.py` | AC7 | verify tests |
| T7 | Factory syncs itself; CI step `factory sync --check`; docs (ARCHITECTURE 3.6/3.7) | `.factory/`, `.claude/skills`, `.github/`, docs | AC6, AC8 | `factory sync --check` exits 0; full gate |
| T8 | Proof on a throwaway copy of an adopted project in a temp dir: `adopt --dry-run`, then real adopt | none (transcript in notes.md) | AC2-AC5 | transcript in notes.md |

## Data, API and migration impact

New flags: `adopt --no-check`, `sync --check`. No schema change. Adopted projects receive the new
`verify.py` and workflow with `factory sync`. Existing `ci.yml` files are untouched. Reversible by
reverting the merge.

## Security and failure modes

Executes commands, but only fixed strings from kit templates; opt-out flag; never in dry-run. A missing
tool or timeout produces a message and keeps the step. Findings never abort adopt; an unparsable workflow
becomes a finding.

## Rollout and rollback

Merge after CI; then `factory sync` in adopted projects (done by their owners, not in this item).
Rollback: revert the merge commit.

## Risks and open points

- The commands heuristic is crude; mitigated by the TODO wording. The signal is a project whose
  AGENTS.md gets a wrong TODO, which a human edits.
- Windows: `shell=True` resolves `npm.cmd` and `uv.exe` through PATH; tests use the fake runner, one test
  checks the default runner on a trivial command.
