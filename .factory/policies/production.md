# Production policy

## Environments

Promote in order: **dev → test → prod**. Never skip an environment; never deploy a build to prod that
was not already deployed and verified in the one before. Environment URLs/notes: `.factory/factory.yaml`.

## Prod needs a human, every time

* Deploying to prod requires a fresh, explicit go-ahead from a human in the current conversation.
  Earlier approvals, merged PRs and "just ship it" in a ticket do not carry over.
* Agents never hold prod credentials and never run prod-mutating commands.
* Record who authorised the release and when (`notes.md` or the PR), then `advance` to `released`.

## Before deploying

* A rollback plan is written down first: how to revert, how long it takes, what data cannot be reverted.
* Migrations are backward compatible with the previous release, or the plan says why not.
* The smoke test (a short script or checklist of the critical user path) exists and passed in the
  previous environment.

## After deploying

* Run the smoke test against prod. If it fails, roll back first and diagnose afterwards.
* Watch errors and key metrics for the agreed window. Then mark the item `released`, then `done`.

## Never

* Debug by mutating prod data, running ad-hoc queries that write, or "fixing up" records by hand.
  Reproduce in dev or test with copied or synthetic data.
* Disable monitoring, alerts or checks to get a release through.

## Incidents

1. **Mitigate:** stop the harm first: roll back, disable the flag, or scale down. A human decides.
2. **Diagnose:** gather logs, timeline and a reproduction, without changing prod data (`factory-diagnose`).
3. **Fix:** go through the bug path: a bug work item, regression test first, normal gates.
4. **Post-incident note** in the work item `notes.md`: timeline, root cause, impact, what changed,
   what would have caught it. Blameless, short.
