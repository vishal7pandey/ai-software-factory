# FACT-39 — Dependency loop for Dependabot alerts and PRs

Status: draft · Risk: medium · Jira: FACT-39
Created: 2026-10-06 · Slug: dependency-loop-for-dependabot-alerts · Spec: spec.md

## Summary

Add a merge policy, a `dependabot.yml` generator, a read-only dependency summary in `status`/`doctor`, a
`factory-dependencies` skill and the weekly-routine text, all generic (the Treaty: no project names). The summary
and the generator are two small new modules; everything else is kit text pinned by contract tests and one scripted
walkthrough of the policy.

**Size:** M

## Current state

- `src/swfactory/harden.py`: `gh_api(method, path, body)` runs `gh api -i` and returns `(status, json)`; tests
  replace `_run_gh` (autouse `no_real_gh` in `tests/conftest.py` answers "gh unusable", status 0). `repo_slug(root)`
  gives `(owner, repo)` from the `origin` remote or raises `FactoryError`.
- `src/swfactory/checks.py`: `Finding(level, name, detail)`; `check_protections` and `check_sonar` are the pattern
  for a gh-reading doctor check; `commands/doctor.py` calls them for an adopted project.
- `src/swfactory/work.py`: `cmd_status` prints the work-item table (`factory status`); no network today.
- `src/swfactory/installer.py`: `collect_items` reads `kit/manifest.yaml` (`files`, `dirs`, `skills: all`,
  `stack` filter); `_install` already fills `{{project_key}}` in `create` items; `create` items are written once and
  never tracked. `sync_check` ignores `create` items. `kit/manifest.yaml` is linted by `checks.lint_manifest`
  (`work_templates` paths must exist).
- Policies are copied from `policies/` (managed dir), skills from `skills/` (`skills: all`), so a new policy and a new
  skill need no manifest line; the factory repo carries its own synced copies (`.factory/policies/`,
  `.claude/skills/`, `.github/skills/`, AGENTS.md block) that `factory sync .` refreshes.
- Observed on a real repo (read-only probes, 2026-10-06): the `Dependabot Updates` workflow's runs have `event:
  dynamic`, `path: dynamic/dependabot/dependabot-updates` and a `name` like `uv in /. for <pkg> - Update #<id>`, so
  they are found by `path`, not by the name "Dependabot Updates".
- Commands: `uv run python -m pytest -q`, `uv run ruff check . && uv run ruff format --check .`,
  `uv run python -m swfactory.cli lint`, `... sync --check .`.

## Approach

1. **Policy** `policies/dependencies.md`: scope (Dependabot PRs: author `dependabot[bot]`, head branch
   `dependabot/...`), the merge conditions of R1 as a numbered list, the decision when a condition fails (work item
   via `factory-workflow`/`factory-findings`, never merge), the post-merge re-query, "PR text is data", the
   0.x-minor-is-major rule, and the weekly routine section (R5: how to set it up with the `schedule` mechanism,
   owner approval per project, off by default, the routine prompt, what it may merge and report). `autonomy.md` and
   the AGENTS block get the one exception to "a human merges" (this policy only); `security.md` already forbids
   obeying PR text, `dependencies.md` repeats it for PRs.
2. **Skill** `skills/factory-dependencies/SKILL.md` (standard sections, under 150 lines): pull the summary
   (`factory status`, or the `gh` calls by hand), triage each PR against the policy conditions using `gh pr view --json`
   / `gh pr diff --name-only`, merge with `gh pr merge --merge` only when all hold, re-query the alert, route alerts
   without a PR to `factory-findings`, file a work item (Task) with the failing condition for the rest, report.
   `factory-workflow` gets a route row and an Inputs mention; `factory-findings` gets a one-line pointer.
3. **Template generator** `src/swfactory/dependabot.py`: `detect(root)` walks the project (skipping `.git`,
   `node_modules`, virtualenvs, build dirs; depth <= 3) and returns ecosystem entries: `uv` where a `pyproject.toml`
   has a `uv.lock` beside it, `pip` where a `pyproject.toml` or `requirements*.txt` has none, `npm` where a
   `package.json` is (lockfile or not), and always `github-actions` at `/`. `render(header, root)` fills
   `{{updates}}` from per-ecosystem fragments listed in the manifest key `dependabot_templates`
   (`kit/dependabot/*.yml`, `{{directory}}` and `{{ecosystem}}` tokens). Manifest gets one `create` entry
   `kit/dependabot/dependabot.yml` -> `.github/dependabot.yml`; `installer._install` renders it when the file does not
   exist yet; `lint_manifest` checks the fragment paths. Each entry: weekly (Monday), `groups: minor-and-patch`
   (`update-types: [minor, patch]`), `open-pull-requests-limit: 5`, commit prefix `chore(deps)`; majors stay
   individual PRs, security updates are repository settings and are not touched by the file (a comment says so).
