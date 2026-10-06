# FACT-35 — SonarCloud scan in the kit

Status: draft · Risk: medium · Jira: FACT-35
Created: 2026-10-05 · Slug: sonarcloud-scan-in-the-kit

## Problem

FACT-11 wants static analysis whose findings the coding agent can read, fix and close. CodeQL and
Dependabot are covered by `factory harden` (FACT-33) and the findings loop by FACT-34, but code
quality findings (bugs, code smells, security hotspots, coverage, duplication) have no scanner in the
kit. Each project would have to hand-write a SonarCloud workflow, a `sonar-project.properties`, and
remember the token, the organisation, the project key and the "turn Automatic Analysis off" step. A
workflow that needs a secret also breaks on fork PRs and on repos where the secret was never set, which
makes people delete it. The owner decided (2026-10-05, ticket comment) on **SonarCloud**
(https://sonarcloud.io), free for public repositories, reachable from GitHub Actions.

## Users and context

* **A project owner adopting the factory** (the human): wants `factory adopt` to lay down a working,
  safe-by-default SonarCloud setup and `factory doctor` to say what is still missing. Does the
  SonarCloud-side steps (organisation, project import, token) and runs `gh secret set` themselves.
* **The coding agent**: pulls Sonar issues through its SonarQube tools (skill `factory-findings`,
  FACT-34, unchanged here) once the project is analysed.

Read to ground this: `docs/ARCHITECTURE.md` (the Treaty: file modes 3.1, CLI 3.7, `gh_api` 3.8),
`kit/manifest.yaml`, `kit/ci/*.yml`, `src/swfactory/installer.py` (`collect_items`, `_plan_item`,
`_install`), `src/swfactory/adopt_inspect.py`, `src/swfactory/checks.py`, `src/swfactory/harden.py`
(`gh_api`, `repo_slug`), `tests/test_harden.py` (the `FakeGh` pattern), FACT-11 and FACT-35 comments.

## Goals and non-goals

**Goals**
- `factory adopt` lays a `sonar.yml` GitHub Actions workflow and a `sonar-project.properties` into
  python and node projects, as create-mode files (never overwritten by `sync`).
- The workflow can never fail a fork PR or an unconfigured repository: it skips with a notice.
- `factory doctor <path>` reports whether the `SONAR_TOKEN` Actions secret exists (name only) and
  whether the properties file still holds the placeholder.
- A written how-to: organisation, project, Automatic Analysis off, token, secret, local scan.

**Non-goals**
- Self-hosted SonarQube (URL handling beyond an optional `SONAR_HOST_URL` repository variable that
  defaults to `https://sonarcloud.io`).
- Making the quality gate a required check (R4 of the ticket: a separate human decision per project).
  The workflow stays a plain scan; SonarCloud itself reports the gate on the PR once the project is
  bound to GitHub; the docs say how to make the job fail on a failed gate.
- Stacks `docs` and `other` (no code to analyse; no real project has needed it, ROADMAP rule).
- Changing `factory-findings` or `policies/findings.md` (FACT-34/FACT-38); creating the SonarCloud
  organisation or project, or setting the secret (owner actions; the factory never touches a token).
- Checking from `doctor` that the project exists on the server (the ticket's R2 second half): it needs
  a SonarCloud token on the doctor machine, and the factory never reads one. The agent's SonarQube
  tools answer that question (AC8).

## Requirements

- R1. The kit contains a `sonar.yml` workflow template for each of the stacks `python` and `node`,
  registered in `kit/manifest.yaml` as a `create`-mode file with destination
  `.github/workflows/sonar.yml`.
- R2. The workflow scans on push to the default branch and on pull requests whose head is in the same
  repository, checks out with full history (`fetch-depth: 0`), uses `SonarSource/sonarqube-scan-action`
  pinned to the current major (`v8`), takes the token only from `secrets.SONAR_TOKEN`, and takes the
  organisation and project key only from `sonar-project.properties`.
- R3. A guard step runs first and exits 0 with a clear notice (and no scan) when `SONAR_TOKEN` is empty,
  when `sonar-project.properties` is missing, or when it still contains the placeholder. It never
  prints the token. Every later step runs only when the guard enabled the scan.
- R4. The kit contains a `sonar-project.properties` template per stack (`python`, `node`), `create`
  mode, destination `sonar-project.properties`. Python points at `coverage.xml`, node at
  `coverage/lcov.info`. The project key is `<owner>_<repo>` taken from the GitHub `origin` remote when
  `adopt` runs; the organisation key, which `adopt` cannot know, is the marked placeholder
  `REPLACE_ME_SONAR_ORGANIZATION`. Without a GitHub remote the project key is also a marked
  placeholder (`REPLACE_ME_OWNER_REPO`).
- R5. On `adopt`, a new `sonar.yml` points its push trigger at the project's default branch, as the
  generated `ci.yml` already does.
- R6. `factory doctor <path>` on a project that has the Sonar files reports (a) whether the repository
  Actions secret `SONAR_TOKEN` exists, as present / not set / unknown, by name only through the one
  stubbable GitHub access point (`harden.gh_api`), never reading, printing or storing any value, and
  (b) whether `sonar-project.properties` still contains the placeholder (comment lines are ignored).
  On a project with neither Sonar file it prints one notice and makes no GitHub call. No Sonar finding
  can make `doctor` exit 1.
- R7. Docs: `docs/sonarcloud.md` explains how to create the organisation and import the project, turn
  Automatic Analysis off, generate a token, set the secret (`gh secret set SONAR_TOKEN`, run by the
  owner) and run a local scan; `docs/ARCHITECTURE.md` and `README.md` list the new files and doctor
  lines; `policies/security.md` gets one pointer line.

## Acceptance criteria

- AC1. (R1, R4, R5) After `factory adopt` of a python project whose `origin` is
  `https://github.com/me/proj.git`, `.github/workflows/sonar.yml` and `sonar-project.properties` exist;
  the properties hold `sonar.projectKey=me_proj`, `sonar.organization=REPLACE_ME_SONAR_ORGANIZATION` and
  the `coverage.xml` report path. The same for a node project gives the `coverage/lcov.info` path and no
  `coverage.xml`. A project with no GitHub remote gets the marked project-key placeholder. A project
  whose default branch is `trunk` gets `branches: [trunk]` in `sonar.yml`. Stacks `docs` and `other` get
  neither file.
- AC2. (R1) Both files are `create` mode for both stacks in the manifest; `factory sync` right after
  `adopt` reports "up to date"; after the project edits either file (or sets the organisation) `sync`
  leaves the bytes unchanged and exits 0; `sync --check` ignores them; neither path is recorded in
  `factory.yaml › managed`. `factory lint` passes with the new manifest entries.
- AC3. (R2) For both stack templates: triggers are `push` on one branch and `pull_request` (never
  `pull_request_target`); the job runs only when the event is not a pull request or the PR head repo
  equals the current repository; checkout has `fetch-depth: 0`; the scan step uses
  `SonarSource/sonarqube-scan-action@v8` with `SONAR_TOKEN` from `secrets.SONAR_TOKEN`; no workflow text
  passes `sonar.organization` or `sonar.projectKey`; permissions grant no write scope; the python
  template produces `coverage.xml` and the node template an lcov report before the scan.
- AC4. (R3) Running the guard step's script locally with bash: with `SONAR_TOKEN` unset or empty it
  exits 0, prints a `::notice` naming the secret, and writes `enabled=false` to `$GITHUB_OUTPUT`; with
  a token but a missing properties file, or a placeholder in a non-comment line, the same; with a
  token and a filled properties file it writes `enabled=true`; a `REPLACE_ME` that appears only in a
  comment does not block the scan; in no case does the token value appear in its output. Every step
  after the guard in both templates is conditioned on `steps.guard.outputs.enabled == 'true'`.
- AC5. (R6) Given a project with the Sonar files and a stubbed `gh_api` answering `GET
  repos/{o}/{r}/actions/secrets`: a list containing `SONAR_TOKEN` gives an `ok` "present" line; a list
  without it gives "not set" (a WARN when the properties are already filled, an OK notice while they
  still hold the placeholder: setup has not started); `gh` unusable or HTTP 403/404/500 gives WARN
  `unknown` naming only the status; a list longer than one page that does not contain the name gives
  `unknown`. Whatever values the stub response carries (a marker string in `value` fields and in an
  error body), they are never printed. Only GET calls are made. A project with no github.com remote
  gets one OK `skipped` line instead.
- AC6. (R6) `doctor` prints a WARN naming the placeholder keys when `sonar-project.properties` still
  has them and the secret is present (the scan would be skipped), an OK "not set up yet" notice when
  the secret is absent; comment lines never count; a filled file gives OK. A project with neither Sonar
  file gets one OK "not configured" notice and `gh_api` is never called. `doctor` exits 0 in every one
  of these cases, and a freshly adopted local-only project still has a doctor output with no WARN or FAIL
  (`tests/test_integration.py` keeps passing).
- AC7. (R7) `docs/sonarcloud.md` exists and contains each of: the organisation and project import steps,
  "Automatic Analysis" off, the token generation path, `gh secret set SONAR_TOKEN`, the project key
  convention, and a local `sonar-scanner` run that reads the token from the environment;
  `policies/security.md` has exactly one line pointing at it; `docs/ARCHITECTURE.md` lists the kit files
  and the doctor lines; `factory lint` and `factory sync --check .` pass.
- AC8. (ticket AC4, live, owner-gated) After the owner supplies the organisation key and the secret, a
  first real analysis of a project appears in SonarCloud and the SonarQube tools list it (project count
  from 0 to 1); recorded on FACT-35. Not testable in this PR: waits for the owner.
- AC9. (ticket AC5, live, owner-gated) One Sonar issue goes through the findings loop end to end
  (`factory-findings`). Not testable in this PR: waits for AC8.

## Edge cases and failure modes

- Secret absent (fork PR, Dependabot PR, unconfigured repo): the guard notice, job succeeds.
- Fork PRs are excluded at job level as well, so no secret expression is ever evaluated for them.
- Token set but organisation still the placeholder: scan skipped with a notice naming the file (a failed
  scan with an opaque authorisation error is the alternative this avoids).
- `sonar-project.properties` deleted but the workflow kept: skipped with a notice.
- `gh` missing, logged out, or without repo admin rights: `unknown`, never `not set`.
- Over 100 repository secrets: only one page is read; a name not on it is `unknown`, not `not set`.
- The secret exists at organisation level only: the repository list will not show it; doctor says "not
  set" for the repo. Documented, accepted (the owner sets it per repository).
- `sync` after the properties file was deleted recreates it from the template (create-mode semantics).
- Project key characters: the owner and repo names are validated by `repo_slug` (letters, digits,
  `_ . -`), all legal in a Sonar key.

## Non-functional requirements

- Security (`policies/security.md`): the token reaches the scan only as the `SONAR_TOKEN` environment
  variable of the steps that need it; the guard receives it in `env`, tests it for emptiness and never
  echoes it; the workflow has `permissions: contents: read` and `pull-requests: read` and no
  `pull_request_target`; the factory code never reads a secret value (the API lists names only).
  Third-party action pinned to a major, as the other kit workflows do.
- The suite never reaches the network (`conftest.no_real_gh`); the guard test runs bash locally.
- ASCII-only doctor output; LF newlines in all new files; passes on Windows and Linux.
- Generic: no project name, owner, organisation or tracker host in kit, docs or policies (`factory lint`).

## Assumptions

- Python projects can run `uv run --with pytest-cov python -m pytest --cov --cov-report=xml:coverage.xml`
  (the python kit CI already uses uv); node projects' test script accepts `--coverage` (jest, vitest) and
  writes `coverage/lcov.info`; the step is the line a project adapts, as in the existing `ci.yml`
  templates.
- `SonarSource/sonarqube-scan-action` latest release is v8.3.0 (checked 2026-10-05 with `gh release
  list`); `@v8` tracks it. The scan action reads `sonar-project.properties` from the checkout root and
  defaults to SonarCloud when no host is given.
- Reading the repository secret list through `gh api repos/{o}/{r}/actions/secrets` is the same read
  as `gh secret list` (same endpoint); it goes through `harden.gh_api` so tests stub it and the factory
  keeps one GitHub access point (Treaty 3.8).
- The factory repo adopts its own kit, so `factory sync` lays the two files into it too (python stack);
  with no secret the workflow skips, so the repo's CI is unaffected until the owner configures it.
- A placeholder or not-yet-set-up Sonar project is a notice, not a warning, so that a fresh adopt keeps a
  clean doctor (as for the missing GitHub remote in FACT-33).

## Risks and dependencies

- Risk **medium**: it adds a workflow that runs third-party code in CI and handles a token, but it is
  inert without the secret, creates no write permissions, and is a create-mode file the project can
  delete. Policy asks a human to review CI/CD and third-party-service additions: the PR says so.
- Depends on the owner for the organisation key, the project import and the secret (AC8, AC9).
- SonarCloud may rename or change its free-plan terms; the how-to names the owner-side steps in
  neutral wording.
- The scan duplicates the test run (coverage) next to `ci.yml`; accepted for now (rejected alternative
  in the plan: sharing coverage between workflows).

## Open questions

None open. Resolved with the owner on the ticket: SonarCloud only; organisation key and secret supplied
by the owner later; project key convention `<owner>_<repo>`.
