# FACT-18 — Test suite writes a fake project into the real registry

Status: in-review · Risk: low · Jira: FACT-18

## Repro

Environment: `main` @ 41d5825 (after FACT-12 and FACT-16 merged), Windows, Python 3.12.

1. Back up `~/.factory/registry.yaml` and hash it.
2. Remove the `tests/test_registry.py` redirect of the registry in `test_adopt_list_remove_with_env`
   (the `monkeypatch.setenv("FACTORY_REGISTRY", ...)` line), i.e. simulate any test, present or future, that
   calls `adopt` and forgets to redirect the registry.
3. Run `uv run python -m pytest -q tests/test_registry.py` with `HOME`/`USERPROFILE` pointing at a throw-away
   copy of the home directory (so the real file is never touched while reproducing).

Automated repro: none can exist yet; that is the defect (see Root cause). The mutation above produces:
the copy's hash changes from `5799bead...` to `54b0a540...` and a `sample-app` entry appears in the copy.

Reproducibility: the original report (a developer's real registry gained `sample-app`) happened during
FACT-16 development. On current `main` the suite as committed does NOT leak: a full run against the real
`~/.factory/registry.yaml` left its hash unchanged (`600cd037...` before and after). Every existing test
redirects the registry by hand; the leak returns the moment one test forgets to.

## Expected

A test run never reads or writes the developer's real home (`~/.factory/`), whatever any single test does.
The factory's own ARCHITECTURE 3.6 says the registry is user-level data outside the repo; tests must not
share it.

## Actual

Isolation is opt-in, per test (`monkeypatch.setenv("FACTORY_REGISTRY", ...)` repeated in each test or
fixture). Nothing stops a new test, or a test that deletes the variable, from resolving
`Path.home()/".factory"/"registry.yaml"`, and nothing fails loudly when it does. A leaked entry is silent and
stays in the developer's registry.

## Root cause (with evidence)

- Where: `tests/conftest.py` has no registry/home isolation; `src/swfactory/common.py:41-49`
  (`registry_path()`) falls back to `Path.home()/".factory"/"registry.yaml"` whenever `FACTORY_REGISTRY` is unset.
- Why it fails: protection lives in individual tests, not in the harness. FACT-16 moved the registry from the
  repo to the user's home; the old per-test monkeypatches protected the old location only, and the new
  location needed a harness-level guard that was never added.
- Introduced by: FACT-16 (PR 4), `bef2e68`.
- Evidence: the mutation above (hash of the home copy changes); `grep -n "FACTORY_REGISTRY" tests/` shows the
  redirect repeated per test and absent from `conftest.py`.

## Blast radius

- Any test that reaches `adopt`, `project add|remove|list` or `registry_path()`: `tests/test_registry.py`,
  `tests/test_install.py`, `tests/test_integration.py`, `tests/test_adopt_inspect.py`, `tests/test_work.py`.
- Anything else that reads `Path.home()` (none today besides the registry).
- Data already wrong: the developer's `~/.factory/registry.yaml` carries a stale `paths.sample-app` entry
  pointing into an old pytest temp directory. Not repaired by this item (the owner asked to leave the file as it is).
- Other projects' registries are unaffected: only the one shared file.

## Regression criterion (AC1)

AC1: Running the whole suite leaves `~/.factory/registry.yaml` byte-identical, including when a test forgets
its own redirect. Verified two ways, recorded in `test-plan.md`: (a) hash of the real file before and after a
full run; (b) the mutation from Repro (redirect line removed) leaves the home copy's hash unchanged once the
autouse fixture exists, and changes it on the current code.

AC2: A test that resolves the registry to a path under the real home fails loudly with an assertion that says
so, instead of passing silently. A guard test asserts that, during a test, `registry_path()` and `Path.home()`
are inside the test's temp directory.

## Fix constraints

Test-only change (`tests/conftest.py` plus one test file). No change to `src/`. Must work on Windows and Linux
(`HOME` and `USERPROFILE`). Must not make the suite fail because another process legitimately changes the
real registry while the suite runs, so the guard is path-based, not a before/after hash inside the suite.

## Risks

Low: tests only. A test that deliberately wants a specific registry still sets `FACTORY_REGISTRY` itself, which
overrides the fixture's value. Rollback: revert the commit.
