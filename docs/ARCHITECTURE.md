# Architecture — and the Treaty

This document is the contract every part of the factory is built against. If code, a skill, or a
template disagrees with it, the disagreement is a bug — fix the artifact, or change this file
deliberately in the same commit.

## 1. What the factory is

> A repository of **engineering method** (skills, policies, templates) plus a **thin CLI** that lays
> that method into real projects and keeps work items honest. Everything else — Git, Jira, CI, cloud,
> the AI coding agent itself — is somebody else's job.

### Principles

1. **Don't own what a platform already provides.** Git → GitHub. Tracking → Jira. CI → Actions.
   Coding agent → Claude Code / Copilot / whatever is best this year. We write glue and method only.
2. **Kit-in-repo.** After `factory adopt`, a project contains everything it needs: `AGENTS.md`,
   skills, policies, CI workflow, a standalone `verify.py`. It must keep working if the factory repo
   vanishes, and it must work inside an environment where we cannot install anything but git + a
   coding agent. *A skill must be executable by an agent with only git and file access; the CLI is a
   convenience, never a requirement.*
3. **Skills, not agent personas.** One strong engineer-agent, many skills. Independent reviewer
   roles are a later evolution (see ROADMAP), not a V1 requirement.
4. **Work is a graph, not a pipeline.** `factory-workflow` is a router: it picks the entry point
   (feature, bug, …) and the next skill from the current state. No hard-coded "bug workflow".
5. **Evidence lives in git.** Every work item leaves spec, plan, test plan and approvals in
   `docs/work/<id>-<slug>/`, committed with the code. "Why does this exist?" is answerable from the repo.
6. **Humans gate what is irreversible or costly:** approving a spec, approving a plan, merging, and
   production. Agents do everything between gates.
7. **Boring.** Python stdlib + PyYAML. Markdown. YAML. No daemon, no database, no framework.

### Honesty clause on gates

`factory approve` is a **ledger, not a lock**. It records who approved what and when; an agent with
shell access could also type it. The lock is GitHub: branch protection + required review on the PR,
with `docs/work/**` covered by CODEOWNERS, plus the `verify` check in CI. Policy
(`policies/autonomy.md`) forbids agents from running `approve` except under an explicit, recorded owner
delegation, which is written in the distinguishable `--delegated` form; CI makes violations visible.

## 2. Repository anatomy

```
ai-software-factory/
├── AGENTS.md  CLAUDE.md          how to work ON the factory
├── README.md
├── docs/            ARCHITECTURE.md (this), ROADMAP.md, decisions/ (ADRs), jira-workflow.md
├── skills/          the method — one dir per skill, SKILL.md inside   (source of truth)
├── policies/        security / git / testing / production / autonomy / findings / dependencies  (copied into projects)
├── kit/             files laid into adopted projects; kit/manifest.yaml is the index
│   ├── ci/          stack CI workflows            ├── workflows/  factory-verify.yml
│   ├── sonar/       SonarCloud workflow + props   ├── dependabot/ dependabot.yml header + per-ecosystem entries
│   └── work/        work-item doc templates       └── *.md        AGENTS block, PR template, …
├── templates/       stack templates for `factory new`   (V1: python)
├── src/swfactory/   the CLI.  (package is NOT called `factory` — collides with factory_boy)
└── tests/
```

## 3. The Treaty

### 3.1 Adopted-project layout (what `adopt` produces)

