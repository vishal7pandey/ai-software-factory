# docs/work/

Evidence for every change: why it exists, what was agreed, how it was proven. Committed with the code.

## Layout

```
docs/work/<ID>-<slug>/
  item.yaml     machine state: id, type, title, status, risk, jira, branch, approvals, pr
  spec.md       what and why; acceptance criteria (bugs: repro, root cause, regression criterion)
  plan.md       approach, files touched, task list, risks, rollout
  test-plan.md  one row per acceptance criterion -> the test(s) that prove it
  notes.md      optional scratch and decisions
```

`<ID>` is the Jira key (`PF-12`) when there is one, otherwise `F-###` (feature) or `B-###` (bug).

## Status order (forward only)

`draft -> spec-approved -> plan-approved -> implementing -> in-review -> merged -> released -> done`

## Who does what

* **Agent:** writes spec, plan, test plan, code and tests; moves status from `implementing` onward.
* **Human:** approves the spec and the plan (and the plan only if autonomy requires it), reviews and
  merges the PR, authorises production. Agents never approve or merge.

## Approvals

A human records approval with `factory approve <id> spec|plan`, which writes `approvals.<gate>:
{by, at}` into `item.yaml`. Or the human edits that entry by hand. It is a ledger, not a lock: the lock is
branch protection and code-owner review on `docs/work/`. CI (`factory-verify`) flags inconsistencies.

When the owner has explicitly delegated an approval to an agent, it is recorded with
`factory approve <id> spec|plan --delegated "<owner>"` (`by: "<owner> (delegated to agent)"`, `delegated: true`);
`factory status` marks such items. See `.factory/policies/autonomy.md`.

Rules: [.factory/policies/](../../.factory/policies/). Method: skill `factory-workflow`.
