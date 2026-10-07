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

* Adding or upgrading a dependency (a Dependabot PR under `dependencies.md` is the exception; every other Dependabot PR is a work item).
* Changing CI, infra, deployment or build configuration.
* Schema or data migrations.
* Deleting files outside the scope of the work item.
* Anything touching authentication, authorization, payments or personal data (PII).
* Broadening scope beyond the approved spec.
* Dismissing or resolving a scanner finding, and changing a repo's security settings (`findings.md`).
* Any network call to a non-dev environment.

## NEVER

* Run `factory approve`, or write `approvals:` entries in `item.yaml`, unless the owner has delegated that gate to you (see Delegated approval). Never record an approval under a human's own name.
* Run `factory decide`, or write `status`, `decision`, `by` or `at` into a decision record yourself: answering a decision is the owner's act (see Owner decisions). Never record a decision under a human's own name.
* Merge your own PR, or any PR except a Dependabot PR that meets every condition of `dependencies.md` (the one standing exception; the conditions are conjunctive, a major or a failing check never qualifies).
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

## Owner decisions

A choice that belongs to the owner (a design direction, a scanner-finding dismissal, a project charter) is not asked
only in chat: the agent opens a decision record in `docs/decisions/` (`factory decision new`), recommends one option and
stops. `factory status`, `factory doctor` and `factory inbox` list what waits. The owner answers with
`factory decide`; an agent never runs it on its own. The agent acts on the answer only when the record is `accepted`
with `by` and `at` (`factory verify` fails one without them).

* `charter` and `dismissal` decisions are never delegated to an agent, even on request: `decide --delegated` refuses
  them and `verify` fails a record that says otherwise.
* A `design` or `other` decision may be delegated only by an explicit owner instruction recorded where others can read
  it, naming that decision; the form is `factory decide <id> --accept --delegated "<owner name>"` (`by: "<owner name>
  (delegated to agent)"`, `delegated: true`). An agent never infers it.
* Like `approve`, `decide` is a ledger, not a lock: GitHub review on `docs/decisions/` is the lock.

### The project charter

`docs/PROJECT.md` (purpose, 3 to 7 measurable done criteria, non-goals, parked list, maintenance mode) is approved only
through a `charter` decision, which is never delegated to an agent. The agent may draft or amend the file and propose
the record; it never runs `factory decide`, never edits `decision:` to name a record the owner has not accepted, and
never switches `mode:` to `maintenance` on its own. An edit after approval shows as `changed` in `factory doctor` and
needs a new decision. New work is checked against the charter (`factory-spec`); in maintenance mode only security and
dependency updates go ahead without a charter amendment.

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
