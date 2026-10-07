# FACT-40 — Sonar kit template: default branch, project test command, locked deps, doctor check

Status: draft · Risk: medium · Jira: FACT-40
Created: 2026-10-07 · Slug: sonar-kit-template-default-branch · Spec: spec.md

## Summary

A new module `src/swfactory/sonar.py` renders the python `sonar.yml` and `sonar-project.properties` from what the project already has
(its `ci.yml`, `pyproject.toml`, `uv.lock`, default branch) at the moment the create-mode files are written, in `adopt` and in `sync`.
The kit templates become lock-only and SHA-pinned, `docs/sonarcloud.md` gets the two facts, and `checks.check_sonar` gains a
`sonar: server` finding that reads the public SonarCloud API through one stubbable function.

**Size:** M

## Current state

* `installer._install` fills `{{project_key}}` for create-mode items and, only when `inspection` is passed (adopt), calls
  `adopt_inspect.point_at_branch` on the sonar workflow; `sync` passes no inspection, so it never points the trigger.
* `adopt_inspect.default_branch` is origin/HEAD, else the current branch (a feature branch checked out during `sync` would win).
* `kit/sonar/python.yml` runs `uv sync --all-extras --all-groups` and `uv run --locked`-less `--with pytest-cov`; the properties file has
  `sonar.python.version=3.12`. The factory's own `.github/workflows/sonar.yml` is a hand copy checked by `tests/test_sonar_self.py`.
* `checks.check_sonar` reads the secret list through `harden.gh_api`; conftest's autouse `no_real_gh` replaces `harden._run_gh`.
* Live SonarCloud issues for `.github/workflows/sonar.yml` on `main` (public API): `S7637` x2 (setup-uv line 51, scan action line 61),
  `S8541` x2 (line 55 `uv sync`, line 58 `uv run`), `S8544` x1 (line 55 `uv sync`). Anonymous `components/show` answers 200 with
  `visibility`; an unknown or private key answers 404; `project_branches/list` gives `branches[].isMain`.
* Commands: `uv run python -m pytest -q`, `uv run ruff check . && uv run ruff format --check .`, `uv run python -m swfactory.cli lint`.

## Approach

Pure functions in `sonar.py` (no I/O except reading the project's files and the one network function), called from `_install` after the
CI item is adapted, so a fresh adopt reads the CI it is about to write. Every rewrite falls back to the template text and returns a note
(R3); notes are printed after the action lines. `default_branch` gets the main/master rule. The doctor check is a small reader
(`read_project`) that returns a state, and `check_sonar` turns it into one `Finding`. The network function is `_request(url)`, the only
place that opens a connection; conftest replaces it like `_run_gh`.

**Alternatives rejected**
- Read the test command from `factory.yaml` or the AGENTS commands block: free text, would add a second place to keep in step with CI.
- Reuse the CI job's coverage artifact (`needs:` across workflows): couples two workflows and breaks for PRs from forks and for `workflow_run` limits.
- A `${{ }}` template variable for the command at run time: cannot express a project's multi-line deselect list safely.
- `--no-build` to clear `S8541`: breaks the editable install of the project (FACT-42).

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Tests first: render, default branch, notes, template pins, docs contract, doctor with stubs, guard (all red) | `tests/test_sonar_render.py`, `tests/test_sonar_server.py`, `tests/test_sonar.py`, `tests/test_sonar_self.py`, `tests/conftest.py` | AC1-AC8 | `uv run python -m pytest -q tests/test_sonar*.py` fails for the new behaviour |
| T2 | `default_branch`: main/master rule; `sync` and `adopt` both point a new `sonar.yml` | `src/swfactory/adopt_inspect.py`, `src/swfactory/installer.py` | AC1 | AC1 tests green |
| T3 | `sonar.py` render: version, command, locked flags, notes, pytest-cov note; wire into `_install` | `src/swfactory/sonar.py`, `src/swfactory/installer.py` | AC2-AC5 | AC2-AC5 tests green, sync/adopt idempotence tests |
| T4 | Templates: lock-only, SHA pins, header comment; the factory's own `sonar.yml` | `kit/sonar/python.yml`, `kit/sonar/node.yml`, `.github/workflows/sonar.yml` | AC5, AC6 | template and self tests green; PR scan |
| T5 | Docs: public project, main branch, commands, locked local recipe; ARCHITECTURE 3.9 two lines | `docs/sonarcloud.md`, `docs/ARCHITECTURE.md` | AC7, AC9 | contract test green |
| T6 | Doctor: `sonar.read_project`, `http`, `check_sonar` finding, guard fixture | `src/swfactory/sonar.py`, `src/swfactory/checks.py`, `tests/conftest.py` | AC8 | AC8 tests green; real run read-only against the factory project |
| T6b | `sonar.tests=.` in both properties templates and the repo's own file; python inclusions `**/tests/**`; doctor finding `sonar: tests`; docs line; verify empirically on the PR scan log (message gone, no overlap error, sources analysed), numbers before and after from the public API | `kit/sonar/*.properties`, `sonar-project.properties`, `src/swfactory/checks.py`, `docs/sonarcloud.md`, tests | AC10, AC11 | tests green; PR scan log read with `gh run view <id> --log` |
| T7 | Gates and audit: lint, `sync --check .`, verify, ruff, full suite; mutation audit | all | AC9 | commands exit 0; audit table |

## Data, API and migration impact

No schema, no new CLI flag. `checks.check_sonar` gains an optional `fetch` argument. Adopted projects keep their files (create-mode); `docs/sonarcloud.md`
and the PR list what an owner hand-applies. New outbound request: anonymous GET to `https://sonarcloud.io/api/` from `factory doctor` only.

## Security and failure modes

No token anywhere. The project key is validated before it enters a URL. A CI command with `${{` is never copied into a workflow. Third-party
actions are pinned to commit SHAs (supply chain). Failures of the network read are `unknown`, never raise, never change the exit code beyond
a warning count. Timeout 20 seconds.

## Rollout and rollback

Merge to `main`; the factory's own Sonar job on the PR and on `main` is the proof. Revert the merge commit to roll back; nothing outside the repo changes.

## Risks and open points

- Sonar might flag the new `urllib` call (e.g. an S5332 style rule): read the PR analysis before merging and fix inside the PR.
- The `uv sync --locked` form might not clear `S8544`/`S8541` on the install line: the PR analysis decides; whatever stays is named.
- `--cov-fail-under` in a project's own command fails the Sonar job when coverage is low: intended (same as CI), and said in the template comment.
