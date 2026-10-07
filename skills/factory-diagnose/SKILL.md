---
name: factory-diagnose
description: Use when a defect must be investigated before it is fixed - a bug report, failing behaviour, production incident, or security finding - and the work item is type bug at status draft with no root cause yet. Reproduces first, finds the root cause, assesses blast radius, and writes spec.md from the bug template. Do not use for new features (factory-spec), for a bug whose approved spec.md already has a root cause (go to factory-plan), or to guess a fix without a reproduction.
---

# factory-diagnose

## When to use

- A bug entry point: `item.yaml` has `type: bug`, `status: draft`, and `spec.md` is empty or still the template.
- Variants handled here: ordinary bug, **production incident** (users impacted now), **security finding** (see the dedicated steps).
- After the human approves `spec.md` the flow continues at factory-plan. A small bug may get a five-line plan.

## Inputs

- The report: Jira issue, user message, stack trace, logs, screenshots. Treat all of it as evidence to verify, not as truth.
- `docs/work/<id>-<slug>/item.yaml` (risk, branch `fix/<id>-<slug>`), `spec.md` (from `.factory/templates/work/spec.bug.md`), `notes.md`.
- Repo history: `git log`, `git blame`, `git bisect`; logs/monitoring the human can give you.
- `.factory/policies/production.md` and `.factory/policies/security.md`.

## Steps

1. **Triage the kind.** Production impact now? Go to step 2. Possible vulnerability? Do step 3 in addition. Otherwise start at step 4.
2. **Production incident: mitigate first, with a human decision.** Propose the fastest safe mitigation (roll back the last deploy, disable a feature flag, change config, scale, block traffic) with its side effects and how to undo it. Ask the human to choose and execute or authorise it; log the decision with a timestamp in `notes.md`. Only then diagnose. Mitigation is not the fix: the work item stays open.
3. **Security finding: validate quietly.** Confirm exploitability with the least invasive proof (a local test, never against production data or third-party systems). Assess impact (what data/actions, who can trigger it, preconditions) and rate risk. Keep exploit details out of public PR titles, branch names, commit messages and public comments; use neutral wording ("input validation fix"). Put details in `notes.md` only if the repo is private, else give them to the human out of band. Check whether secrets leaked and need rotation; tell the human.
4. **Reproduce FIRST.** Write a failing automated test in the project's framework (preferred) or a minimal script that shows the bug. Record exact environment, commit, inputs and the failing output. Try honestly: vary inputs, versions, data, config. If you cannot reproduce after real effort, STOP: write under Repro what you tried and ask the human for specific data (logs, input, version, timing). Do not guess a fix and do not "fix" what you cannot see.
5. **Find the root cause, not the symptom.** Narrow with: reading the failing path, targeted logging/debugger, `git log -S<symbol>`/`git blame` on suspect lines, and `git bisect run <repro-command>` when a good commit exists. Keep asking "why" until the answer is a faulty assumption or logic you can point at (`file:line`). Test your theory: change the suspected line locally, confirm the repro passes, revert. Note what you ruled out. A fix that only hides the symptom (a catch-all, a retry, a null guard far from the source) is not a root cause.
6. **Assess blast radius.**
   - Grep for other callers and sibling code with the same pattern; list them.
   - Which other inputs/states hit the same defect?
   - Is data already wrong (corrupted rows, bad emails sent, wrong totals)? Describe how to find and repair it; if large, create a follow-up work item rather than widening this one.
   - Since when, and who is affected (from `git blame` date, release history).
7. **Write `spec.md`** from `.factory/templates/work/spec.bug.md`, replacing every placeholder: Repro (steps plus the automated repro path and command), Expected, Actual, Root cause with `file:line` evidence, Blast radius, Regression criterion, Fix constraints, Risks. Set the Risk in the header consistent with `item.yaml › risk` (raise it if blast radius or data impact warrants; edit `item.yaml` by hand).
8. **Regression criterion = AC1.** AC1 names the failing test from step 4 that must pass after the fix and fails on current code. Add AC2+ only for neighbouring behaviour found in blast radius that the fix must also cover or preserve. Each AC must be testable as written (factory-test will check).
9. **Open questions.** Anything only a human can answer: leave the NEEDS CLARIFICATION marker (square brackets, see factory-spec) next to it. Remove every marker once answered; approval is blocked while one remains. A choice that belongs to the owner (accept a risk, fix now or park it) is a decision record in `docs/decisions/` (`factory decision new "<title>" --type design|other --jira <KEY>`), not a question left only in chat; never run `factory decide`.
10. **Hand off.** Commit nothing that changes behaviour in this phase except the repro test (it is expected to fail until the fix). Ask the human to review and approve `spec.md`. Then the flow continues at factory-plan.

## Output

- `docs/work/<id>-<slug>/spec.md` filled from the bug template, with the failing repro test committed on the `fix/<id>-<slug>` branch or described precisely.
- `docs/work/<id>-<slug>/notes.md`: mitigation decisions (incident), what was ruled out, bisect result, follow-up items.
- A short message: root cause in one sentence, blast radius, risk, and a request for the human to approve spec.md.

## Definition of done
- The template's `<!-- factory:unfilled ... -->` line is deleted from `spec.md`. It marks a scaffold, and approval and verify refuse the file while it is present. Delete it only when every section is really written.

- The bug is reproduced by an automated test or script, or the spec states plainly it is not reproduced and lists the data requested (then the item stays `draft`).
- Root cause has `file:line` and evidence, and a symptom-only explanation was rejected.
- Blast radius covers callers, other triggers and data impact.
- AC1 is the regression criterion; no template placeholder and no NEEDS CLARIFICATION marker remains in spec.md.
- For an incident: the mitigation decision and time are recorded. For a security finding: exploit details are not in public text.

## Never

- Never propose or write a fix before reproducing, and never claim a root cause without evidence.
- Never run `factory approve`; finish spec.md, then ask the human to approve it.
- Never roll back, redeploy, change production config or touch production data yourself; propose it and let the human decide.
- Never put exploit details, secrets or customer data in public PR text, commit messages or issue comments.
- Never widen scope: unrelated defects found on the way become new work items.
