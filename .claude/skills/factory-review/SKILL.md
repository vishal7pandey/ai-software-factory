---
name: factory-review
description: Use when a work item is at status in-review (PR open or branch ready) and needs an independent pass against its spec before a human merges, or when the implementer has pushed fixes and only the delta needs re-review. Do not use to implement or fix the code yourself, to review work whose spec.md is not approved, or to merge or approve anything.
---

# factory-review

## When to use

- Status is `in-review`: implementation is finished, tests written, a PR exists or the branch is ready.
- Re-review: the implementer fixed findings; review only what changed since your last pass.
- You wear a different hat from the implementer. If you wrote this code in this session, say so in the review and apply extra suspicion: re-derive everything from the spec, not from memory of your intent.

## Inputs

- `docs/work/<id>-<slug>/spec.md` (read FIRST), then `plan.md`, `test-plan.md`, `notes.md`, `item.yaml`.
- The diff: `git diff <base>...HEAD` (base is usually `main`), plus `git log --oneline <base>..HEAD`.
- `.factory/policies/security.md`, `.factory/policies/testing.md`, `.factory/policies/git.md`.
- CI status: `gh pr checks <pr>` when `gh` is available (else ask the human to paste it or open the Checks tab).

## Steps

1. **Assume nothing.** Do not trust the PR description, commit messages, or plan.md claims. Read spec.md first and write down the ACs. Then read the diff, then the tests. Read code, do not skim stat lines.
2. **Check CI.** `gh pr checks <pr>`: list failing/pending checks. Failing CI is a blocker unless it is demonstrably unrelated (then say why and link evidence). Run the project's tests/linter locally if CI is unavailable.
3. **Review against these seven lenses, in order**, recording findings with file:line:
   1. **Every AC met, demonstrably.** For each AC cite where the behaviour lives (`file:line`) and the test that proves it (`path::name`). An AC without both is a blocker.
   2. **Scope.** Flag unrelated changes, drive-by refactors, reformatting of untouched files, new dependencies, debug leftovers, commented-out code, anything not traceable to an AC or plan.md task.
   3. **Correctness and edge cases.** Boundaries, null/empty, error paths, concurrency, resource cleanup, idempotency, time/locale, backwards compatibility of any public interface.
   4. **Tests prove the AC.** Compare against test-plan.md: every row points to a real test; assertions are meaningful; the test would fail if the behaviour broke (reason concretely or temporarily break it, then restore). Tests that only exercise mocks or assert nothing are findings.
   5. **Security** per `.factory/policies/security.md`: input validation, authn/authz, injection, secrets in code/logs/fixtures, unsafe deserialization, new dependencies, error messages leaking internals, PII in logs.
   6. **Maintainability.** Naming, size of functions, duplication, comments that explain why, consistency with surrounding code, no speculative generality.
   7. **Docs, config, migrations.** README/docs updated, config defaults and env vars documented, migrations reversible and ordered, changelog if the project keeps one, factory docs/work files consistent with what was built.
4. **Label every finding** with exactly one severity:
   - `blocker`: AC unmet or unproven, bug, security issue, data loss risk, failing CI, broken build.
   - `should-fix`: real weakness that is cheap to fix now (weak test, missing edge case, scope creep, missing doc).
   - `nit`: taste; the implementer may ignore.
   Each finding: severity, `file:line`, what is wrong, why it matters, suggested fix (one sentence).
5. **Deliver.** Append a section to `docs/work/<id>-<slug>/notes.md` titled `## Review <n> — <YYYY-MM-DD>` containing the AC table (AC | evidence | test | met?), the findings, the CI result, and the verdict. If `gh` is available also post it: `gh pr comment <pr> --body-file <file>` (or `gh pr review <pr> --comment`; never `--approve`). Security findings with exploit detail go in notes.md only if the repo is private; in a public PR comment write "security finding, see private notes".
6. **Verdict** is exactly one of: `ready for human merge` (no open blockers or should-fix) or `changes needed` (list them). Nothing else.
7. **Loop.** After the implementer fixes blockers and should-fix, re-review only the delta (`git diff <last-reviewed-sha>..HEAD`), re-check CI, confirm each previous finding is resolved, and append `## Review <n+1>`. Re-open the full review only if the delta touches an AC's behaviour broadly or CI regressed.

## Output

- Section appended to `docs/work/<id>-<slug>/notes.md` (always).
- PR comment with the same content (when `gh` is available).
- A one-paragraph message to the human: verdict, count of findings per severity, CI state.

## Definition of done

- Every AC has file:line evidence and a test citation in the review, or a blocker saying why not.
- All seven lenses were applied; CI status was checked and recorded.
- Every finding has a severity and a location; verdict is one of the two allowed phrases.
- On re-review: each earlier blocker/should-fix is marked resolved or still open.

## Never

- Never merge, approve the PR (`gh pr review --approve`, `gh pr merge`), or run `factory approve`; the human merges.
- Never fix the code yourself during review; send findings to the implementer (factory-implement), unless the human asks you to switch hats.
- Never review from the PR description or plan alone; always read spec.md, the diff and the tests.
- Never reword the spec to make the diff pass; a spec gap is a finding for the human.
- Never post secrets, tokens or exploit details in a public PR comment.
