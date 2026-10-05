---
name: factory-release
description: Use when a work item is at status merged and its change must be rolled out and verified through the project's environments (dev, test, prod as configured in .factory/factory.yaml), then closed out as released and done. Do not use before the PR is merged to main with green CI, to approve or merge anything, or to deploy to prod without an explicit human go-ahead given for that release.
---

# factory-release

## When to use

- `item.yaml` status is `merged` (PR merged to main; the PR's last commit recorded the status before the merge). You take it to `released`, then `done`, recording that after the release by a docs-only PR (a status commit straight to `main` is not allowed).
- Nothing to release to? When `.factory/factory.yaml › environments` has no configured environment (all `null` or absent), `merged` is the end of the line: do nothing here, `factory status` already treats the item as complete.
- Also for projects with no deployment (library, docs): release means tag/publish per the project's convention; say so explicitly in notes.md and treat that as the single "environment".
- Not for: deploying unmerged branches, hotfix incident mitigation (factory-diagnose handles mitigation decisions), or approving production by yourself.

## Inputs

- `docs/work/<id>-<slug>/{item.yaml,spec.md,notes.md}` — ACs drive the smoke checks.
- `.factory/factory.yaml › environments` — e.g. `{dev: <url|note>, test: <...>, prod: <...>}`. A key with value `null` or absent means skip that environment, and you say so in notes.md.
- `.factory/policies/production.md` and `.factory/policies/git.md`.
- How the project deploys: CI workflow, `Makefile`/scripts, README/runbook. Find it; do not invent a deploy method.
- `gh` when available (`gh run list`, `gh release`), else read the Actions tab via the human.

## Steps

1. **Check preconditions.** Merge commit is on `main` (`git fetch && git branch -r --contains <sha>`), `gh pr view <pr> --json state,mergedAt` says MERGED, CI on that commit is green (`gh run list --branch main --limit 3`; else ask the human). If either fails, stop and report; do not release.
2. **Plan the release.** Read `environments`; list the ones to walk in order dev → test → prod, skipping `null`. Identify the artifact (commit sha, image tag, version) and how each environment is deployed (automatic from main via CI, manual command, tag). Write the plan into notes.md under `## Release <YYYY-MM-DD>`.
3. **Derive smoke checks from spec.md.** For each AC (at least the headline ones) write one concrete check: a command (`curl -fsS <url>/health`, CLI invocation, query), or a manual observation with exact steps and expected result. Add: app starts, health endpoint, one read path, no new error spikes in logs. Keep it to a few minutes of checks.
4. **For each environment in order (dev, then test, then prod):**
   1. Deploy the identified artifact (or confirm CI auto-deployed it) and record the deployed version/commit.
   2. Run the smoke checks. Record in notes.md: environment, UTC timestamp, deployed version/commit, each check with result (pass/fail + evidence line).
   3. If any check fails: stop, do not continue to the next environment, record the failure, and tell the human with a recommendation (fix forward as a new bug item, or roll back). Move on only after a pass.
5. **Before prod: stop and ask the human.** State: what is shipping (id, title, commit), dev/test results, the **rollback plan** (exact command or revert PR, data/migration reversibility, who does it), and the watch window (what to monitor, for how long, thresholds). Wait for an explicit go-ahead for THIS release, in words. Earlier approval of the spec, plan, merge or a previous release is not a go-ahead. If prod is `null`, skip and record "prod: skipped (not configured)".
6. **Deploy prod and verify.** After the go-ahead deploy (or have the human trigger it if policy says so), run the smoke checks, then keep the watch window: check logs/metrics/errors at the intervals you stated and record each check with a timestamp. Any regression: recommend rollback immediately and ask the human.
7. **Move status.** After all configured environments pass, set `status: released` (run `factory advance <id> released`, or edit `item.yaml` by hand: set `status: released`). After the watch window is clean and follow-ups are filed, set `status: done` the same way.
8. **Close the loop.** Link the release (version, tag or run URL) in the PR (`gh pr comment`) and the Jira issue if `item.yaml › jira` is set (comment and transition via the tracker; if there is no tool access, give the human the text). Update CHANGELOG/release notes if the project keeps one, and docs affected by the change. Create a follow-up work item (`factory feature start` / `bug start`, or ask the human) for anything deferred, known issues, or cleanup such as removing a feature flag; list them in notes.md.
9. **Library/docs projects.** Create the tag/publish step per convention (`git tag vX.Y.Z`, package publish, docs deploy); confirm the human wants that version number and publish target before pushing the tag; verify by installing/loading the published artifact; then step 7 onward.

## Output

- `notes.md` section `## Release <date>`: plan, per-environment result table (env | time UTC | version/commit | checks | result), rollback plan, human go-ahead (who, when, quote), watch-window log, follow-ups.
- `item.yaml` status `released`, later `done`.
- PR and Jira updated with the release link; changelog/docs updated if applicable.

## Definition of done

- Every configured environment was deployed in order and smoke-checked, each recorded with timestamp and version/commit.
- Prod (if configured) had an explicit human go-ahead for this release, a stated rollback plan, a post-deploy verification and a watch window.
- Status advanced to `released`, then `done`; PR/Jira linked; follow-up items created for everything deferred.

## Never

- Never deploy to prod without an explicit human go-ahead for this specific release; never infer it.
- Never release unmerged code or code whose CI on main is red.
- Never skip an environment that is configured, reorder environments, or continue after a failed smoke check.
- Never run `factory approve` or merge a PR; humans own approvals and merges.
- Never mark `released` or `done` without recorded smoke results, and never hide a failed check.
