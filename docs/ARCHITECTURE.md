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
├── policies/        security / git / testing / production / autonomy / findings  (copied into projects)
├── kit/             files laid into adopted projects; kit/manifest.yaml is the index
│   ├── ci/          stack CI workflows            ├── workflows/  factory-verify.yml
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
├── .github/workflows/factory-verify.yml (managed)
├── .factory/
│   ├── factory.yaml               project config + ledger of managed-file hashes
│   ├── verify.py                  standalone copy of src/swfactory/verify.py (managed)
│   ├── policies/*.md              (managed)
│   └── templates/work/*.md        work-item doc templates; skills read them here (managed)
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

### 3.4 Skill format

`skills/<name>/SKILL.md`, name == directory, all prefixed `factory-`. YAML frontmatter:
`name`, `description` (≤ 1024 chars; says **when to use it**, starts "Use when…"). Body ≤ 150 lines
with these H2 sections, in order: `## When to use`, `## Inputs`, `## Steps`, `## Output`,
`## Definition of done`, `## Never`. Optional `references/` dir for long material.
Rules: reference work-item paths and statuses exactly as in 3.2; never tell an agent to run
`approve`; mention the CLI only as optional ("or edit `item.yaml` by hand"). `factory lint` enforces
the mechanical parts, and that `factory-implement` keeps carrying the file-editing rule (editor tools,
never inline scripts) and the explicit-staging rule (never `git add -A`).

V1 skills: `factory-workflow` (router), `factory-spec`, `factory-plan`, `factory-implement`,
`factory-test`, `factory-review`, `factory-diagnose`, `factory-release`, and `factory-findings` (scanner
alerts to tracked, fixed, scanner-confirmed closed Jira Bugs; policy `findings.md`).

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
error (`FactoryError`, message to stderr), 2 usage. No command may require network except where noted.

| command | owner module | purpose |
|---|---|---|
| `adopt <path> [--stack] [--tracker] [--jira-key] [--autonomy] [--dry-run] [--no-check]` | `commands/install.py` | lay the kit into a project; register it. Project-aware: prints findings (default branch, existing CI triggers, commands section), inserts a commands TODO above a new AGENTS.md block, points a new CI at the default branch and drops CI steps that fail locally (`--no-check` skips running them; `--dry-run` never does). `adopt_inspect.py` |
| `sync [path] [--force] [--dry-run] [--check]` | `commands/install.py` | refresh managed files; report conflicts/drift. `--check` writes nothing and exits 1 if a managed file is stale or missing |
| `new <name> --stack python [--dir]` | `commands/install.py` | copy `templates/<stack>`, `git init`, adopt |
| `project list\|add\|remove` | `commands/install.py` | registry |
| `doctor [path]` | `commands/doctor.py` | tools present (git, gh, uv, node, docker, claude); gh auth; for a project: drift/missing kit files |
| `lint` | `commands/lint.py` | validate skills + kit manifest in the factory repo |
| `feature start <title> [--jira KEY] [--risk] [--no-branch] [--run AGENT]` | `commands/work.py` | scaffold work item + branch + handoff prompt |
| `bug start <title> …` | `commands/work.py` | same, bug templates |
| `status [--all]` | `commands/work.py` | table of work items: id, type, status, branch, next step |
| `approve <id> spec\|plan [--yes] [--delegated WHO]` | `commands/work.py` | human gate ledger; `--delegated` records an owner-delegated approval (3.2) |
| `advance <id> <status>` | `commands/work.py` | forward-only status moves |
| `next <id> [--run claude\|copilot]` | `commands/work.py` | print (or launch) the prompt for the next step given status |
| `verify [...]` | `commands/work.py` → `swfactory/verify.py` | the CI gate (3.3) |

Shared helpers live in `swfactory/common.py`. Command modules expose `register(subparsers)`.

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
