# FACT-43 — Test plan: Contain installer writes

Status: draft · Risk: low · Jira: FACT-43 (also FACT-44, FACT-45)

Test framework and conventions found: pytest, `tests/test_*.py`; `tests/test_install.py` has a fixture factory
root (`factory`), a project (`proj`), `run(...)` and `snapshot(...)`; run all with
`uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_install.py::test_a_manifest_file_dest_outside_the_project_is_rejected_before_any_write | n/a: the unchanged shipped-style fixture adopts in every existing install test | `../x`, `a/../../x`, an absolute path and `../proj-evil.txt` (shares the project dir name as a prefix), in `create` and `managed` mode (8 cases) | adopt raises "outside the project", the project tree is byte-identical and nothing exists outside | verified |
| AC1 | integration | tests/test_install.py::test_a_manifest_dir_dest_outside_the_project_is_rejected_before_any_write | n/a: see above | `../elsewhere`, `docs/../../elsewhere` for a `dirs` entry | same: rejection before any write, no directory created outside | verified |
| AC2 | integration | tests/test_install.py::test_a_skill_target_outside_the_project_is_rejected_by_sync | n/a: existing sync tests | `skill_targets: ["../outside-skills"]` in the project's own `factory.yaml` | sync raises, tree unchanged, outside dir not created | verified |
| AC2 | integration | tests/test_install.py::test_a_dest_reached_through_a_symlink_that_leaves_the_project_is_rejected | n/a: see above | `.github` is a symlink (junction on Windows) to a directory outside | adopt raises, nothing written into the outside directory | verified |
| AC3 | integration | tests/test_install.py::test_new_rejects_a_template_path_that_climbs_out_of_the_new_project | n/a: `test_new_substitutes_renames_inits_and_adopts` covers the happy path | a template path `../evil.txt` (Path subclass whose `rglob` climbs) | `new` raises, `evil.txt` exists neither beside nor inside the project | verified |
| AC3 | integration | tests/test_install.py::test_the_registry_is_not_written_through_a_symlink_that_leaves_its_directory | n/a: `test_registry.py` and `test_install.py` registry tests keep the header-preserving write green | registry file is a symlink to another directory | `project_add` raises, the link target keeps its content (skipped without symlink rights) | verified |
| AC4 | integration | the full suite, plus the Sonar API after merge | existing tests stay green (482 passed) | n/a: manual | an issue still OPEN after the scan keeps the Bug In Progress with a dismissal proposal | planned |

## Regression risk

`tests/test_install.py` (adopt/sync/new/project), `tests/test_registry.py` (header-preserving registry write, now a
single write), `tests/test_isolation.py` (registry path guard). All stay green; nothing needed updating.

## Untestable AC

None. AC4's scanner half is a property of the live service (manual checks).

## Manual checks

- AC4: after merge and the push scan on main, read the three issues from the Sonar API
  (`issues/search?issues=<key>&componentKeys=vishal7pandey_ai-software-factory`) and record the status in Jira.

## Audit (after implementation)

2026-10-06. Failing first: on `d4126a6` the 11 new tests failed with `DID NOT RAISE FactoryError` (1 skipped,
registry symlink: no symlink rights on this Windows machine; the directory-symlink test uses a junction). After the
fix: full suite 482 passed, 1 skipped (the registry symlink test, which runs on Linux CI). Deliberate breaks, each
restored afterwards (`git diff` shows only the intended change):

| Mutation | Result |
|----------|--------|
| M1 plan-time check removed from `_plan_item` | `test_a_manifest_file_dest_outside...` fails (earlier files were already written, the tree differs) |
| M3 plan-time check without `+ os.sep` (`startswith(base)`) | the `../proj-evil.txt` case fails (sibling-prefix escape) |
| M4 `new_project` template check removed | `test_new_rejects_a_template_path_that_climbs...` fails |
| M5 plan-time `realpath` replaced by `abspath` | still passes: the write-time `realpath` check in `_install` catches the symlink (defence in depth, by design) |
| M2 write-time check removed | still passes: the plan-time check catches every case first (redundant by design; a link created between plan and write is not simulated) |
| Registry check removed (`_save_registry`) | the symlink test cannot run here; checked with a script that fakes `os.path.realpath` for the registry file: with the check the write is refused, without it the write goes to the redirected path |
