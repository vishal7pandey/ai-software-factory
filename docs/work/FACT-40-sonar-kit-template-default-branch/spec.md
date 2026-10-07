# FACT-40 — Sonar kit template: default branch, project test command, locked deps, doctor check

Status: draft · Risk: medium · Jira: FACT-40
Created: 2026-10-07 · Slug: sonar-kit-template-default-branch

## Problem

The SonarCloud rollout (FACT-41, FACT-42, ADE-55, CPID-40, ADE-26) found that the kit's Sonar template does not fit a real
project without hand edits. (1) A `sonar.yml` created by `factory sync` always triggers on pushes to `main`; ade's default
branch is `master`, so it would never scan after a merge (`adopt` already points the file at the default branch, `sync`
does not). (2) The python template's test step runs plain `pytest -q --cov`, ignoring the project's own test command
(markers, `--deselect` lists, python version), and `sonar.python.version` is the constant 3.12 while ade's CI uses 3.11.
(3) The template's `uv run --with pytest-cov` and its unlocked `uv sync` are reported by SonarCloud itself
(`githubactions:S8544`; the sibling `S7637` flags third-party actions that are not pinned to a commit). (4) Two facts cost
real time and are not written down: on the free plan the SonarCloud project must be public, and its main branch name must
equal the repository's default branch. (5) `factory doctor` cannot tell either problem.

## Users and context

* The owner and agents adopting or syncing a python or node project into the kit; the owner doing the SonarCloud side.
* Code read: `src/swfactory/installer.py` (`_install`, `adopt`, `sync`), `adopt_inspect.py` (`default_branch`,
  `point_at_branch`, `adapt_ci`), `checks.py` (`check_sonar`), `harden.py` (`gh_api`, the stubbable-runner pattern),
  `kit/sonar/*`, `docs/sonarcloud.md`, `docs/ARCHITECTURE.md` 3.9, the factory's own `.github/workflows/sonar.yml`
  (FACT-42), and the live public SonarCloud API (issues, `components/show`, `project_branches/list`).
* Out of the item: ade and chatpid are not edited (their `sonar.yml` and properties are create-mode, so `sync` never
  rewrites them); follow-up tickets carry the exact diffs.

## Goals and non-goals

**Goals**
- A `sonar.yml` and `sonar-project.properties` created by `sync` or `adopt` carry the project's real default branch, the
  project's own test command and the python version its CI uses.
- The template contains nothing SonarCloud flags cheaply: locked dependency use, third-party actions pinned to a commit.
- `docs/sonarcloud.md` states the two facts, with the exact commands.
- `factory doctor` reads, without a token, whether the SonarCloud project exists, is public and has the right main branch.

**Non-goals**
- No rewriting of an existing `sonar.yml` or properties file (create-mode stays create-mode).
- The generated `ci.yml` of a project created by `sync` is not changed here (it still triggers on `main`); noted for a
  follow-up, since this item is about the Sonar files.
- Sibling rule `githubactions:S8541` ("omit `--no-build`") stays: `--no-build` cannot be used when the project itself is an
  editable install (FACT-42). The same rules on the factory's `ci.yml` and `factory-verify.yml`, and the kit's `ci.yml`
  and `factory-verify.yml` templates, stay for the later sweep.
- The node test step is not derived from the project's CI (the ticket is about the python template).
- No SonarCloud write calls from the factory: the branch repair commands are printed and the owner runs them.

## Requirements

- R1. When `sync` or `adopt` creates `.github/workflows/sonar.yml`, its push trigger names the project's default branch
  (origin/HEAD, else the only one of `main`/`master` that exists, else the current branch). An existing file is never changed.
- R2. For a python project the new `sonar.yml` test step is the project's own test command, found as the first `pytest` step
  of the project's `ci.yml` (the one that exists, or, on a fresh adopt, the one being created), rewritten to
  `uv run --locked --no-sync python -m pytest <the original arguments>` with the coverage options added (`--cov` unless the
  command has one, and an XML report `coverage.xml` unless it has one). Markers, `--deselect` lists and paths are kept.
