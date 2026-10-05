# Autonomy policy

What an agent may do alone, what needs a human first, and what it never does.
Mode is set in `.factory/factory.yaml › autonomy`.

## ALWAYS (no need to ask)

* Read any file in the repo; search; inspect git history.
* Create branches; commit to a feature branch; push that branch.
* Edit code, tests and docs within the scope of the current work item.
* Run tests, linters, formatters and builds locally.
* Open PRs; comment on PRs and Jira issues.
* Write and update `docs/work/<id>-<slug>/` artifacts (spec, plan, test plan, notes).
* Move `item.yaml` status forward from `implementing` onward as the work really progresses.

## ASK FIRST (state what and why, wait for a yes)

* Adding or upgrading a dependency.
* Changing CI, infra, deployment or build configuration.
* Schema or data migrations.
* Deleting files outside the scope of the work item.
* Anything touching authentication, authorization, payments or personal data (PII).
* Broadening scope beyond the approved spec.
* Any network call to a non-dev environment.

## NEVER

* Run `factory approve`, or write `approvals:` entries in `item.yaml`, unless the owner has delegated that gate to you (see Delegated approval). Never record an approval under a human's own name.
* Merge your own PR.
* Push to `main`; force-push a shared branch.
* Deploy to production without a fresh, explicit human go-ahead in the current conversation.
* Disable, skip or delete tests or checks to make something pass.
* Exfiltrate secrets or code; commit secrets.
* Run destructive commands against production data.

## Delegated approval

The owner may delegate the spec or plan approval to an agent. It is valid only when:

* the owner gave an explicit instruction that names the gate(s) and the scope (a work item, a ticket, a run),
  and it is recorded where others can read it (the tracker ticket, the run brief, the conversation). An agent never infers it;
* the agent records it as `factory approve <id> spec|plan --delegated "<owner name>"`, which writes
  `by: "<owner name> (delegated to agent)"` and `delegated: true`. Never under the owner's own name;
* it is never used for a production go-ahead, which needs a fresh explicit human instruction every time. A delegation to merge,
  if given, must be as explicit and recorded as an approval delegation.

`factory status` marks items with a delegated approval, and `verify` accepts the form. Delegation does not replace review:
the PR and its checks still stand.

## Supervised vs trusted

* `supervised` (default): a human approves the **spec** and the **plan** before implementation.
* `trusted`: the plan approval is waived for `risk: low` items only. The spec is always approved.
  Merge and production are always human, in both modes.

If unsure which list an action belongs to, treat it as ASK FIRST.

## What enforces this

Approval in `item.yaml` is a **ledger, not a lock**: it records who approved what, and anyone with
shell access could write it. The lock is GitHub: branch protection, required review, code-owner
review on `docs/work/` and `.factory/` (see `.github/CODEOWNERS`), and the `factory-verify` check.
This policy is what keeps an agent from touching the ledger. Do not rely on the lock to stop you.
