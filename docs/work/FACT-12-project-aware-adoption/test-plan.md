# FACT-12 — Test plan: Project-aware adoption

Status: in-review · Risk: medium · Jira: FACT-12

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, fixture factory
roots and projects in `tmp_path` (`tests/test_install.py`), `capsys` for output; run everything with
`uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine). Commands that adopt
would run are injected as a fake runner, so no test needs `uv` or `npm`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_adopt_inspect.py::test_python_template_installs_all_dependency_layouts | real `kit/ci/python.yml` contains `uv sync --all-extras --all-groups`; fixture with pytest only in an optional extra adopted with a recording runner: the first command run is that install | n/a: one template line | a bare `uv sync` line anywhere in the template fails the test | done |
| AC2 | unit | tests/test_adopt_inspect.py::test_trigger_findings | default branch `master`, workflow with `push: branches: [main]` -> finding names file, `master`, `main` | no branch filter, or filter listing `master`, or a glob that matches -> no finding; `on:` read as the YAML key `True` | unparsable workflow -> finding, no crash; `factory-verify.yml` ignored | done |
| AC2 | integration | tests/test_install.py::test_adopt_prints_findings_before_and_report_after | output has a findings block before the plan lines and a result block after | no git remote: default branch falls back to current branch | not a git repo: "unknown", no trigger finding | done |
| AC3 | unit | tests/test_adopt_inspect.py::test_detects_commands_and_commands_section | Makefile targets and `package.json` scripts listed; heading `## Testing` counts as a commands section | nothing detected -> TODO says so; Makefile targets outside the fixed list ignored | heading text only in a code block does not count | done |
| AC3 | integration | tests/test_install.py::test_adopt_inserts_todo_above_block_and_is_idempotent | no commands section -> TODO section sits immediately above the factory block; second adopt leaves the snapshot identical | AGENTS.md absent -> created with TODO then block; CRLF file keeps CRLF | AGENTS.md already has `## Commands` -> bytes outside the block unchanged | done |
| AC4 | unit | tests/test_adopt_inspect.py::test_adapt_ci_drops_failing_steps | fake runner fails ruff step -> returned CI lacks it, has the comment, report names step and last output line; passing steps stay | install step fails -> nothing dropped, report says checks could not run; tool missing on PATH -> same; timeout counts as failure | `check=False` -> runner never called | done |
| AC4 | integration | tests/test_install.py::test_adopt_check_flags | real adopt writes the adapted CI | `--no-check` and `--dry-run` -> runner never called | existing `ci.yml` -> not modified and runner never called | done |
| AC5 | unit | tests/test_adopt_inspect.py::test_ci_push_trigger_uses_default_branch | default branch `master` -> `branches: [master]` | `main` -> text unchanged; unknown -> `main` | n/a: no invalid input | done |
| AC6 | integration | tests/test_install.py::test_sync_check | freshly adopted project -> exit 0 and no file changes | source file changed -> exit 1 listing it; managed file deleted -> exit 1; local edit -> exit 1 (conflict) | not adopted -> FactoryError | done |
| AC6 | integration | tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit | the factory repo itself: `sync --check` is 0 | n/a | an out-of-date managed copy fails the test | done |
| AC7 | unit | tests/test_verify.py::test_docs_only_changed_files | `feature/` branch at `draft`, list only `docs/work/...` -> pass | empty list -> pass | list with `src/x.py` -> fail; item missing -> fail; no option -> unchanged; unreadable file -> strict | done |
| AC8 | integration | whole suite via CI (ubuntu-latest and windows-latest) | all tests pass | Windows paths and CRLF | n/a: the suite either passes or not | done |

## Regression risk

`tests/test_install.py` adopt/dry-run/idempotence tests run adopt on fixture projects: they must keep
passing with checks on, so the shared `proj` fixture injects a fake runner (or `--no-check`). The old
`test_changed_files_from_is_accepted_and_ignored` in `tests/test_verify.py` becomes the AC7 test.
`tests/test_doctor.py` compares installed files with the kit; the CI template edit must not break it.

## Untestable AC

None. The default subprocess runner is checked once against a trivial real command.

## Manual checks

AC2-AC5 also get an end-to-end proof: `adopt --dry-run` and a real adopt against a throwaway copy of an
adopted project in a temp directory (never a real project). The transcript goes into `notes.md`.

## Audit (after implementation)

Each behaviour was broken on purpose (mutation), the named tests were run, and the code restored.

| AC | Real tests | Mutation tried | Caught by |
|----|-----------|----------------|-----------|
| AC1 | `tests/test_adopt_inspect.py::test_python_template_installs_all_dependency_layouts` | (template line; asserted directly, and the recorder must see the install command first) | n/a, direct assertion |
| AC2 | `test_adopt_inspect.py::test_trigger_findings`, `::test_default_branch`; `tests/test_install.py::test_adopt_prints_findings_before_and_report_after` | trigger finding disabled | `test_trigger_findings` |
| AC3 | `test_adopt_inspect.py::test_detects_commands_and_commands_section`; `test_install.py::test_adopt_inserts_todo_above_block_and_is_idempotent`, `::test_adopt_leaves_existing_commands_section_alone`, and the four rewritten block tests (CRLF, rerun, existing AGENTS.md, fresh adopt) | TODO insertion disabled | the install tests |
| AC4 | `test_adopt_inspect.py::test_adapt_ci_drops_failing_steps`, `::test_adapt_ci_install_failure_or_missing_tool_drops_nothing`, `::test_adapt_ci_check_off_never_runs_commands`, `::test_project_commands_do_not_inherit_the_factorys_virtualenv`, `::test_default_runner_runs_a_real_command`; `test_install.py::test_adopt_check_flags`, `::test_no_check_flag_reaches_adopt` | failing step kept; install failure treated as droppable; checks run in `--dry-run` | all three caught |
| AC5 | `test_adopt_inspect.py::test_ci_push_trigger_uses_default_branch` | branch swap disabled | `test_ci_push_trigger_uses_default_branch` |
| AC6 | `test_install.py::test_sync_check`; `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit` | `sync --check` always returns 0 | `test_sync_check` |
| AC7 | `tests/test_verify.py::test_docs_only_changed_files` | docs-only rule never applies; the path-prefix test removed (`startswith("")`) | both caught. A first mutation (`return True or ...`) was not applied because the code had been reformatted, so it was redone as the prefix mutation |
| AC8 | full suite, 271 tests locally; CI on ubuntu and windows | n/a | see PR |

Real-world finding while proving AC4 on a throwaway copy (notes.md): the first real run printed a uv
warning as the "last output line" because the factory's own `VIRTUAL_ENV` leaked into the project's
`uv run`. Fixed (`project_env`) and the reported line now prefers the last error/failure line.
