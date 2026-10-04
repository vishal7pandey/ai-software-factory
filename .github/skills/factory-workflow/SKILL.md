---
name: factory-workflow
description: Use when starting or resuming ANY engineering task in a repo that has adopted the factory kit (a feature, bug, refactor, incident, security finding, or chore) and you must decide where to enter and which skill comes next. Reads the work item state and routes to factory-spec, factory-plan, factory-test, factory-implement, factory-review, factory-diagnose or factory-release. Do not use to do the work itself, and do not use for questions that need no repo change.
---

# factory-workflow — the router

## When to use
- At the start of every task and every time you resume one: you decide the entry point and the next skill from the work item's state, not from habit.
- When new information appears mid-task (a spec assumption proves false, a plan task is impossible) and you must decide how far back to go.
- Not for doing the work: this skill only routes. Not for pure questions or read-only investigation.

## Inputs
- `AGENTS.md` and every file in `.factory/policies/` (`security.md`, `git.md`, `testing.md`, `production.md`, `autonomy.md`). Read them at the start of the session, not when something goes wrong.
- `.factory/factory.yaml` (`autonomy`, `tracker`, `environments`).
- The request, and any work item id, Jira key, branch name or PR the human mentioned.
- `docs/work/<id>-<slug>/item.yaml` and the files beside it (`spec.md`, `plan.md`, `test-plan.md`, `notes.md`).

## Steps
1. **Find the item.** Look in `docs/work/*/item.yaml` for the id/Jira key in the request, or for the current branch name (`git branch --show-current`; branch is `feature/<id>-…` or `fix/<id>-…`). Read `item.yaml`, then `notes.md` (newest entries first) so you inherit earlier decisions.
2. **No item and the task is not exempt?** Create one. Either run `factory feature start "<title>"` / `factory bug start "<title>"`, or by hand: id = Jira key if given, else `F-###` (feature) / `B-###` (bug), next free number, zero-padded; dir `docs/work/<ID>-<slug>/`; `item.yaml` with `type`, `title`, `slug`, `status: draft`, `risk`, `jira`, `branch` (`feature/<id-lowercase>-<slug>` or `fix/…`), `created`, `pr: null`. Doc templates are in `.factory/templates/work/` (spec.feature.md, spec.bug.md, plan.md, test-plan.md); copy them in, replacing the placeholders. Create the branch from the default branch.
3. **Pick the entry point** (new tasks):

   | Situation | Route |
   |---|---|
   | New feature or enhancement | `type: feature` → `factory-spec` |
   | Bug, unexpected behaviour | `type: bug` → `factory-diagnose` (reproduce, root cause, spec with regression criterion), then rejoin at plan |
   | Refactor | No dedicated skill. `type: feature`; spec = goal + constraints + risk assessment + criteria of the form "behaviour X is unchanged" (name the tests that pin it); then `factory-plan` as usual |
   | Production incident | Mitigate first (rollback, flag off, scale — per `production.md`); record what you did in `notes.md`; then open a bug item and take the bug path |
   | Security finding | Validate it is real and reachable, assess impact and exposure, then bug path; `risk: high`; `factory-review` must include a security pass |
   | Chore / docs / deps | Exempt, see below |

4. **Exempt chores.** No work item, branch `chore/…`, `docs/…` or `deps/…`, only when ALL hold: tiny (roughly < 50 lines changed), no change to runtime behaviour, no schema/API/config-semantics change, no auth/security-relevant change, CI is green. Examples: typo and README fixes, comment edits, patch-level dependency bumps with unchanged tests. A dependency bump that needs code changes or touches auth/crypto is not a chore: make it an item. If in doubt, make it an item.
5. **Route by status** (existing items):

   | status | next | who moves it on |
   |---|---|---|
   | `draft`, no `spec.md` or spec incomplete | `factory-spec` (bug: `factory-diagnose`) | Human approves spec (you stop and ask) |
   | `draft`, spec finished | Ask the human to approve the spec | Human |
   | `spec-approved` | `factory-plan` | Human approves plan (unless waived, below) |
   | `plan-approved` | `factory-test` to write `test-plan.md`, then set `status: implementing` | You |
   | `implementing` | `factory-implement` | You, to `in-review` |
   | `in-review` | `factory-review`; fixes loop back to `factory-implement` | Human merges |
   | `merged` | `factory-release` | You, to `released` then `done` |
   | `released` | `factory-release` (verification, record, close Jira) | You, to `done` |

   Edit `item.yaml` `status:` by hand (or `factory advance <id> <status>`). Statuses only move forward, in this order: draft → spec-approved → plan-approved → implementing → in-review → merged → released → done.
6. **Stop at human gates.** Spec approval, plan approval, merge, and production are human decisions. When you reach one: finish the artifact, summarise it in 5 lines (what, risks, open assumptions), ask the human to approve it, and stop. Approvals live in `item.yaml › approvals`; you never write them and never run `factory approve` yourself. If asked to act on an unapproved item, say which approval is missing and stop.
7. **Autonomy.** `supervised` (default): spec and plan approvals are both required. `trusted`: the plan approval is waived for `risk: low` items only; spec approval, merge and production always stay human. Read `.factory/factory.yaml` for the value; when unsure, assume `supervised`.
8. **Graph, not pipeline.** If new information invalidates an earlier artifact (a test shows the spec's assumption is false; exploring code shows the plan cannot work), stop, go back to the earliest artifact affected, amend it, and add a dated entry to `notes.md` saying what changed and why. Approvals were given against the old text: tell the human the artifact changed and ask them to re-approve (they re-approve; you do not touch `approvals`). Continue downstream only after that. Never silently diverge from an approved artifact.
9. **Evidence.** Everything about the item lives in `docs/work/<id>-<slug>/` and is committed with the code on the item branch: spec, plan, test-plan, notes, and any logs/screenshots/benchmark output that prove an AC. Decisions and surprises go in `notes.md` as they happen, one dated bullet each.
10. **Jira sync.** Only if `item.yaml › jira` is set AND Atlassian/Jira tools are available: at each status transition add one comment with the new status and links (spec, plan, PR). Do not change Jira workflow states unless `docs/jira-workflow.md` or the human says to. If Jira is unreachable, note it in `notes.md` and carry on; never block on Jira.
11. **Hand off.** Name the skill you are now following and its first action, then follow that skill.

## Output
- A decision stated in one or two sentences: the entry point or current status, the next skill, and which human gate (if any) is next.
- A created or updated `item.yaml` when one was missing or the status moved; amendments logged in `notes.md`.

## Definition of done
- You read AGENTS.md and the policies, and found or created the correct work item (or justified the chore exemption against all five criteria).
- The next skill is named and matches the status table, and the human gate ahead is known.
- `item.yaml` is consistent with reality (status, branch, `pr`), and nothing was advanced past an approval it lacks.

## Never
- Never run `factory approve`, write `approvals:` entries, or tell the human an artifact is approved when they did not say so. Finish the artifact, then ask the human to approve it.
- Never start implementing before the required approvals are in `item.yaml` (both under `supervised`; spec only for a `trusted` `risk: low` item), or skip `factory-test` before `implementing`.
- Never make any step depend on the CLI being installed; every CLI action has a by-hand equivalent.
- Never classify as an exempt chore to avoid writing a spec.
- Never leave an invalidated spec or plan in place while coding on; amend it and ask for re-approval.
