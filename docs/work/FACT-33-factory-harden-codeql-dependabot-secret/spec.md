# FACT-33 — factory harden: CodeQL, Dependabot, secret scanning

Status: draft · Risk: medium · Jira: FACT-33
Created: 2026-10-05 · Slug: factory-harden-codeql-dependabot-secret

## Problem

On 2026-10-05 CodeQL, Dependabot alerts and security updates were switched on by hand for the four public
repos. A manual step that nothing checks decays: the next adopted project will not have it, and nobody
notices a protection that was later turned off. The owner decided this must be part of the factory
itself (umbrella FACT-11, part 1): the factory enables the repository-level protections for any
GitHub-hosted project and verifies they are still on.

## Users and context

The owner or an agent adopting a project, and anyone running `factory doctor` on one. Grounded in
`src/swfactory/cli.py` (command modules), `commands/doctor.py` and `checks.py` (the doctor findings),
`installer.py` (`adopt`, `_git_remote`, `normalise_repo_url`), `docs/ARCHITECTURE.md` section 3.7 (CLI
surface, "no command may require network except where noted") and `policies/security.md`. The GitHub
API calls were checked against the live repo with `gh api -i` on 2026-10-05 (status line is printed even
for 4xx; `automated-security-fixes` returns JSON, `vulnerability-alerts` returns 204/404).

## Goals and non-goals

**Goals**
- One command, `factory harden`, that turns on four protections for a project's GitHub repo and is safe
  to re-run: secret scanning with push protection, Dependabot alerts, Dependabot security updates, and
  CodeQL default setup.
- `factory doctor <path>` reports the same four as `ok` / `off` / `unknown` (or `not available`) and
  fails when one is off on a public repo.
- `factory adopt` shows the plan and the one command to apply it, but never changes settings itself.

**Non-goals**
- Reading, triaging or dismissing findings (alerts): FACT-34 and later.
- Branch protection, rulesets, CODEOWNERS, SonarQube, dynamic analysis (other tickets).
- Hosts other than github.com; GitHub Enterprise Server.
- Choosing CodeQL languages or query suites beyond "default setup, default suite" (GitHub detects the
  languages).
- Writing the manual `gh api` fallback into `policies/findings.md` (R5 of the ticket belongs to FACT-34).
  This ticket makes `--dry-run` print the exact calls, so the fallback exists as output.

## Requirements

- R1. `factory harden [path] [--dry-run]` derives owner and repo from the project's `origin` git remote
  and enables, through `gh api`: secret scanning plus push protection, Dependabot alerts, Dependabot
  security updates, and CodeQL default setup (`state=configured`, `query_suite=default`). It reads the
  current state first and only changes what is not already on (idempotent; "already on" is not an
  error). With `--dry-run` it prints what it would do and issues no write call.
- R2. `factory adopt` (also with `--dry-run`) ends by printing the harden plan in dry-run form and the
  one command that applies it. It never writes repo settings. If the project has no GitHub remote or
  `gh` cannot be used, it says so in one line and still succeeds.
- R3. `factory doctor <path>` (and `doctor` run inside an adopted project) reports each of the four
  protections as `ok`, `off` or `unknown`, plus `not available` where the repo cannot have it. It exits
  non-zero when any protection is `off` on a public repo. `unknown` (for example `gh` unauthenticated)
  and `not available` never fail the check.
- R4. A protection that cannot be enabled (private repo or plan without the feature, missing
  permission) is reported per protection and does not stop the others. A failure is reported with the
  HTTP status only, never the response body. A private repo without the feature is reported
  `not available`.
- R5. The tests never touch the network: all `gh` access goes through one small runner function that
  tests replace.

## Acceptance criteria

- AC1. (R1) With a stubbed runner on a repo where nothing is on, `harden` issues exactly these writes, in
  this order: `PATCH repos/{o}/{r}` with `security_and_analysis` secret scanning and push protection
  `enabled`; `PUT repos/{o}/{r}/vulnerability-alerts`; `PUT repos/{o}/{r}/automated-security-fixes`;
  `PATCH repos/{o}/{r}/code-scanning/default-setup` with `state=configured`, `query_suite=default`.
  With a protection already on, its write is not issued; with all four on, no write is issued and
  the exit code is 0. Owner and repo are taken from the git remote (https and ssh forms).
