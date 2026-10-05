# FACT-33 — Plan: factory harden: CodeQL, Dependabot, secret scanning

Status: spec-approved · Risk: medium · Jira: FACT-33
Created: 2026-10-05 · Slug: factory-harden-codeql-dependabot-secret · Spec: spec.md

## Summary

A new module `src/swfactory/harden.py` holds all the logic (read state, plan, apply, format, doctor
findings) behind one runner function `gh_api(method, path, body)`; `commands/harden.py` is the thin
argparse wiring. `doctor` and `adopt` call into it. Tests stub the runner; a conftest guard makes the real
`gh` unreachable from the suite. **Size:** M.

## Current state

- `src/swfactory/cli.py`: `COMMAND_MODULES = ["install", "doctor", "lint", "work"]`; each module has
  `register(subparsers)`; `FactoryError` -> exit 1.
- `commands/doctor.py` prints `checks.check_project(...)` findings and counts FAIL/WARN; `checks.Finding`
  (OK/WARN/FAIL), `checks.format_findings`.
- `installer.py`: `adopt()` prints findings then runs `_install`; `_git_remote(root)` and
  `normalise_repo_url` give `host/owner/name`. Tests in `tests/test_install.py`, `test_integration.py`
  assert on adopt output, so the new trailing block must not break them (checked by running them).
- `tests/conftest.py` already has autouse isolation fixtures (home, registry, project commands).
- `docs/ARCHITECTURE.md` 3.7 (command table, "no command may require network except where noted"),
  `README.md` quick start, `policies/security.md` (copied into projects through `kit/manifest.yaml` dir
  `policies`, so no manifest edit is needed).
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run factory lint`, `uv run factory sync --check .`, `uv run python .factory/verify.py`.
- Verified live with `gh api -i`: status line comes first even for errors; `GET code-scanning/default-setup`
  -> `{"state": "configured"}`; `GET vulnerability-alerts` -> 204 (on) / 404 (off);
  `GET automated-security-fixes` -> `{"enabled": bool}`.

## Approach

States: `ok`, `off`, `unavailable` ("not available"), `unknown`. Four protections in a fixed order:
`secret-scanning`, `dependabot-alerts`, `dependabot-updates`, `code-scanning`.

- Runner `gh_api(method, path, body=None) -> (status, data)`: runs `gh api -i -X METHOD path` (JSON body
  on stdin via `--input -`, argv list, no shell), splits the status line from the JSON body, returns
  `(0, None)` when `gh` is missing, times out or prints nothing parseable. The OS call is one tiny
  function `_run_gh(argv, stdin)` so the parsing is testable too. Only GET bodies are ever looked at, for
  state; error bodies are dropped there and never printed.
- `read_state(owner, repo, gh)`: `GET repos/o/r` (private flag, `security_and_analysis` statuses), then
  `vulnerability-alerts`, `automated-security-fixes`, `code-scanning/default-setup`. A failing read gives
  `unknown` with `HTTP n`; on a private repo 403/404/422 on a read gives `unavailable`.
- `plan(...)`: per protection `skip` (ok), `skip` (unavailable) or `enable` (off/unknown) with the exact
  call. `apply` runs the enable calls in the fixed order (alerts before updates), each result 2xx ->
  `enabled`; otherwise `failed (HTTP n)` or, on a private repo with 403/404/422, `not available (HTTP n)`.
  One protection's failure never stops the others. Exit 1 if any failed.
- `repo_slug(root)`: `origin` URL via `installer._git_remote`-style normalisation; requires host
  `github.com`. To avoid an import cycle `installer` imports `harden` lazily inside `adopt`.
- `doctor_findings(root, gh)`: one `Finding` per protection: ok -> OK, off -> FAIL on a public repo (WARN on
  private), unknown/unavailable -> WARN. No remote or non-GitHub -> one WARN `unknown`.
- `adopt_note(root, gh)`: prints `repo protections (dry-run):` plan lines and
  `apply with: factory harden <path>`; never raises, never writes.

**Alternatives rejected**
- PyGithub or `urllib` with a token: new dependency or token handling; the platform's CLI already
  authenticates (principle 1: do not own what the platform provides).
- Runner returning `(returncode, text)` like `checks.run_cmd`: would force every caller to re-parse HTTP
  status lines; a status-aware runner keeps "HTTP status only" in one place.
- Putting the logic in `checks.py`: that file is already 470 lines of lint+doctor; harden is its own unit.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Test guard: autouse fixture makes `harden._run_gh` fail (no network); `harden.py` skeleton with `gh_api` response parsing and `repo_slug` + tests | `tests/conftest.py`, `src/swfactory/harden.py`, `tests/test_harden.py` | AC1, AC6 | pytest `-k "gh_api or slug or guard"` |
| T2 | `read_state` and the four state mappings + tests | `src/swfactory/harden.py`, `tests/test_harden.py` | AC1, AC3 | pytest `-k state` |
| T3 | `plan` / `apply` / output, `--dry-run`, failure isolation, status-only reporting + tests | same | AC1, AC2, AC4 | pytest `-k "apply or dry or fail"` |
| T4 | `factory harden` command wiring (`COMMAND_MODULES`) + CLI-level tests | `src/swfactory/cli.py`, `src/swfactory/commands/harden.py`, `tests/test_harden.py` | AC1, AC2 | pytest |
| T5 | doctor integration + tests | `src/swfactory/commands/doctor.py`, `src/swfactory/harden.py`, `tests/test_doctor.py` or `tests/test_harden.py` | AC3 | pytest `-k doctor` |
| T6 | adopt ends with the dry-run plan + tests; fix any existing adopt output assertion | `src/swfactory/installer.py`, `tests/test_install.py` or `tests/test_harden.py` | AC2 | pytest |
| T7 | Docs: ARCHITECTURE 3.7, README, `policies/security.md`; `factory sync .`; lint | `docs/ARCHITECTURE.md`, `README.md`, `policies/security.md`, managed copies | AC6 | `factory lint`; `sync --check .` |
| T8 | Real run against this repo (all on): `harden`, `doctor`; record on the ticket; mutation audit | none | AC5 | output captured |

## Data, API and migration impact

New CLI command `harden [path] [--dry-run]`; `doctor` and `adopt` print more; doctor can now exit 1 on an
`off` protection of a public repo (a new failure mode for existing users who ran `doctor <path>` on a repo
without the protections, which is the intent). No config schema change, no new dependency, no migration.

## Security and failure modes

Writes repo security settings only on `harden` without `--dry-run`. Calls use `gh`'s own authentication; the
tool never reads a token. Response bodies of non-GET calls and of failed calls are discarded; messages
carry the HTTP status only. Failures: gh missing/unauthenticated -> `unknown` and (apply) exit 1; 403 on a
write -> reported, others continue; no remote -> clear error. Idempotent writes make a re-run after a
partial failure safe.

## Rollout and rollback

Merge the PR; adopted projects get the new kit text with `factory sync`. Nothing changes in any repo until
someone runs `factory harden`. Rollback: revert the PR. Repo settings enabled by a run stay on (turn off
in the repo's security settings if wanted); there is no point of no return.

## Risks and open points

- GitHub API field or status differences for edge repos (forks, org policies): covered by "unknown" and
  per-protection failure reporting; the real run on this repo is the integration proof.
- `adopt` now makes read calls to the network when `gh` is available; failures degrade to one line.
- Test-plan Audit must prove the status-only rule with a body marker, not just by reading.