- R3. When there is no `ci.yml`, no pytest step, or the step cannot be reused safely (shell operators, a working directory,
  environment overrides, a GitHub expression, a runner that is not `uv run`/`python -m`/bare `pytest`), the template default is kept
  and a note says why. Nothing is guessed.
- R4. The python version of the job (`setup-python`) and `sonar.python.version` come from the project's CI (`python-version:`,
  `uv python install`, `--python`; several versions are joined with a comma in the property), else from the lower bound of
  `requires-python`, else 3.12.
- R5. Without a `uv.lock` the `--locked` flags are left out (they would fail the job).
- R6. The python template installs only from the lock: `uv sync --locked ...`, `uv run --locked --no-sync python -m pytest ...`,
  no `--with`. A python adopt/sync that creates the workflow prints a note when `pytest-cov` is not in `pyproject.toml`
  (it must be in the locked dev group: `uv add --dev pytest-cov`).
- R7. Both templates pin every third-party action (`astral-sh/setup-uv`, `SonarSource/sonarqube-scan-action`) to a full
  40-character commit SHA with the version in a trailing comment; permissions stay read-only. The factory's own
  `sonar.yml` follows the same rules.
- R8. `docs/sonarcloud.md` states (a) on the free plan the SonarCloud project must be public, and a CI scan of a private
  project succeeds but nothing can be read; (b) the SonarCloud main branch name must equal the repository's default
  branch, a new project is created with main branch `master`, and the repair is `project_branches/delete` of the empty side
  branch followed by `project_branches/rename`, with the exact commands. Its local-scan recipe uses the locked form.
- R9. `factory doctor <project>` adds one `sonar: server` finding, read through the public SonarCloud API with no token:
  OK when the project exists, is public and its main branch equals the repository default branch (read from GitHub through
  `gh`); WARN with the exact repair commands on a mismatch; WARN when the project is not found or not public (anonymous
  access cannot tell the two apart); WARN `unknown (...)` when any step fails. It makes no network call while the
  properties file still has `REPLACE_ME`, and none for a project without a github.com remote.
- R10. The network access of R9 goes through one stubbable function; the test suite never reaches the network.

## Acceptance criteria

- AC1. (R1) A project whose default branch is `master` (origin/HEAD) gets a `sonar.yml` with `push.branches == ["master"]`
  from `sync` and from `adopt`, for python and node; `main` stays `main`; with origin/HEAD unset and a feature branch checked
  out the default is still `master` (the only of main/master); an existing `sonar.yml` is byte-identical after `sync`.
- AC2. (R2) A fixture `ci.yml` whose pytest step has `-m "not integration"`, a path and several `--deselect` lines gives a
  `sonar.yml` test step that contains each of them, `uv run --locked --no-sync python -m pytest`, and `--cov-report=xml:coverage.xml`;
  `uv run --frozen --with pytest-cov pytest -q --cov=pkg` keeps `--cov=pkg`, drops `--frozen` and `--with`, and gets the XML report;
  a command that already writes `--cov-report=xml:coverage.xml` is not given a second one.
- AC3. (R3) Each of: no `ci.yml`, no pytest step, `pytest && other`, a step with `working-directory`, a step with `env`, a `${{ }}`
  expression, `tox`, `make test` keeps the template step, still yields a valid workflow, and prints a note naming the reason (a missing `ci.yml` or an absent pytest step prints no alarm, only the note).
- AC4. (R4) CI with `python-version: "3.11"` gives `setup-python` 3.11 and `sonar.python.version=3.11` (checked on the real python
  kit properties); `uv python install 3.11` the same; a list `["3.10", "3.12"]` gives job 3.10 and property `3.10,3.12`;
  unquoted `3.10` stays `3.10`; no CI version and `requires-python = ">=3.11"` gives 3.11; nothing at all gives 3.12.
