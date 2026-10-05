# FACT-16 — Test plan: Keep the factory generic: external project registry

Status: in-review · Risk: low · Jira: FACT-16

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, fixtures with `tmp_path` and `monkeypatch`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_registry.py::test_adopt_list_remove_with_env | `FACTORY_REGISTRY=<tmp>/r.yaml`; `adopt` writes `projects` entry and `paths` entry; `project list` shows it; `project remove` deletes both | relative `FACTORY_REGISTRY` resolves against the cwd; re-adopt updates the entry instead of duplicating | remove of an unknown name exits 1 with a message, file unchanged | done |
| AC2 | integration | tests/test_registry.py::test_default_location_and_missing_file | no env var, `HOME`/`USERPROFILE` redirected to tmp: `list` exits 0 with "no registry yet"; after `adopt` the file exists at `<home>/.factory/registry.yaml` | parent directory `.factory/` does not exist yet and is created | `FACTORY_REGISTRY` pointing into an unwritable location: error names the path, kit already installed, exit 1 | done |
| AC3 | unit | tests/test_lint.py::test_repo_has_no_registry_dir | `FACTORY_ROOT/registry` does not exist and `.gitignore` has no `registry` line | n/a: file or directory either exists or not | a `registry/` directory created in a fixture root is rejected by lint (see AC4) | done |
| AC4 | unit | tests/test_lint.py::test_instance_data_rules | clean fixture root passes | a hostname such as `x.atlassian.net` in `docs/` fails; the same string in `tests/` is ignored | a fixture with `registry/projects.yaml` fails with a message naming the path | done |
| AC5 | manual | n/a (manual check below) | search finds hits only in `.factory/`, `.claude/`, `.github/` and this work item | n/a: a search either finds a hit or not | any hit in `src/`, `kit/`, `skills/`, `policies/`, `templates/`, `registry/`, `tests/` or `docs/` outside this work item fails the AC | done |
| AC6 | integration | whole suite via CI (ubuntu-latest and windows-latest) | all tests pass | Windows path separators and home-directory handling | n/a: the suite either passes or not | done |

## Regression risk

`tests/test_install.py` (16 registry references) and `tests/test_integration.py` (2) monkeypatch `registry_path` and `local_registry_path`; they are rewritten to use `FACTORY_REGISTRY` and must keep covering the same behaviour (upsert, no duplicate, remove). The adopt, sync and new commands must stay green: registry writing moves to the end of adopt, and a registry error must not undo the installed kit.

## Untestable AC

None. AC5 is checked manually because an automated test would have to contain the very names it forbids.

## Manual checks

AC5: from the repo root run a search of tracked files (excluding `uv.lock`) for the maintainer's name, the former Jira key and the real project names (the list is in the Jira ticket FACT-16). Expected: hits only under `.factory/`, `.claude/`, `.github/` and in `docs/work/FACT-16-*`.

## Audit (after implementation)

Each test was confirmed to fail by temporarily breaking the behaviour it covers (mutation), then
restoring the code. Run: `uv run python -m pytest -q tests/test_registry.py tests/test_lint.py tests/test_install.py`.

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `tests/test_registry.py::test_adopt_list_remove_with_env`, `::test_remove_unknown_leaves_file_unchanged`, `::test_relative_env_resolves_against_cwd`; `tests/test_install.py::test_adopt_upserts_registry_and_paths`, `::test_project_add_list_remove` | `registry_path()` ignores `FACTORY_REGISTRY`; `project remove` stops removing `paths` | both mutations fail the suite |
| AC2 | `tests/test_registry.py::test_default_location_and_missing_file`, `::test_unwritable_registry_is_an_error_after_the_kit_is_installed` | `project list` no longer checks for a missing file; the write error is re-raised raw instead of a `FactoryError` naming the path | both fail |
| AC3 | `tests/test_lint.py::test_repo_has_no_registry_dir` | (not mutated; asserts the real repo state: no `registry/`, no `registry` in `.gitignore`) | n/a, repo state |
| AC4 | `tests/test_lint.py::test_instance_data_rules`, `::test_registry_directory_fails_lint` | registry-dir rule off; hostname rule off; `lint_generic` removed from `lint_factory` | all three fail. The first version of the wiring test passed with the rule unwired (the fixture already failed on a missing manifest); it now builds a valid kit first |
| AC5 | manual, below | n/a | done |
| AC6 | full suite: 254 passed locally; CI on ubuntu and windows | n/a | see PR |

AC5 manual check (tracked files, excluding `uv.lock` and `docs/work/`): the search finds only
`LICENSE` (the copyright holder line), the generic word "Scrum" in `docs/jira-workflow.md`, and the
forbidden-hostname literal in the lint rule and its tests. No project names, no personal name in
examples, no instance keys. The spec's AC5 wording was amended accordingly (see `notes.md`).
