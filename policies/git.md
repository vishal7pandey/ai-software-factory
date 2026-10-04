# Git policy

## Branches

Branch from an up-to-date `main`. The work-item id is lower-cased in the name.

* `feature/<id>-<slug>` — features, e.g. `feature/pf-12-add-google-login`
* `fix/<id>-<slug>` — bugs
* `chore/<slug>` — maintenance, deps, tooling (no work item needed)
* `docs/<slug>` — documentation only

`factory-verify` requires an item at `implementing` or later for `feature/` and `fix/` branches.
`chore/`, `docs/`, `deps/` and `main` are exempt.

## Commits

* Conventional commits: `type(scope): summary`, types `feat fix docs test refactor chore ci`.
* Put the work-item id in the scope or body: `feat(PF-12): add Google OAuth callback`.
* Small, single-purpose commits that each leave the tests passing.
* Imperative summary, <= 72 characters; body says why, not what.
* Never commit secrets, `.env` files, build output or large binaries.

## Pull requests

* One PR per work item. Title: `<ID>: <title>`, e.g. `PF-12: Add Google login`.
* Fill in the PR template: AC to test table, risk, verification, gates.
* Link the spec and plan paths. Keep the PR within the approved scope.
* A human merges. Squash or merge-commit is the project's choice; follow what the repo already does.

## History

* Never rewrite shared history: no force-push to `main` or any branch others use.
* Rebasing your own unshared branch, or `--force-with-lease` on it, is fine.
* Never `git reset --hard` or `git clean -fd` over uncommitted work you did not create.
* Never bypass hooks (`--no-verify`); fix the cause.