- AC5. (R5, R6) A project without `uv.lock` gets `uv sync` and `uv run --no-sync` without `--locked`; the python template
  has `uv sync --locked`, no `--with`, and a note about `pytest-cov` appears exactly when it is missing from `pyproject.toml`.
- AC6. (R7) Both kit templates and the factory's own `sonar.yml` use only actions pinned to a 40-hex SHA with a `# v<version>`
  comment, except `actions/*` (GitHub-owned, major tag); `permissions` are `contents: read` and `pull-requests: read`; the kit's
  existing guard behaviour is unchanged (its tests stay green). After the PR scan, SonarCloud reports no `githubactions:S8544` and no
  `githubactions:S7637` for `.github/workflows/sonar.yml`; `S8541` stays and is named.
- AC7. (R8) Contract test: `docs/sonarcloud.md` contains the public-project fact, the main-branch fact, both API method names
  with `curl` commands that read the token from `$SONAR_TOKEN`, and no `--with pytest-cov`.
- AC8. (R9, R10) With the API stubbed: project public with main `main` and repository default `main` is OK; main `master` vs default
  `main` is WARN containing the `project_branches/rename` command (and the `project_branches/delete` command only when a side branch
  named like the default exists); 404 is WARN "not found or not public"; visibility `private` is WARN; HTTP 500, status 0, malformed JSON, no branch flagged
  main, `gh` unable to read the default branch are each WARN beginning `unknown`; a placeholder properties file and a project without a github.com remote make
  no API call and are not warnings; no output ever contains a token; the autouse guard makes the real network function unreachable
  and the real function maps a URL error to status 0 and an HTTP error to its code.
- AC9. (all) `factory lint`, `factory sync --check .`, `factory verify`, ruff and the full suite pass; the facts of ARCHITECTURE 3.9 match
  the new behaviour.

## Edge cases and failure modes

- origin/HEAD unset and both `main` and `master` exist: the current branch decides; with neither, the current branch.
- A branch name that is not a plain name (spaces, quotes): the trigger is left as `main` (existing `point_at_branch` rule) and a note says so.
- CI pytest step spread over several lines with `\` continuations or a folded `>` scalar: joined into one command.
- Several pytest steps: the first is used and the note says how many there were.
- The CI file does not parse: template kept, note says so.
- SonarCloud unreachable or slow: `unknown` after a 20 second timeout, never an exception, never a changed exit code.

## Non-functional requirements

- Security: no token is read, sent or printed; the doctor request is an anonymous HTTPS GET to `https://sonarcloud.io/api/` with the
  project key validated against `[A-Za-z0-9_.:-]+`; a CI command containing `${{` is never copied into the workflow (script
  injection); template pins follow `.factory/policies/security.md` (no new write permissions).
- Compatibility: Windows and Linux, stdlib and PyYAML only (`AGENTS.md`); output ASCII.
- Idempotence: `adopt` twice and `adopt` then `sync` stay no-ops.

## Assumptions

- Deriving the command from `ci.yml` is the better of the two options the ticket names ("one place"): `ci.yml` is where a project's
  own command, python version and deselect lists already live and are already kept current; `factory.yaml` and the AGENTS commands block
  are free text. Reusing CI's coverage artifact needs a cross-workflow dependency and is rejected.
- `doctor` WARNs (not FAILs) for every Sonar finding, like the existing Sonar lines.
- SHA pins are the versions the repo already uses: `astral-sh/setup-uv` v10.2.0 and `SonarSource/sonarqube-scan-action` v8.3.0
  (the commit the `v8` tag points at today); Dependabot's github-actions updates keep SHA pins current.

## Risks and dependencies

Medium: the rewrite of a command is text surgery on a project's CI; the guard rails are R3 (fall back, never guess) and that it only
runs when the file is created. The template change reaches adopted projects only when they hand-apply it (create mode).
The anonymous API contract (`components/show`, `project_branches/list`) was probed live; an API change makes `doctor` say `unknown`.

## Open questions

None open. Recorded owner delegation for approval: `approve FACT-40 spec --delegated "Vishal Pandey"`.
