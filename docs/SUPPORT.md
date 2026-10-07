# Supported today

What the factory supports, as of 2026-10-07 (FACT-48), and what proves it. The method (spec, plan, test plan,
review, release, findings, dependencies, decisions) is generic; the machinery around it is narrower. This page
exists so nobody believes more than is true. Principle: **only what a real project, a CI run or a test shows is
written as supported.** The ranked plan for lifting each gap, with the smallest next step and how it would be
proven, is the Confluence page "Factory generality: assumptions and roadmap" (space FACT); the Treaty
([ARCHITECTURE.md](ARCHITECTURE.md), section 3.13) links here.

**Status words.** `supported`: used on a real project, or on the factory itself, without a workaround that
is not written in the gaps. `partial`: part of it works or only tests show it. `not supported`: nothing in the
factory does it, or it is accepted but inert.

**Proven by.** A project and PR (ade is the repo `adep`; PR numbers are in that repo), a CI run, or **tests
only** (a unit or integration test on a temporary directory, no real project), or **nothing**. The factory has
been used by exactly three projects: itself, ade and chatpid. All one owner, all GitHub and Jira, ade and
chatpid are Python with a pnpm `frontend/` directory, all developed on Windows.

**The matrix is checked.** `factory lint` (and `tests/test_support.py`) fails when a stack exists in the
repository (a directory under `templates/`, a file stem under `kit/ci/` or `kit/sonar/`, a `stack:` value in
`kit/manifest.yaml`, a name in `STACKS`) without a `stack` row here, when a `stack` row claims support for a
stack that does not exist, when a Dependabot ecosystem template has no row, or when a row is incomplete. Add the
row in the same change as the stack. Row format: five cells, no `|` inside a cell.

## Stacks

A stack is what `adopt` writes the CI, SonarCloud and Dependabot files for. `adopt` detects `python`
(a `pyproject.toml`), `node` (a `package.json`) or `other`; `docs` only by `--stack docs`. A project of any
other kind is adopted as `other`: it gets the method, `verify`, decisions and the charter, and a placeholder CI.

| dimension | value | status | proven by | known gaps |
|---|---|---|---|---|
| stack | `python` | supported | ade (kit sync PR 22, SonarCloud PR 23, dependency loop PR 25), chatpid (PR 23, 24, 27), the factory itself; `factory new --stack python` ran once end to end in a scratch project (docs/e2e-001.md) | The CI template assumes uv, Python 3.12, ruff and pytest: ade pinned 3.11 and kept a hand-written CI, chatpid edited it (`uv lock --check`, `--all-groups`). A pip, poetry or conda project gets steps that fail (`adopt` drops a failing step from a new CI and says so). One Python version, ubuntu only |
| stack | `node` | partial | tests only (adopt of a node project in tests/test_install.py and tests/test_sonar.py). No project has `stack: node`: the pnpm `frontend/` of ade and chatpid sits inside a python project and its CI is hand-written; the kit helps there only through the Dependabot npm entry (ade PR 25, chatpid PR 27) | The template installs with `npm ci` and caches npm (the Jira ticket text says pnpm, the file says npm): a pnpm or yarn project fails it. No `factory new --stack node` (`templates/` holds python only), no type-check step. A Python root with a Node subdirectory is detected as python. Sonar node properties never ran on a real project |
| stack | `docs` | partial | tests only (adopt `--stack docs` in tests/test_install.py and tests/test_sonar.py; the docs-only rule of `verify`, FACT-12). No project | CI is a placeholder (`git diff --check`). No link check, no site build, no SonarCloud, Dependabot only for github-actions. Never auto-detected |
| stack | `other` | partial | tests only (the default when no manifest is found). No project | The same placeholder CI as `docs`: the project adds its own build and test steps. No SonarCloud. Dependabot only for github-actions. Every stack below falls back here |
| stack | `go` | not supported | nothing | Adopted as `other` (placeholder CI). No template, CI, SonarCloud properties or `gomod` Dependabot entry |
| stack | `java` | not supported | nothing | Adopted as `other`. No Maven or Gradle CI, no Dependabot entry, no SonarCloud properties |
| stack | `rust` | not supported | nothing | Adopted as `other`. No cargo CI, no Dependabot entry |
| stack | `dotnet` | not supported | nothing | Adopted as `other`. No dotnet CI, no NuGet Dependabot entry |
| stack | `static site` | not supported | nothing | Adopted as `other` or `docs`. No build or deploy workflow, no link check |
| stack | `iac` | not supported | nothing | Terraform, OpenTofu and similar are adopted as `other`. No plan or validate CI, no IaC scanner, no Dependabot terraform entry. A `factory-infra` repository is parked in the roadmap |
| stack | `mobile` | not supported | nothing | Adopted as `other`. No build tooling, no store or signing guidance |
| stack | `notebooks` | not supported | nothing | ade has a `notebooks/` folder, covered only as part of a python project. No notebook stack, no output-stripping or execution check |

