# FACT-18 — Test suite writes a fake project into the real registry

Status: in-review · Risk: low · Jira: FACT-18
Created: 2026-10-05 · Slug: test-suite-writes-a-fake-project-into · Spec: spec.md

## Summary

Add an autouse fixture to `tests/conftest.py` that points `FACTORY_REGISTRY`, `HOME` and `USERPROFILE` at a
per-test temp directory and wraps `common.registry_path` so that resolving anything under the real home raises.
Add a guard test file. No source change. **Size:** S.

## Current state

- `src/swfactory/common.py:41-49`: `registry_path()`; falls back to `Path.home()/.factory/registry.yaml`.
- `src/swfactory/installer.py:422,435,471,501`: all registry access goes through `common.registry_path()`
  (attribute lookup on the module, so a monkeypatch of `common.registry_path` reaches every caller).
- `tests/conftest.py`: one autouse fixture (`no_project_commands`); no home isolation.
- Existing tests redirect by hand with `monkeypatch.setenv("FACTORY_REGISTRY", ...)`; `test_default_location_and_missing_file`
  sets `HOME`, `USERPROFILE` itself and deletes the variable.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run factory lint`, `uv run factory sync --check .`.

## Approach

Capture the real home once at import time of `conftest.py` (before any redirect). The autouse fixture sets the three
variables to `tmp_path_factory`-style per-test paths, and replaces `common.registry_path` with a wrapper that calls
the original and raises `AssertionError` when the result is inside `<real home>/.factory`. Tests that set their own
`FACTORY_REGISTRY` or `HOME` keep working because `monkeypatch` applies theirs after the fixture and the wrapper
only objects to the real location. The guard is path-based on purpose: a hash comparison inside the suite would
flake when another process (a second agent, a human running `adopt`) changes the real registry mid-run.

**Alternatives rejected**

- Session-scoped before/after hash of the real file inside the suite: flakes under concurrent legitimate writers.
- Change `registry_path()` to refuse the real home under pytest: production code must not know about tests.
- Per-test redirects only (status quo): the defect.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Autouse isolation fixture with the real-home guard | `tests/conftest.py` | AC1, AC2 | suite green; mutation (redirect line removed) leaves the home copy unchanged |
| T2 | Guard tests: paths are inside tmp; the guard raises for a real-home path | `tests/test_isolation.py` | AC1, AC2 | new tests pass; fail with the fixture removed |
| T3 | Evidence: hash of the real registry before/after a full run; record in test-plan Audit | work item | AC1 | recorded hashes |

## Data, API and migration impact

None. Test code only.

## Security and failure modes

No secrets. Failure mode of the guard: an `AssertionError` naming the real path and the test that caused it.

## Rollout and rollback

Merge the PR. Rollback: revert the commit.

## Risks and open points

- A future test that legitimately needs the real home would have to opt out explicitly; none exists and none should.
- Hidden reads of home from code other than the registry are not guarded (only the env redirect protects them).