- AC2. (R1, R2) `--dry-run` issues no write call (only reads), prints the writes it would make, and
  exits 0; `adopt` issues no write call either, and prints the plan plus a line naming
  `factory harden <path>`.
- AC3. (R3) With a stubbed runner reporting one protection disabled on a public repo, `doctor <path>`
  prints `off` for it and exits non-zero; on a private repo the same state does not fail; when `gh`
  fails (status 0 or HTTP 401) every protection prints `unknown` and doctor does not fail on them.
- AC4. (R4) If one write fails (CodeQL `PATCH` returns 403), the other protections are still attempted,
  the failed one is reported as `HTTP 403`, the exit code is 1, and neither the response body nor any
  text from it appears in the output (the stub's body contains a marker string that must not be
  printed). On a private repo the same 403 is reported as `not available (HTTP 403)` and does not
  make the exit code non-zero.
- AC5. (R1) Run for real against the factory repo (all four already on): `factory harden` reports all
  `ok`, issues no write, and `factory doctor` on it reports all `ok` and passes. Evidence recorded on
  the ticket.
- AC6. (R5) `factory lint` and the full test suite pass; the suite contains a guard so a test cannot
  reach the real `gh`; ARCHITECTURE section 3.7 and the README list the new command and note the
  `gh` use; kit docs (`policies/security.md`) mention it and the managed copies are synced.

## Edge cases and failure modes

- No `origin` remote, or a non-github.com remote: `harden` exits 1 with a clear message; `adopt` prints
  one line and succeeds; `doctor` reports `unknown`, not a failure.
- `gh` not installed, not logged in, timeout: runner returns status 0; every protection is `unknown`;
  `harden` without `--dry-run` exits 1 ("cannot read the repository settings"), with `--dry-run` it
  prints the plan with unknown states and exits 0.
- Repo metadata readable but `security_and_analysis` absent (caller is not an admin): secret scanning
  and Dependabot updates are `unknown`, not `off`.
- Dependabot security updates need alerts first: alerts are enabled before updates.
- CodeQL default setup returns 202 (queued): treated as success. A repo with CodeQL already
  `configured` is skipped; any other state is `off`.
- Write attempted on a state that raced to enabled in between: the API call is idempotent; fine.
- Windows: no shell quoting involved (argv list, JSON body on stdin).

## Non-functional requirements

- Security (`policies/security.md`): no secret or token is read or printed; response bodies from failed
  calls are never printed; GET bodies are parsed for state only. Changing repo settings is the point
  of the command, so it only runs when the user types `harden` without `--dry-run`.
- Compatibility: Python >= 3.12, stdlib + PyYAML only; ASCII output; works on Windows and Linux.
- Network use is limited to `harden` and `doctor` with a project (documented in ARCHITECTURE 3.7);
  each call has a timeout (30 s).

## Assumptions

- "The four protections" are: secret scanning with push protection (one protection, set by one call),
  Dependabot alerts, Dependabot security updates, CodeQL default setup. Overrule at approval if
  push protection should be reported separately.
- The state word set is `ok`, `off`, `unknown`, plus `not available` (R4), so a private repo without
  GitHub Advanced Security does not fail doctor or look broken.
- A non-admin collaborator getting 403/404 on a write is reported as a failure (HTTP status), not
  retried.
- `adopt` printing needs read access only; with no `gh` it degrades to one line.

## Risks and dependencies

Risk medium: the command changes security settings on a real repository, but only on explicit apply, the
changes are all reversible in the repo settings, and every call is idempotent. Depends on `gh` being
installed and authenticated with `repo` scope (and repo admin) for a real run. GitHub may rename API
fields; tests use stubs, so the real-repo run (AC5) is the integration proof.

## Open questions

None.
