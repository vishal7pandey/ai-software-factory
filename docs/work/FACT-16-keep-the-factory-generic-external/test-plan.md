# FACT-16 — Test plan: Keep the factory generic: external project registry

Status: draft · Risk: low · Jira: FACT-16

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, fixtures with `tmp_path` and `monkeypatch`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_registry.py::test_adopt_list_remove_with_env | `FACTORY_REGISTRY=<tmp>/r.yaml`; `adopt` writes `projects` entry and `paths` entry; `project list` shows it; `project remove` deletes both | relative `FACTORY_REGISTRY` resolves against the cwd; re-adopt updates the entry instead of duplicating | remove of an unknown name exits 1 with a message, file unchanged | planned |
| AC2 | integration | tests/test_registry.py::test_default_location_and_missing_file | no env var, `HOME`/`USERPROFILE` redirected to tmp: `list` exits 0 with "no registry yet"; after `adopt` the file exists at `<home>/.factory/registry.yaml` | parent directory `.factory/` does not exist yet and is created | `FACTORY_REGISTRY` pointing into an unwritable location: error names the path, kit already installed, exit 1 | planned |
| AC3 | unit | tests/test_integration.py::test_repo_has_no_registry_dir | `FACTORY_ROOT/registry` does not exist and `.gitignore` has no `registry` line | n/a: file or directory either exists or not | a `registry/` directory created in a fixture root is rejected by lint (see AC4) | planned |
| AC4 | unit | tests/test_lint.py::test_instance_data_rules | clean fixture root passes | a hostname such as `x.atlassian.net` in `docs/` fails; the same string in `tests/` is ignored | a fixture with `registry/projects.yaml` fails with a message naming the path | planned |
| AC5 | manual | n/a (manual check below) | search finds hits only in `.factory/`, `.claude/`, `.github/` and this work item | n/a: a search either finds a hit or not | any hit in `src/`, `kit/`, `skills/`, `policies/`, `templates/`, `registry/`, `tests/` or `docs/` outside this work item fails the AC | planned |
| AC6 | integration | whole suite via CI (ubuntu-latest and windows-latest) | all tests pass | Windows path separators and home-directory handling | n/a: the suite either passes or not | planned |

## Regression risk

`tests/test_install.py` (16 registry references) and `tests/test_integration.py` (2) monkeypatch `registry_path` and `local_registry_path`; they are rewritten to use `FACTORY_REGISTRY` and must keep covering the same behaviour (upsert, no duplicate, remove). The adopt, sync and new commands must stay green: registry writing moves to the end of adopt, and a registry error must not undo the installed kit.

## Untestable AC

None. AC5 is checked manually because an automated test would have to contain the very names it forbids.

## Manual checks

AC5: from the repo root run a search of tracked files (excluding `uv.lock`) for the maintainer's name, the former Jira key and the real project names (the list is in the Jira ticket FACT-16). Expected: hits only under `.factory/`, `.claude/`, `.github/` and in `docs/work/FACT-16-*`.

## Audit (after implementation)

To be filled after implementation: per row, the real test location and how it was confirmed to fail when the behaviour is broken.
