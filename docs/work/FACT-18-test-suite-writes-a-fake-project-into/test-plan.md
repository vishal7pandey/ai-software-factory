# FACT-18 — Test plan: Test suite writes a fake project into the real registry

Status: in-review · Risk: low · Jira: FACT-18

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, fixtures with `tmp_path` and `monkeypatch`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_isolation.py::test_registry_and_home_are_inside_tmp, ::test_forgotten_redirect_does_not_touch_the_real_registry | during a test `registry_path()` and `Path.home()` are under tmp; `adopt` with no redirect writes only into tmp | a test that deletes `FACTORY_REGISTRY` still resolves under tmp via the redirected home | n/a: the negative case is AC2 | verified |
| AC2 | unit | tests/test_isolation.py::test_guard_rejects_a_real_home_registry | `registry_path()` under the redirected env returns normally | a path equal to the real registry file is rejected | the guard raises `AssertionError` naming the real path when `FACTORY_REGISTRY` points at it | verified |

## Regression risk

All registry tests (`test_registry.py`, `test_install.py`, `test_integration.py`) must stay green: they set their own `FACTORY_REGISTRY`/`HOME`, which override the fixture. `test_default_location_and_missing_file` deletes the variable and sets its own home; it must still see that home.

## Untestable AC

None.

## Manual checks

AC1 whole-suite check (not an automated test, because the suite cannot hash a file other processes may legitimately change): hash `~/.factory/registry.yaml`, run the full suite, hash again. Recorded in the Audit.

## Audit (after implementation)

Each mutation was applied temporarily, the tests run with `HOME`/`USERPROFILE` pointing at a throw-away copy
of the home directory, then the code was restored.

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `tests/test_isolation.py:14` `test_registry_and_home_are_inside_tmp`, `:21` `test_forgotten_redirect_does_not_touch_the_real_registry` | fixture sets no `HOME`/`USERPROFILE`/`FACTORY_REGISTRY` (all three removed) | both fail |
| AC1 | same | fixture redirects `FACTORY_REGISTRY` only, not `HOME` | both fail (home still real) |
| AC1 | whole suite | the `FACTORY_REGISTRY` redirect line removed from `tests/test_registry.py::test_adopt_list_remove_with_env` (a test that forgets its redirect) | before the fixture existed: home copy hash `5799bead...` -> `54b0a540...`, `sample-app` appears. With the fixture: hash stays `5799bead...` |
| AC2 | `tests/test_isolation.py:38` `test_guard_rejects_a_real_home_registry` | wrapper around `common.registry_path` removed | fails: `DID NOT RAISE AssertionError` |

Whole-suite evidence on the real file: `sha256(~/.factory/registry.yaml)` = `600cd0378ecc...bb1e` before and
after a full run of 274 tests with the fix. (Without the fix the committed suite also left it unchanged, because
every existing test redirects by hand: the defect is the missing harness-level guarantee, see spec.)
