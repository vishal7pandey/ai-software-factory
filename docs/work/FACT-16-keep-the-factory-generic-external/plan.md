# FACT-16 — Keep the factory generic: external project registry

Status: draft · Risk: low · Jira: FACT-16
Created: 2026-10-04 · Slug: keep-the-factory-generic-external · Spec: spec.md

## Summary

Move the project registry out of the repo into a single user-level file (`FACTORY_REGISTRY`, default `~/.factory/registry.yaml`) holding `projects` and `paths`, delete the committed `registry/` directory, make examples and fixtures neutral, and add a `factory lint` guard so instance data cannot creep back. Size: S.

## Current state

- `src/swfactory/common.py:41-46`: `registry_path()` returns `FACTORY_ROOT/registry/projects.yaml`; `local_registry_path()` returns `FACTORY_ROOT/registry/local.yaml`.
- `src/swfactory/installer.py:324-472`: `_load_registry`, `_save_registry`, the adopt upsert (lines ~378-400), `project list` (404), `project add` (439-457) and `project remove` (463-472). Machine paths are written separately through `common.dump_yaml(local, common.local_registry_path())`.
- `src/swfactory/commands/install.py:53`: help text says "stored in registry/local.yaml".
- `src/swfactory/checks.py`: `lint_factory` is where factory-level lint rules live.
- Tests: 16 registry references in `tests/test_install.py`, 2 in `tests/test_integration.py` (monkeypatching `registry_path` and `local_registry_path`).
- Docs: `docs/ARCHITECTURE.md` lines 52, 181-182, 194; `docs/jira-workflow.md` lines 11 and 20; `AGENTS.md` line 26; `.gitignore` line 8; `registry/projects.yaml`.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run factory lint`.

## Approach

`registry_path()` becomes the only path function: `Path(os.environ["FACTORY_REGISTRY"])` when set (relative paths resolved against the current directory), else `Path.home()/".factory"/"registry.yaml"`. `local_registry_path()` is deleted. The registry dict gains a `paths` mapping next to `projects`, so every place that wrote `local.yaml` writes `reg["paths"]` and saves once. A missing file loads as `{"projects": [], "paths": {}}`; saving creates parent directories.

**Alternatives rejected**

- Keep the two-file split at the new location: more code for no benefit once nothing is committed.
- Delete the registry and the `project` commands: possible, but the maintainer asked to keep a registry that is external.
- A registry inside the workspace folder by default: the factory must not know about any particular workspace layout; the environment variable covers that.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | `registry_path()` reads `FACTORY_REGISTRY` or defaults to `~/.factory/registry.yaml`; delete `local_registry_path()` | `src/swfactory/common.py` | AC1, AC2 | path-resolution unit tests |
| T2 | Registry functions use one file with `projects` and `paths`; missing file loads empty; save creates parents; write errors reported with the path | `src/swfactory/installer.py` | AC1, AC2 | `tests/test_registry.py` |
| T3 | Help text and the "no registry yet" message for `project list` | `src/swfactory/commands/install.py` | AC2 | test asserts message and exit 0 |
| T4 | Lint rules: fail on a `registry/` directory, and on `atlassian.net` under `docs/ kit/ skills/ policies/ templates/` | `src/swfactory/checks.py`, `tests/test_lint.py` | AC4 | lint tests (pass and fail fixtures) |
| T5 | Delete `registry/`, the `.gitignore` line and the `AGENTS.md` line; update ARCHITECTURE (tree, 3.6, command table) and `docs/jira-workflow.md`; add `docs/registry.example.yaml` | docs, `.gitignore`, `AGENTS.md` | AC3, AC5 | `factory lint`; manual search in test-plan |
| T6 | Neutral names in ARCHITECTURE examples and in `tests/test_install.py`, `tests/test_integration.py` (point them at the new location) | tests, docs | AC5, AC6 | full test run |
| T7 | Full run: pytest, ruff check and format, `factory lint`, then the AC5 search | repo | AC5, AC6 | CI green on ubuntu and windows |

## Data, API and migration impact

No schema change to a project entry; the file gains a top-level `paths` key and moves. No migration code: the maintainer copies the values from the old `registry/projects.yaml` (visible in git history) into `~/.factory/registry.yaml`, with local paths under `paths`. Environment variable `FACTORY_REGISTRY` is new.

## Security and failure modes

No secrets involved; the file holds names, URLs and local paths. A bad or unwritable path produces a `FactoryError` naming the path. The kit is installed before the registry is written, so a registry failure never leaves a half-adopted project.

## Rollout and rollback

Merge the PR (human). Verify afterwards: `factory project list` on a machine with no registry prints the "no registry yet" message. Rollback: revert the merge commit; the old registry file returns from history.

## Risks and open points

- Tests that monkeypatched the two old path functions must be updated, not weakened.
- The AC5 search must not turn into a test that contains the names it forbids; it is a documented manual check.