```
<project>/
├── AGENTS.md                      managed block between <!-- factory:begin --> / <!-- factory:end -->
├── CLAUDE.md                      "@AGENTS.md" (created only if absent)
├── .claude/skills/factory-*/      copies of skills/   ─┐ targets configurable in factory.yaml
├── .github/skills/factory-*/      copies of skills/   ─┘
├── .github/copilot-instructions.md      (create-if-absent)
├── .github/pull_request_template.md     (create-if-absent)
├── .github/workflows/ci.yml             (create-if-absent, stack-specific)
├── .github/workflows/sonar.yml          (create-if-absent, python and node only, 3.9)
├── sonar-project.properties             (create-if-absent, python and node only, 3.9)
├── .github/dependabot.yml               (create-if-absent, only the ecosystems the project uses, 3.10)
├── .github/workflows/factory-verify.yml (managed)
├── .factory/
│   ├── factory.yaml               project config + ledger of managed-file hashes
│   ├── verify.py                  standalone copy of src/swfactory/verify.py (managed)
│   ├── policies/*.md              (managed)
│   └── templates/work/*.md        work-item doc templates; skills read them here (managed)
├── docs/PROJECT.md                (create-if-absent) the project charter, a template until written (3.12)
├── docs/decisions/
│   ├── TEMPLATE.md                (create-if-absent) example decision record (3.11)
│   └── D-<n>-<slug>.md            decision records, written by agents, answered by the owner
└── docs/work/
    ├── README.md                  (create-if-absent) explains the evidence convention
    └── <id>-<slug>/               one dir per work item (see 3.2)
```

**File modes** (declared per entry in `kit/manifest.yaml`):

| mode      | behaviour |
|-----------|-----------|
| `create`  | written once if the destination does not exist; never touched again; not tracked |
| `managed` | owned by the factory; hash recorded in `factory.yaml › managed`; `sync` overwrites only if the on-disk hash still equals the recorded hash (file unmodified), otherwise reports a **conflict** and leaves it (unless `--force`) |
| `block`   | text between factory markers inside a user-owned file; inserted if missing, replaced on sync; everything outside markers is never touched |

Hashes are of the file content with `\r\n` normalised to `\n` (Windows!). All operations are
idempotent: running `adopt` twice yields no diff. `--dry-run` prints the plan and writes nothing.

**Containment (FACT-43).** `adopt`, `sync` and `new` write only inside the project root. Every
destination (a manifest `dest`, a skill target from `factory.yaml`, a template path) is resolved
with `os.path.realpath` and must lie strictly under the realpath of the root; otherwise the command
fails with "outside the project" before the first file is written (a `..`, an absolute path or a
symlink that leaves the project is rejected). The registry file is written only if it resolves
inside its own directory.

### 3.2 Work item

Directory `docs/work/<ID>-<slug>/`:

| file           | author | notes |
|----------------|--------|-------|
| `item.yaml`    | CLI (or agent by hand) | machine state — schema below |
| `spec.md`      | agent, human-approved | feature: problem, users, requirements, **acceptance criteria**; bug: repro, expected, actual, root cause, regression criterion. Template: `kit/work/spec.feature.md` / `spec.bug.md` |
| `plan.md`      | agent, human-approved | approach, files/components touched, task list, risks, rollout. `kit/work/plan.md` |
| `test-plan.md` | agent | one row per acceptance criterion → test(s) that prove it. `kit/work/test-plan.md` |
| `notes.md`     | anyone | optional scratch/decisions log |

`item.yaml`:

```yaml
id: F-001                # Jira key when given (PF-12), else F-### (feature) / B-### (bug), zero-padded
type: feature            # feature | bug
title: Add Google login
slug: add-google-login
status: draft
risk: medium             # low | medium | high
jira: null               # Jira key or null
branch: feature/f-001-add-google-login     # feature/… for features, fix/… for bugs; id lower-cased
created: 2026-10-04
approvals:               # key absent until approved
  spec: {by: "Jane Doe", at: "2026-10-04"}
  plan: {by: "Jane Doe (delegated to agent)", at: "2026-10-05", delegated: true}   # delegated form, below
pr: null                 # PR URL once opened
```

**Status order** (strictly forward; `advance` refuses to go backwards or skip):

`draft → spec-approved → plan-approved → implementing → in-review → merged → released → done`

* `draft → spec-approved`: human, `approve spec`. Blocked while `spec.md` is missing/empty or contains `[NEEDS CLARIFICATION`.
* `spec-approved → plan-approved`: human, `approve plan`. Same blockers on `plan.md`.
* everything after: `advance <id> <status>` (agent or human). `implementing` requires `test-plan.md` to exist.
* **Who moves what.** `implementing` is set by the agent (`advance` or by hand) once `test-plan.md`
  is written. With the plan approval waived (autonomy rule below) the agent moves
  `spec-approved → plan-approved` itself via `advance`; otherwise only `approve plan` can.