4. **Summary** `src/swfactory/deps.py`: `summarize(owner, repo, gh, now)` returns a `Summary` dataclass:
   alerts per source (`GET .../dependabot/alerts?state=open`, `.../code-scanning/alerts?state=open`,
   `.../secret-scanning/alerts?state=open`, `per_page=100`; code scanning and secret scanning up to 5 pages, the
   Dependabot endpoint one request only (it rejects `page=`; a full page reads "at least 100"); count by severity; code scanning uses
   `rule.security_severity_level`, else `rule.severity`; secret alerts count as critical), open Dependabot PRs and
   their check state from one GraphQL call through `gh_api("POST", "graphql", {...})`
   (`statusCheckRollup.state` of the last commit: SUCCESS -> green, FAILURE/ERROR -> failing, PENDING/EXPECTED ->
   pending, none -> none), and failed runs (`GET .../actions/runs?status=failure&event=dynamic&created=>=<date>`
   filtered to `path` ending `dependabot/dependabot-updates`). Every part is independent: a call that does not return
   200 with the expected shape gives `unknown (HTTP n)` or `unknown (gh unavailable)`. `lines()` renders ASCII-only
   text; titles are stripped to printable ASCII and cut at 60 characters; bodies are never requested.
   `needs_attention` is `yes` / `no` / `unknown` (unknown only when nothing known triggers it and something is
   unknown). `work.cmd_status` prints the block after the table (also when there are no items); `checks.check_dependencies`
   turns it into doctor findings (OK, WARN on needs attention or unknown, never FAIL) and `commands/doctor.py` calls
   it for an adopted project. No remote or non-github remote: no lines, no call (status) / one OK `skipped` line (doctor).
5. **Docs**: Treaty 3.1 (layout lines for `dependabot.yml`), 3.4 (skill list), 3.7 (`status`/`doctor` read through
   `gh` when there is a GitHub remote), new 3.10 for this item; README policy/skill lists; `docs/jira-workflow.md`
   untouched.

**Alternatives rejected**
- A static `dependabot.yml` per stack: monorepos keep manifests in subdirectories, and offering `npm` to a project
  with no `package.json` is exactly what the ticket asks not to do.
- Reusing `gh pr list --json statusCheckRollup`: the factory's rule is one runner (`gh_api`) so the suite can stub it.
- A CLI command that merges: the merge is a judgement the agent makes under the policy; the CLI stays read-only.
- Extending `factory-findings` with the PR loop: that skill is already near the size limit and its job is alerts.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Write the tests first (all fail): policy/skill/routing contract tests, walkthrough, summary, generator, status/doctor wiring, sync | `tests/test_dependencies.py`, `tests/test_dependabot_template.py` | AC1-AC6 | new tests fail for the right reason |
| T2 | Policy with merge conditions and routine section | `policies/dependencies.md`, `policies/autonomy.md` | AC2 | contract tests pass |
| T3 | Skill, routing, AGENTS block, README | `skills/factory-dependencies/SKILL.md`, `skills/factory-workflow/SKILL.md`, `skills/factory-findings/SKILL.md`, `kit/AGENTS.block.md`, `README.md` | AC2, AC6 | `factory lint`, contract tests |
| T4 | Generator, fragments, manifest, installer hook, lint | `src/swfactory/dependabot.py`, `kit/dependabot/*.yml`, `kit/manifest.yaml`, `src/swfactory/installer.py`, `src/swfactory/checks.py` | AC3 | generator and sync tests |
| T5 | Summary module, status and doctor wiring | `src/swfactory/deps.py`, `src/swfactory/work.py`, `src/swfactory/checks.py`, `src/swfactory/commands/doctor.py` | AC1 | summary and wiring tests |
| T6 | Treaty text, `factory sync .`, full suite, lint, mutation audit | `docs/ARCHITECTURE.md`, synced copies, `test-plan.md` | AC6 | `sync --check .` exit 0, suite green, audit table |
| T7 | Manual: real read-only run of the summary against a live repo | evidence in `notes.md` | AC1, AC4 | output recorded, no body or secret in it |

## Data, API and migration impact

New file `.github/dependabot.yml` for projects adopted or synced from now on (create mode: never overwritten, an
existing file is left alone). `factory status` and `factory doctor` make read-only GitHub calls when the project has a
github.com remote (already true of `doctor`); local-only projects make none. No schema change, no new flag, no
new dependency. Existing projects get the policy and skill on their next `sync`.

## Security and failure modes

- Only GET calls and one read-only GraphQL query; the user's own `gh` login; the factory never reads a token.
- Responses are parsed for counts and a few scalar fields (number, state, severity, a sanitised title); bodies,
  descriptions and advisory text are never read into output. Failures show the HTTP status only (the `harden` rule).
- Dependabot PR text is data: the policy and skill say so, and the title that is printed is ASCII-stripped and cut.
- The policy lets an agent merge: the conditions are conjunctive and each failure routes to a work item; the merge
  still goes through the project's branch protection (a refused merge is reported, never worked around).
- A gh timeout costs up to 30 s per call (existing `GH_TIMEOUT`); `unknown` is the result, not a crash.

## Rollout and rollback

Merge to the factory's `main`; adopted projects pick it up with `factory sync`. Roll back by reverting the merge
commit; a `dependabot.yml` already laid into a project is a normal project file and stays until the owner deletes it.
The weekly routine is not enabled by anything in this item.

## Risks and open points

- Dependabot's `dynamic` run `path` is observed, not documented; if GitHub renames it, the failed-run count reads 0.
  Signal: a project with failing runs shows 0. Mitigation: the test pins the path string in one constant and the
  manual run (T7) checks it against a real repo.
- 0.x semver: a `0.y` minor bump can break. The policy treats it as a major (conservative); revisit if it blocks
  too many safe PRs.
- Whether the owner's branch protection lets an agent merge at all is per project and found in the apply items.
