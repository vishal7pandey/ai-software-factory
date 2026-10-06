# FACT-35 — SonarCloud scan in the kit

Status: spec-approved · Risk: medium · Jira: FACT-35
Created: 2026-10-05 · Slug: sonarcloud-scan-in-the-kit · Spec: spec.md

## Summary

Add four kit templates (a `sonar.yml` workflow and a `sonar-project.properties` for each of python and
node), register them as create-mode manifest entries, teach `adopt` to fill the project key from the
origin remote and the default branch into them, and add a `check_sonar` to `checks.py` that `doctor`
calls. Write `docs/sonarcloud.md` and the doc pointers. The guard logic lives inline in the workflow and
is tested by extracting it from the YAML and running it with bash.

**Size:** M (about one day: four templates, ~80 lines of code, ~40 tests, docs).

## Current state

* `kit/manifest.yaml` `files:` entries carry `src`, `dest`, `mode`, optional `stack` (name or list);
  `installer.collect_items` filters by stack and reads each `src`; `_plan_item` implements the modes:
  `create` writes only when the destination is absent and records nothing in `factory.yaml › managed`;
  `sync --check` (`sync_check`) ignores create-mode items.
* `adopt` calls `_install(..., inspection=...)`; only for `.github/workflows/ci.yml` does it adapt new
  content (`adopt_inspect.adapt_ci`: `branches: [main]` replaced by the default branch, optional local
  command checks). `sync` passes no inspection.
* `checks.check_project` and `checks.check_protections` are what `commands/doctor.py` prints;
  `check_protections` takes an injectable `gh` and defaults to `harden.gh_api`, which the autouse
  fixture `no_real_gh` makes inert (status 0). `harden.repo_slug(root)` gives (owner, repo) or raises
  `FactoryError`.
* `tests/test_integration.py::test_adopt_is_idempotent_and_doctor_is_clean` asserts no WARN/FAIL in
  `doctor` after `adopt` of a local-only project; `test_factory_repo_is_in_sync_with_its_kit` checks the
  factory repo against its own kit.
* Commands: `uv sync`; `uv run python -m pytest -q`; `uv run ruff check . && uv run ruff format --check .`;
  `uv run python -m swfactory.cli lint`; `... sync --check .`.
* `gh release list -R SonarSource/sonarqube-scan-action` (2026-10-05): latest v8.3.0.

## Approach

1. **Templates** under `kit/sonar/`: `python.yml`, `node.yml`, `python.properties`, `node.properties`.
   Four manifest entries (a workflow and a properties file per stack), `mode: create`, `stack: python` or `stack: node`. The two workflows
   share an identical guard step and scan step (a test asserts that); they differ in the toolchain and
   coverage steps. Duplicated text is the price of manifest entries staying plain files; the alternative
   (one template plus per-stack fragments) needs a new rendering mechanism for four lines of YAML.
2. **Guard** is an inline `run:` step with `id: guard`, receiving `SONAR_TOKEN` via `env`. It skips (exit
   0, `::notice`, `enabled=false` in `$GITHUB_OUTPUT`) when the token is empty, the properties file is
   missing, or a non-comment line contains `REPLACE_ME`; otherwise `enabled=true`. All later steps carry
   `if: steps.guard.outputs.enabled == 'true'`. The job-level `if` drops fork PRs before any step runs.
3. **Placeholder** marker `REPLACE_ME` shared by the templates, the guard and `checks.SONAR_PLACEHOLDER`;
   a test asserts the templates contain it, so the three cannot drift apart.
4. **Rendering at adopt**: properties templates contain `{{project_key}}`. `installer._render_create`
   (used in `_install` for `create`-mode items only, so managed skills and policies are never touched)
   replaces it with `<owner>_<repo>` from `harden.repo_slug` (lazy import: harden imports installer), or
   `REPLACE_ME_OWNER_REPO` when there is no GitHub remote. `adopt_inspect.point_at_branch` applies the
   default branch to a new `sonar.yml` (only when `inspection` is given, i.e. adopt).
5. **Doctor**: `checks.check_sonar(root, gh=None)` returns `Finding`s; `commands/doctor.py` appends them
   after `check_protections` in both branches. Secret names come from `GET
   repos/{o}/{r}/actions/secrets?per_page=100` through `gh` (default `harden.gh_api`); only `name` fields
   are read. Levels: see spec AC5/AC6 (OK when nothing is wrong or setup has not started, WARN for an
   inconsistent or unknown state, never FAIL).
6. **Docs**: `docs/sonarcloud.md`; Treaty 3.1 layout and CLI table, a short 3.9 on Sonar; README quick
   start line; `policies/security.md` one line; `factory sync .` refreshes `.factory/policies/` and
   lays the files into this repo.