## Trackers

The work item id is the tracker key (Treaty 3.2). `tracker` in `.factory/factory.yaml` is `jira`, `github` or
`none`.

| dimension | value | status | proven by | known gaps |
|---|---|---|---|---|
| tracker | `jira` | supported | All three projects: FACT, ADE and CPID keys on every work item, through the agent's Atlassian tools | The CLI has no Jira client: a charter `jira` criterion reads `unknown` without an injected lookup. The Jira key shape is hard-wired in `verify.py`, `work.py`, `decisions.py` and `charter.py`. Seven of the ten skills and docs/jira-workflow.md speak Jira. By convention a project also gets its own Jira project and Confluence space |
| tracker | `none` | partial | tests only (no `--jira`: the id is `F-###` or `B-###`, tests/test_work.py; adopt default; the e2e-001 scratch project). No real project | The skills still say Jira and do not branch on the tracker kind. The findings loop files Jira bugs only, with no tracker-less path. The only workflow document is the Jira one |
| tracker | `github` | not supported | nothing | Inert: `adopt --tracker github` is accepted and recorded in `factory.yaml`, the Treaty lists it, but nothing reads it (no skill, no code path). No issue-number ids (the id pattern is Jira-shaped), no issue creation in the findings loop |
| tracker | `other` | not supported | nothing | Linear, Azure Boards, GitLab issues and the like: `adopt --tracker linear` is rejected (`TRACKERS` is jira, github, none) |

## Hosting and CI

| dimension | value | status | proven by | known gaps |
|---|---|---|---|---|
| hosting | `github.com` | supported | The factory, ade and chatpid, all public with branch protection; `harden`, `doctor`, `status` and `adopt` read through `gh api`; secret scanning, push protection, Dependabot and CodeQL read back as on in all three (2026-10-07) | Needs `gh` logged in for every read (`doctor` warns without). A private repo on a free plan reports `not available` for the protections, and the free SonarCloud plan needs a public repo |
| hosting | `local only` | partial | tests only (a project with no remote keeps a clean `doctor` and skips every GitHub read; the e2e-001 scratch project). No real project | Nothing enforces the gates: `verify` needs a CI to run in. Branch protection and CODEOWNERS are GitHub concepts. The Sonar project key falls back to a marked placeholder |
| hosting | `other host` | not supported | nothing | GitLab, Bitbucket, Azure DevOps and GitHub Enterprise: `harden.repo_slug` accepts only the host github.com, `doctor` prints `skipped`, and skills and policies tell the agent to use `gh`. The parts that only need git (work items, `verify.py`, decisions, charter) have no host dependency |
| ci | `github actions` | supported | All three projects; the factory's own `ci.yml` runs the suite on ubuntu-latest and windows-latest on every PR, with `factory-verify.yml` and a CodeQL result check beside it | The kit templates are starters: ubuntu only, one Python or Node version, actions pinned to a major. ade and chatpid both edited theirs. `adopt` runs the template commands locally through the shell and drops the ones that fail |
| ci | `other ci` | not supported | nothing | GitLab CI, Jenkins, CircleCI, Azure Pipelines: no template and no test. `.factory/verify.py` is standalone and could be called from any CI by hand |

## Scanners and dependency updates