* **Recording `merged` (FACT-20).** A status change after the merge would need another PR on a protected
  branch, so finished items would sit at `in-review` forever. Instead the **last commit on the PR branch** sets
  `status: merged` (`advance <id> merged`), after review is done and CI is green; the merge is the next event. If the PR is
  closed unmerged, revert that commit. In a project with no environment configured (`factory.yaml › environments` all
  null or absent) `merged` is the end of the line: `status` omits such items by default, lists them with `--all` as
  complete, and `next` says there is nothing to do. With an environment configured, `merged` routes to `factory-release`,
  and `released`/`done` are recorded after the release by a docs-only PR (exempt from rule 3's status check).
* **Amending after approval (graph rule).** If new information changes an approved `spec.md` or
  `plan.md`, the agent amends it, records why in `notes.md`, and asks the human to re-run
  `approve <id> spec|plan`. Re-approval is allowed at any status up to `in-review`; it refreshes
  `approvals.<kind>` (new `by`/`at`) and never moves status backwards.
* **Delegated approval.** When the owner has explicitly delegated a gate to agents (a recorded instruction
  naming the gate and the scope; never production), the agent records it with
  `approve <id> spec|plan --delegated "<owner>"`: `by: "<owner> (delegated to agent)"`, `delegated: true`.
  `verify` accepts that form and the same wording written by hand, and rejects a non-boolean `delegated` or
  `delegated: true` without the suffix; `status` marks such items `(delegated)`. Rules: `policies/autonomy.md`.
* **Autonomy** (`factory.yaml › autonomy`): `supervised` (default) requires spec **and** plan approvals.
  `trusted` waives the plan approval for `risk: low` items only. Anything else is a config error.
  `verify` and `approve` both read this; the rule lives in one function (`required_approvals`).

### 3.3 `verify` rules (runs in CI; standalone: stdlib + PyYAML)

`python .factory/verify.py [--root .] [--branch <name>] [--changed-files-from <file>]`. Exit 0/1.

1. Every `docs/work/*/item.yaml` parses and satisfies the schema (id matches dir prefix, enums valid).
2. status ≥ `spec-approved` ⇒ `approvals.spec` present; ≥ `plan-approved` ⇒ `approvals.plan` present
   (unless waived by autonomy rule); ≥ `implementing` ⇒ `spec.md`, `plan.md`, `test-plan.md` non-empty and free of the
   NEEDS CLARIFICATION marker (square-bracket form, see `factory-spec`).
3. If `--branch` matches `feature/<id>-…` or `fix/<id>-…` the item must exist and be ≥ `implementing`
   (code is not allowed to ride on an unapproved spec). Branches prefixed `chore/`, `docs/`, `deps/`,
   or `main` are exempt. With `--changed-files-from <file>` (one path per line; CI passes the PR's
   diff) a branch whose changed files are all under `docs/work/` is also exempt from the status check
   (the item must still exist); an unreadable list is ignored, so the strict rule applies.
4. Prints one line per violation: `FAIL <id>: <reason>`; final line `verify: OK` or `verify: N problem(s)`.
5. (FACT-5, warning only — never changes the exit code) status ≥ `in-review` and `test-plan.md`'s
   `## Audit` section still holds only the template placeholder ⇒ `WARN <id>: <reason>` printed before
   the FAIL lines; the final line becomes `verify: OK (N warning(s))` when there are no problems, so an
   empty audit does not pass silently even though it does not block the merge.
6. (FACT-46) Every `docs/decisions/D-<n>-<slug>.md` is a valid decision record (3.11): `validate_decision`, the same pure
   function the CLI uses, lives in this file. `FAIL D-<n>: <reason>` for an accepted or rejected record without `by`/`at`,
   an accepted `decision` that is not one of the options, a proposed record that already carries an answer, a delegated
   record without the delegated wording or a delegated `charter`/`dismissal`, a `dismissal` without alert URL and an
   allowed reason, an accepted `subject` without `subject_sha256`, a duplicate id. Other files in that folder (ADRs
   `001-*.md`, `TEMPLATE.md`) are not records.

### 3.4 Skill format

`skills/<name>/SKILL.md`, name == directory, all prefixed `factory-`. YAML frontmatter:
`name`, `description` (≤ 1024 chars; says **when to use it**, starts "Use when…"). Body ≤ 150 lines
with these H2 sections, in order: `## When to use`, `## Inputs`, `## Steps`, `## Output`,
`## Definition of done`, `## Never`. Optional `references/` dir for long material.
Rules: reference work-item paths and statuses exactly as in 3.2; never tell an agent to run
`approve` or `decide`; mention the CLI only as optional ("or edit `item.yaml` by hand"). `factory lint` enforces
the mechanical parts, and that `factory-implement` keeps carrying the file-editing rule (editor tools,
never inline scripts) and the explicit-staging rule (never `git add -A`).

V1 skills: `factory-workflow` (router), `factory-spec`, `factory-plan`, `factory-implement`,
`factory-test`, `factory-review`, `factory-diagnose`, `factory-release`, `factory-findings` (scanner
alerts to tracked, fixed, scanner-confirmed closed Jira Bugs; same-package and same-rule alerts share one
issue, closed only when every alert it carries is fixed; policy `findings.md`) and `factory-dependencies`
(Dependabot PRs: merged by the agent only when every condition of `dependencies.md` holds, else a work
item; routed from `factory-workflow`; 3.10).

### 3.5 `factory.yaml` (in the adopted project)

```yaml
factory_version: 0.1.0
stack: python                    # python | node | docs | other
autonomy: supervised             # supervised | trusted
tracker: {kind: jira, key: PROJ}   # kind: jira | github | none ; key only for jira
skill_targets: [.claude/skills, .github/skills]
environments: {dev: null, test: null, prod: null}   # URLs/notes; null = skip that stage
managed:                         # written by adopt/sync — path → sha256 of installed content
  .factory/verify.py: <sha256>
```

### 3.6 Registry

The registry is **instance data, so it lives outside the factory repo**: one user-level file,
`$FACTORY_REGISTRY` if set (a relative path resolves against the cwd), else `~/.factory/registry.yaml`.
Created on the first write (`adopt`, `project add`); a missing file is not an error (`project list`
says "no registry yet").

```yaml
projects: [{name, repo, stack, tracker: {kind, key}, autonomy, adopted}]
paths: {<name>: <absolute path of the local checkout>}
```

`docs/registry.example.yaml` shows the shape with placeholder values. If the registry cannot be
written, `adopt` still installs the kit and then exits 1 naming the path. `factory lint` fails when
a `registry/` directory appears in the repo or an Atlassian cloud site hostname appears under `docs/`
(except `docs/work/`), `kit/`, `skills/`, `policies/` or `templates/`: the factory stays generic.

### 3.7 CLI surface

Python ≥ 3.12, argparse, entry point `factory` (`uv run factory …`). Every command: exit 0 ok, 1 user
error (`FactoryError`, message to stderr), 2 usage. No command may require network except where noted:
`harden`, and the read-only reads of `doctor <project>`, `adopt` and `status` (3.10), call the GitHub API
through `gh` (3.8).

| command | owner module | purpose |
|---|---|---|
| `adopt <path> [--stack] [--tracker] [--jira-key] [--autonomy] [--dry-run] [--no-check]` | `commands/install.py` | lay the kit into a project; register it. Project-aware: prints findings (default branch, existing CI triggers, commands section), inserts a commands TODO above a new AGENTS.md block, points a new CI at the default branch and drops CI steps that fail locally (`--no-check` skips running them; `--dry-run` never does). Ends with the `harden` dry-run plan and the command to apply it (3.8). `adopt_inspect.py` |
| `sync [path] [--force] [--dry-run] [--check]` | `commands/install.py` | refresh managed files; report conflicts/drift. `--check` writes nothing and exits 1 if a managed file is stale or missing |
| `new <name> --stack python [--dir]` | `commands/install.py` | copy `templates/<stack>`, `git init`, adopt |
| `project list\|add\|remove` | `commands/install.py` | registry |
| `doctor [path]` | `commands/doctor.py` | tools present (git, gh, uv, node, docker, claude); gh auth; for a project: drift/missing kit files, the four repo protections (3.8) and the SonarCloud setup lines (3.9); exits 1 when a protection is `off` on a public repo (a Sonar line never fails) |
| `harden [path] [--dry-run]` | `commands/harden.py` → `swfactory/harden.py` | enable secret scanning + push protection, Dependabot alerts and security updates, CodeQL default setup on the project's GitHub repo (3.8) |
| `lint` | `commands/lint.py` | validate skills + kit manifest in the factory repo |
| `feature start <title> [--jira KEY] [--risk] [--no-branch] [--run AGENT]` | `commands/work.py` | scaffold work item + branch + handoff prompt; a feature in a charter maintenance mode prints a warning (3.12) |
| `bug start <title> …` | `commands/work.py` | same, bug templates |
| `status [--all]` | `commands/work.py` | table of work items: id, type, status, branch, next step; then the decisions waiting for the owner (3.11), then the charter progress (3.12), then, for a github.com project, the read-only dependency summary (3.10) |
| `approve <id> spec\|plan [--yes] [--delegated WHO]` | `commands/work.py` | human gate ledger; `--delegated` records an owner-delegated approval (3.2) |
| `decide <id> --accept [--option N] \| --reject [--note T] [--yes] [--delegated WHO]` | `commands/decide.py` → `swfactory/decisions.py` | the owner's answer to a decision record (3.11): stamps status, decision, `by`, `at`; never run by an agent |
| `decision new <title> --type T [--jira KEY] [--alert URL --reason R] [--by NAME]` | `commands/decide.py` | scaffold a proposed, draft decision record from the kit template (next free `D-<n>`) |
| `inbox` | `commands/decide.py` | decisions waiting for the owner in every registered project with a local path; read-only |
| `advance <id> <status>` | `commands/work.py` | forward-only status moves |
| `next <id> [--run claude\|copilot]` | `commands/work.py` | print (or launch) the prompt for the next step given status |
| `verify [...]` | `commands/work.py` → `swfactory/verify.py` | the CI gate (3.3) |

Shared helpers live in `swfactory/common.py`. Command modules expose `register(subparsers)`.

### 3.8 Repository protections (`harden`, FACT-33)

A GitHub-hosted project should have four protections on: **secret scanning with push protection**,
**Dependabot alerts**, **Dependabot security updates** and **CodeQL default setup**. They are repository
settings, not files, so they cannot be laid in by `adopt` and nothing in git would show them going off.

* The repo is the project's `origin` remote (`github.com/<owner>/<repo>`); any other host is an error for
  `harden` and a skipped line for `doctor`.
* All GitHub access goes through one function, `swfactory.harden.gh_api(method, path, body)`, which runs
  `gh api -i` (the user's own `gh` login; the factory never reads a token) and returns the HTTP status and
  the parsed JSON. Tests replace it; the suite cannot reach the network.
* `harden` reads each state first (GET), then writes only what is not on, in this order:
  `PATCH repos/{o}/{r}` (`security_and_analysis`: `secret_scanning` and `secret_scanning_push_protection`
  `enabled`), `PUT .../vulnerability-alerts`, `PUT .../automated-security-fixes`,
  `PATCH .../code-scanning/default-setup` (`state: configured`, `query_suite: default`). `--dry-run` prints
  these calls and issues no write; re-running with everything on writes nothing.
* One protection failing does not stop the others. A failure is reported as `HTTP <status>` only, never the
  response body. On a private repo a 403/404/422 means the plan has no such feature and is reported
  `not available`, which is not a failure. Exit 1 when any protection failed.
* `doctor <project>` shows each protection as `ok`, `off`, `unknown` (gh unusable, no admin) or
  `not available`, and exits 1 when one is `off` on a **public** repo (a warning on a private one).
  A project without a github.com remote gets one `skipped` line.
* `adopt` ends by printing the dry-run plan and `factory harden <path>`; it never changes a setting itself.

### 3.9 SonarCloud scan (FACT-35)

Optional code-quality scan for python and node projects; the owner-side steps are in `docs/sonarcloud.md`.

* `kit/sonar/{python,node}.yml` become `.github/workflows/sonar.yml` and `kit/sonar/{python,node}.properties`
  become `sonar-project.properties`, all `create` mode (never touched by `sync`, not in `managed`). Stacks
  `docs` and `other` get neither.
* The only substitution the installer makes is `{{project_key}}` in a `create`-mode template: `<owner>_<repo>`
  from the GitHub `origin` remote, else the marked placeholder `REPLACE_ME_OWNER_REPO`. The organisation key
  is the marked placeholder `REPLACE_ME_SONAR_ORGANIZATION` (`installer.SONAR_PLACEHOLDER` is the marker).
  `adopt` also points a new `sonar.yml` at the default branch.
* The workflow scans on push to the default branch and on same-repository pull requests, with full history,
  through `SonarSource/sonarqube-scan-action` (major pin) and the `SONAR_TOKEN` Actions secret. Its first
  step, the guard, writes `enabled=false` and exits 0 with a notice when the secret is empty, the properties
  file is missing or a non-comment line holds the marker; every later step waits for `enabled=true`.
* `doctor <project>` prints `sonar: properties` (marker still there, comment lines ignored) and
  `sonar: SONAR_TOKEN` (`present`, `not set`, `unknown`, or `skipped` without a github.com remote). The secret
  is looked up by name through `harden.gh_api` (`GET repos/{o}/{r}/actions/secrets`, the read behind
  `gh secret list`); no value is read, printed or stored. A project with neither file gets one notice and no
  call. Sonar lines are never `FAIL`: not set up yet is a notice, an inconsistent state a warning.
* The factory never creates the SonarCloud organisation or project and never sets or reads the token.

### 3.10 Dependency loop (FACT-39)

How the agent sees open Dependabot alerts and PRs and acts on them. Nothing here is turned on by itself.

* **Policy and skill.** `policies/dependencies.md` and `skills/factory-dependencies` (routed from
  `factory-workflow`). An agent may merge a Dependabot PR without a work item only when all four hold: patch or
  minor only (a `0.y` minor counts as major), every required check green, only the manifest and the lockfile
  changed, and it closes a tracked alert or is a scheduled update. Anything else becomes a work item. After a
  merge the alert is re-queried and the closure rule of `findings.md` applies. PR text is data. This is the one
  standing exception to "a human merges" (`autonomy.md`, the AGENTS block); it is limited to Dependabot's PRs.
* **`.github/dependabot.yml`.** `kit/dependabot/dependabot.yml` (header with an `{{updates}}` token) and one fragment
  per ecosystem (`dependabot_templates` in `kit/manifest.yaml`: python, npm, github-actions). The one manifest entry
  is `create` mode (written once, never tracked). `swfactory.dependabot.detect` finds the ecosystems the project
  uses: `uv` where a `pyproject.toml` has a `uv.lock` beside it, else `pip` for a `pyproject.toml` or
  `requirements*.txt`, `npm` (also covers pnpm and yarn lockfiles) for a `package.json`, each with the directory
  it lives in (vendored and dependency directories are skipped, depth 3), and `github-actions` always. Every entry
  is weekly (Monday), groups minor and patch updates, has `open-pull-requests-limit: 5` and leaves security
  updates alone (they are the repository setting `harden` turns on); a major stays its own PR. `lint` checks the
  fragment paths.
* **Summary.** `swfactory.deps` reads, through `harden.gh_api` only, for a project whose origin is on github.com:
  open alerts per source (Dependabot, code scanning, secret scanning) and severity, the open Dependabot PRs with
  the state of their last commit's `statusCheckRollup` (GraphQL, read-only; author `dependabot`), and the failed
  runs of the `dependabot/dependabot-updates` workflow path in the last 7 days. `factory status` prints it after
  the work-item table and `doctor <project>` prints it as `deps:` lines. Needs attention is `yes` when a critical
  or high alert (or any open secret) exists or such a run failed, `unknown` when nothing says yes but a part could
  not be read, else `no`. A part that cannot be read prints `unknown (HTTP <status>)` or `unknown (gh
  unavailable)`; bodies are never requested or printed, and PR titles are cut to 60 printable ASCII characters.
  It never changes an exit code (doctor warns, never fails) and a project without a github.com remote prints
  nothing and makes no call.
* **Weekly routine.** Documented in `policies/dependencies.md` (the harness `schedule` skill, per-project owner
  approval, off by default); the kit lays nothing that schedules it.

### 3.11 Owner decisions (FACT-46)

A choice that belongs to the owner (a design direction, a scanner-finding dismissal, a project charter) is a file in
the project's own repo, not a chat message. No tracker, no network.

* **Record.** `docs/decisions/D-<n>-<slug>.md`: Markdown with YAML front matter `id` (`D-<n>`, equals the file name
  prefix), `type` (`dismissal` | `design` | `charter` | `other`), `title`, `status` (`proposed` | `accepted` |
  `rejected` | `superseded`), `jira` (a link, or null), `proposed_by`, `proposed_at`, `options` (a list of
  `{text, recommended}`; exactly one recommended while proposed), and the answer: `decision` (the chosen option's
  text), `by`, `at`, `delegated`, `note`; optional `subject` (a project file the decision covers) with
  `subject_sha256` stamped on accept; a `dismissal` also carries `alert` (URL) and `reason` (one of the three of
  `policies/findings.md`); `superseded_by` when superseded. The body is context, evidence, options with consequences,
  a recommendation. ADRs (`001-*.md`) and `TEMPLATE.md` in the same folder are not records.
* **One validator.** `validate_decision(meta, filename)` is a pure function in `verify.py` (standalone; the CLI imports
  it). `verify` rule 6 applies it to every record; `swfactory/decisions.py` reads records and answers them.
* **Answering.** `factory decide <id> --accept [--option N] | --reject [--note T] [--yes] [--delegated WHO]` is a ledger
  like `approve`: it refuses a record that is not `proposed`, is invalid, or still holds the unfilled line, a
  clarification marker, `REPLACE_ME` or `{{`; stamps `by` (git user name, or `WHO (delegated to agent)`), `at`,
  `decision` (the recommended option unless `--option`), and leaves the body alone. It asks for confirmation on a
  terminal and refuses without `--yes` on a non-terminal. It is never run by an agent on its own, and
  `--delegated` is refused for `charter` and `dismissal` records (never delegated); a `design` or `other` record may be
  delegated only by an explicit, recorded owner instruction (`policies/autonomy.md`, Owner decisions). Like `approve`
  it records, it does not lock: the lock is GitHub review (CODEOWNERS on `docs/decisions/`).
* **Proposing.** `factory decision new "<title>" --type T` scaffolds a proposed draft from `kit/decisions/TEMPLATE.md`
  (named by `templates.decision` in the manifest, checked by `lint`); the agent writes it and deletes the unfilled
  line. `docs/decisions/TEMPLATE.md` (create mode, never overwritten) is the same example laid into each project.
* **Visibility.** `status` prints a "waiting for the owner" block (id, type, age, title, recommended option; nothing
  when nothing waits); `doctor` gives one WARN per waiting or invalid record; `factory inbox` does the same across the
  registry's projects that have a local path, reading their `docs/decisions` only (read-only, deterministic order).
* **Findings.** A dismissal is a `dismissal` record; `factory-findings` applies it only when the record is `accepted`
  with `by` and `at`, and cites the id in Jira (`policies/findings.md`, Dismissal gate).

### 3.12 Project charter (FACT-47)

A project needs a written, owner-approved definition of done and a stop rule, or scope only grows.

* **File.** `docs/PROJECT.md` (kit `kit/charter/PROJECT.md`, `create` mode: a template with the unfilled marker and
  `REPLACE_ME` placeholders, never overwritten by `sync`, not tracked). Markdown with YAML front matter: `purpose`
  (two sentences), `mode` (`active` | `maintenance`), `decision` (the `D-<n>` of the approving record, or null),
  `done` (3 to 7 criteria `{id, text, check}`), `non_goals`, `parked` (`{item, jira}`), and a body with a
  `## Maintenance mode` section: after done only security and dependency updates, through the findings and
  dependency loops; any other change needs a charter amendment (a new charter decision).
* **Measurable.** `check` has exactly one of `work: <id>` (met when that work item is `merged` or later; no such item
  is `not met`), `file: <path>` (exists), `metric: {file, key, min|max|equals}` (the number at the dotted `key` of a
  YAML or JSON file; an unreadable file or key is `unknown`), `jira: <KEY>` (met when an injected lookup says `Done`;
  without one it is `unknown`: the factory has no Jira client). Paths resolve inside the project (`os.path.realpath`
  plus a `startswith` guard). `validate_charter(meta, body)` (pure, `swfactory/charter.py`) rejects fewer than 3 or
  more than 7 criteria, duplicate ids, a criterion without a valid `check`, vague phrases ("works well",
  "user-friendly", "robust", ...), fewer than three words, an empty purpose or `non_goals`, a bad mode, a missing
  maintenance section and a template.
* **Approval.** Only through a `charter` decision record (3.11) with `subject: docs/PROJECT.md` (`validate_decision`
  requires it). `decide --accept` refuses unless the file is a valid charter that names that record in `decision`,
  then stamps `subject_sha256`. The charter is **approved** when `decision` names an accepted `charter` record whose
  hash equals the current file (newlines normalised); an edit afterwards is `changed`; a missing, proposed, rejected,
  superseded or invalid record is `unapproved`. Charter decisions are never delegated and never run by an agent.
* **Visibility.** `doctor` gives one `charter` finding: OK when approved, else WARN `no approved charter: <why>` (never
  FAIL). `status` prints, for an approved `active` charter, each criterion as `met`, `not met` or `unknown` with its
  reference and the count, and when every one is met, "ready for maintenance mode": the owner sets `mode: maintenance`
  and proposes a new charter decision; for `maintenance` it prints the stop rule; an unapproved existing charter
  gets one line, and a project without the file prints nothing. `feature start` prints a warning in maintenance
  mode and carries on (not a block, so the owner can proceed deliberately); `bug start` does not warn.
* **Skills.** `factory-spec` checks proposed work against the charter (in scope, a done criterion, parked, or an
  amendment); `factory-workflow` and `policies/autonomy.md` say who may change it.

## 4. Golden path

```
factory feature start "Add Google login" --jira PF-12     → docs/work/PF-12-add-google-login/ + branch
  agent + factory-spec        → spec.md  (acceptance criteria; open questions flagged)
  human: factory approve PF-12 spec
  agent + factory-plan        → plan.md ;  human: approve plan
  agent + factory-test        → test-plan.md   (AC → tests)       factory advance PF-12 implementing
  agent + factory-implement   → code + tests, small commits, PR   factory advance PF-12 in-review
  agent + factory-review      → independent pass against spec; fixes loop
  last commit on the branch                                       factory advance PF-12 merged
  CI: project ci.yml + factory-verify.yml ;  human merges
  agent + factory-release     → deploy through environments, smoke, record, close Jira
```

Bugs enter at `factory-diagnose` (reproduce → root cause → `spec.md` with regression criterion) and
rejoin the same path at plan/implement. `factory-workflow` decides; the path is a default, not a rail.

## 5. Deliberately not here (yet)

Cloudflare/Supabase/Infisical infra repo, Jira REST client, dashboard, vector memory, custom agent
runtime, incident/refactor/security skills. Each is in `docs/ROADMAP.md` with the trigger that would
justify building it. Rule of thumb: **if no project has needed it yet, it does not exist.**