**Alternatives rejected**
- A per-project `sonar-project.properties` written by the agent from a skill: not deterministic, and the
  kit's create-mode mechanism is exactly for this.
- Extra manifest field `render: true`/a templating engine: one token does not justify it (Boring).
- `gh secret list` as a subprocess in `checks.py`: a second GitHub access point that tests would have
  to stub separately; the same read is available through `gh_api` (spec assumption).
- Sharing coverage from `ci.yml` via artifacts, so the scan does not re-run the tests: cross-workflow
  artifact download needs `actions: read`, run ids and event handling; revisit when a real project
  complains about CI minutes.
- Making the quality gate fail the job by default (`sonar.qualitygate.wait=true`): that is the R4 human
  decision per project; documented as a one-line opt-in.
- A scheduled scan and a `docs`/`other` template: no project needs them yet.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Write the tests first (expected to fail) | `tests/test_sonar.py` | AC1-AC7 | `uv run python -m pytest tests/test_sonar.py -q` fails for the right reasons |
| T2 | Kit templates and manifest entries | `kit/sonar/*`, `kit/manifest.yaml` | AC1, AC2, AC3, AC4 | template, manifest and guard tests green; `factory lint` OK |
| T3 | Render project key and default branch at adopt | `src/swfactory/installer.py`, `src/swfactory/adopt_inspect.py` | AC1, AC2 | adopt tests green; second adopt/sync is "up to date" |
| T4 | `check_sonar` and doctor wiring | `src/swfactory/checks.py`, `src/swfactory/commands/doctor.py` | AC5, AC6 | doctor tests green; `test_adopt_is_idempotent_and_doctor_is_clean` still green |
| T5 | Docs and pointer | `docs/sonarcloud.md`, `docs/ARCHITECTURE.md`, `README.md`, `policies/security.md` | AC7 | docs tests green; `factory lint` OK |
| T6 | Sync the kit into this repo | `.factory/policies/security.md`, `.github/workflows/sonar.yml`, `sonar-project.properties` | AC2, AC7 | `factory sync .` then `factory sync --check .` in sync; `test_factory_repo_is_in_sync_with_its_kit` green |
| T7 | Gates, audit, PR | `test-plan.md`, `item.yaml` | all | ruff, full suite, `factory lint`, `verify.py`; mutation audit recorded; CI green on the PR (the new workflow runs its guard) |

## Data, API and migration impact

New files in adopted python/node projects (create mode, so existing projects get them on their next
`factory sync` only if they lack them; nothing existing is overwritten). New doctor lines (all
non-failing). New read-only GitHub call: `GET repos/{o}/{r}/actions/secrets`. No CLI flag, no
`factory.yaml` field, no schema change. Backwards compatible; reversible by deleting the two files.

## Security and failure modes

* The token is only ever an environment variable of the guard and scan steps; the guard never prints it;
  the factory never reads a secret value (the endpoint returns names and timestamps only, and the code
  reads `name` only). Test with a marker value in the stub response and in the guard's env.
* Third-party action `SonarSource/sonarqube-scan-action@v8` (major pin, like the other kit actions);
  `permissions: contents: read, pull-requests: read`; no `pull_request_target`; fork PRs excluded at job
  level.
* Failure modes: secret absent, properties placeholder, missing file, gh unusable, no admin, more than
  100 secrets, org-level secret: each has a stated behaviour in the spec and a test, except the
  org-level secret, which is documented.
* Mandatory human security review applies (CI/CD plus a new third-party service): the PR says so.

## Rollout and rollback

Merge the PR; the factory repo's own `sonar.yml` runs the guard on that PR's CI (proves AC4 in a real
runner: skip with a notice, job green). The owner then does the SonarCloud-side steps from
`docs/sonarcloud.md` per repo; `factory doctor` shows what remains. Rollback: revert the PR; adopted
projects keep their copies, which are inert without the secret and can be deleted.

## Risks and open points

* The `v8` major could change input names: the scan step uses no inputs except the `SONAR_TOKEN` env and
  `GITHUB_TOKEN`; signal: the first real analysis (AC8) fails, fix in the template.
* `uv run --with pytest-cov` might not be allowed by a project's index config: the step is documented as
  the line to adapt.
* A stub-only doctor test cannot prove the live API shape: `GET .../actions/secrets` is checked by hand
  once on this repo with the real `gh` (test-plan Manual checks) before merge.
* Windows machines with only WSL `bash` cannot run the guard tests: they skip with a reason; CI on Linux
  always runs them.