| dimension | value | status | proven by | known gaps |
|---|---|---|---|---|
| scanner | `codeql` | supported | Default setup is configured on the factory (actions, python), ade and chatpid (actions, javascript-typescript, python); code-scanning alerts were fixed as work items (CPID-34, ADE-72) | Enabled by `factory harden` through GitHub's default setup: the language set is GitHub's choice, not the factory's. Not available on a private repo without the plan |
| scanner | `dependabot alerts` | supported | Enabled on all three repos by `harden`; the dependency loop applied in ade (PR 25) and chatpid (PR 27) | A repository setting only; the factory reads alerts and PRs, it does not scan itself |
| scanner | `secret scanning` | supported | Secret scanning and push protection on in all three public repos (read back 2026-10-07) | A private repo needs a paid plan. A revoked secret is the only closure the findings loop accepts |
| scanner | `sonarcloud` | partial | The factory (FACT-41), ade (PR 23) and chatpid (PR 24): analyses read through the public API, gate OK | python and node only (`docs` and `other` get neither file). SonarCloud only, no self-hosted SonarQube. Needs a public repo on the free plan and the owner's organisation and token steps. The node properties never ran on a real project |
| scanner | `container` | not supported | nothing | ade and chatpid ship Dockerfiles and nothing scans the image (Trivy, Grype, Docker Scout) |
| scanner | `iac` | not supported | nothing | No Checkov, tfsec or KICS step; there is no IaC stack either |
| scanner | `licence` | not supported | nothing | No licence policy or check on dependencies |
| scanner | `sbom` | not supported | nothing | GitHub's dependency graph exists; the factory neither reads nor exports an SBOM |
| dependabot ecosystem | `python` | supported | ade (PR 25) and chatpid (PR 27) generated and merged under the dependency loop; the factory itself | `uv` where a `uv.lock` is beside `pyproject.toml`, else `pip`. Other managers (poetry, pipenv, conda) are not detected as such. The weekly Monday schedule and grouping are fixed in the fragment |
| dependabot ecosystem | `npm` | supported | ade and chatpid, directory `/frontend` (pnpm lockfiles), generated with the dependency loop (PR 25, PR 27); frontend advisories were fixed as work items (ADE-77, CPID-36, CPID-43) | One entry covers npm, pnpm and yarn. Detection looks three directories deep; a workspaces monorepo is untested |
| dependabot ecosystem | `github-actions` | supported | Generated for every project; Node 24 action bumps (FACT-15) | none known |
| dependabot ecosystem | `other` | not supported | nothing | gomod, cargo, maven, gradle, nuget, docker, terraform, bundler, composer: no fragment under `kit/dependabot/` and `detect` never emits them |

## Operating systems, agents, project shapes, owners

| dimension | value | status | proven by | known gaps |
|---|---|---|---|---|
| os | `windows` | supported | The daily machine for the factory, ade and chatpid (Windows 11); the windows-latest leg of the factory's CI runs the whole suite on every PR | Needed Windows-specific fixes: long paths, locked folders, shells, CRLF (hashes normalise it). Symlink tests skip without the right. `pytest.exe` is blocked by Application Control, so `python -m pytest`. `adopt` runs template commands with `shell=True` |
| os | `linux` | partial | The ubuntu-latest leg of the factory's CI runs the whole suite (adopt, sync, new, harden against temporary directories) on every PR; every adopted project's CI runs on ubuntu | Nobody has used the CLI by hand on Linux outside those tests. `doctor` marks `uv` required for every stack, even a node or docs project |
| os | `macos` | not supported | nothing | No run, no CI leg, no known break and no evidence. Paths use `pathlib` and nothing needs a shell on purpose, so it may well work |
| agent | `claude code` | supported | All the work on the factory, ade and chatpid; skills under `.claude/skills`; `factory next` prints the prompt | `--run claude` was listed as not exercised in docs/e2e-001.md (the Windows launch) and nothing since records it |
| agent | `github copilot` | partial | tests only (skills laid under `.github/skills`, `copilot-instructions.md`, the `copilot -i` command line). No work item was done with it | No run evidence for any skill under Copilot |
| agent | `other agents` | not supported | nothing | Cursor, Codex, Gemini CLI and the like: `AGENTS.md` is read by several, but nothing was tried; `skill_targets` in `factory.yaml` could point skills at another directory, untested |
| shape | `service or library` | supported | The factory (a CLI and library), ade (a service with a frontend), chatpid | Both services deploy nowhere: `environments` is empty in all three, so `factory-release` has never run a deployment |
| shape | `docs only` | partial | tests only | See the `docs` stack |
| shape | `research or learning` | not supported | nothing | Notebooks, course exercises, spikes: the method assumes code that ships with tests, and its ceremony (spec, plan, test plan, review) is heavy for exploration. `learning/` is deliberately outside the factory |
| shape | `infrastructure` | not supported | nothing | Deployment targets and environments are notes, not tooling; `factory-infra` is parked in the roadmap |
| owners | `one owner` | supported | All three projects, all one person, with delegation recorded in `approve --delegated` | Approval is a ledger kept in git, locked only by GitHub review |
| owners | `several owners` | not supported | nothing | `approvals.by` is a free-text git user name and nothing checks that the approver may approve. The CODEOWNERS template is inert until edited and holds one `<owner>`. The delegation and decision rules say "the owner". The registry is a per-user file |
