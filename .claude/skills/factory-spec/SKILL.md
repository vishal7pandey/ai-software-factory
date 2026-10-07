---
name: factory-spec
description: Use when a feature, enhancement or refactor idea exists and the work item has no approved spec yet (status draft), so you must turn the idea into docs/work/<id>-<slug>/spec.md with numbered requirements and testable acceptance criteria. Not for bugs (use factory-diagnose, which writes the bug spec), not for planning the implementation (factory-plan), and not once the spec is approved unless new information forces an amendment.
---

# factory-spec — idea to approvable spec

## When to use
- Work item exists with `status: draft`, `type: feature` (refactors too, see below), and `spec.md` is missing, empty or still the template.
- A human asked you to revise a spec after review comments, or an approved spec must be amended because later work disproved it (graph rule in `factory-workflow`).
- Not for bugs: `factory-diagnose` produces the bug spec. Not for design: how to build it belongs in `plan.md`.

## Inputs
- `docs/work/<id>-<slug>/item.yaml` (risk, jira, title) and `notes.md` if present.
- The human's request, plus the Jira issue text if `jira` is set and Jira tools are available.
- The repo: `README`, `docs/`, `AGENTS.md`, existing code and tests in the area, prior `docs/work/*/spec.md` that touch the same area.
- `.factory/policies/security.md` (for the non-functional section).
- Template structure: Problem, Users and context, Goals and non-goals, Requirements, Acceptance criteria, Edge cases and failure modes, Non-functional requirements, Assumptions, Risks and dependencies, Open questions. Header line: `Status: draft · Risk: <risk> · Jira: <key or null>`.

## Steps
1. **Ground yourself before asking anything.** Find where the feature would live: read the related modules, tests, docs and earlier specs. Note what already exists, what conventions apply, and what the change would touch. A question you could have answered by reading the repo is a wasted human turn.
2. **Decide what you must ask.** List every unknown, then sort: (a) changes scope, cost, risk or user-visible behaviour: ask; (b) has an obvious default consistent with the repo: assume and record it under Assumptions; (c) cannot be answered by anyone yet: mark it. Ask at most 3-5 questions, in one message, each with your recommended answer and the consequence of each option. If the human is not available, continue with your recommendations as assumptions and mark the blocking ones. A choice that belongs to the owner and outlives this item (a design direction, a scope or definition-of-done call) is not asked only in chat: open a decision record, `factory decision new "<title>" --type design|other --jira <KEY>` (or copy `docs/decisions/TEMPLATE.md`), with options and your recommendation; the owner answers it, and `factory status` lists it as waiting. Never run `factory decide` yourself.

3. **Mark genuine unknowns** inline where they matter with the marker: `[NEEDS CLARIFICATION: <the specific question>]` (square brackets, exact text). Approval is blocked while any marker remains anywhere in the file, so every one must be answered, or converted to a stated assumption after the human agrees, before handover. Do not use the marker to avoid thinking.
4. **Write `spec.md`** from the template structure. Start with `# <id> — <title>` and the status header line.
   - Problem: who is hurt, when, cost today. No solution language.
   - Requirements `R1…`: one behaviour each, "The system …", consistent must/should.
   - Acceptance criteria `AC1…`: each cites the requirement(s) it proves; every R has at least one AC; at least one failure-path AC.
   - Non-goals: at least the things a reasonable reader might assume are included.
   - Edge cases: empty/duplicate/oversized input, concurrency, partial failure, permissions, third-party outage, with expected behaviour.
   - Non-functional: only what applies, each with a number or a policy reference.
   - Risks: justify the `risk` value. If you think `item.yaml` risk is wrong (money, auth, personal data, irreversible migration means high), say so and propose the new value to the human.
5. **Refactors.** Spec = goal, constraints, risk assessment, and ACs of the form "given X, behaviour is identical (pinned by test T)". Name the tests that already pin behaviour, or add an AC to write characterisation tests first.
6. **Quality bar for an AC.** It is good if all hold: (1) a person who did not write the code can run it; (2) it states concrete inputs and an observable result (status code, message, row, file, screen text, metric); (3) it has one pass/fail outcome; (4) it avoids vague words ("fast", "robust", "user-friendly", "properly"): replace with a number or behaviour; (5) it does not name an implementation (class, table) unless that is the requirement.
7. **Self-review before handover.** Check each and fix: no template comments left; no marker left; every R has an AC; every AC is testable; failure paths covered; non-goals present; assumptions listed; nothing in the spec is a design decision in disguise; spec contradicts neither `AGENTS.md` nor policies; a stranger could read it cold.
8. **Hand over.** Leave `status: draft`. Commit the spec on the item branch (conventional message, e.g. `docs(F-001): add spec`). Post a 5-line summary: the problem, the ACs count, key assumptions, residual risks, and the question list if any. Then ask the human to review and approve the spec, and stop. Do not start planning. If Jira sync applies, comment as `factory-workflow` says.
9. **After review comments:** amend in place, answer each comment in `notes.md` or the reply, and ask for approval again. If the spec was already approved, the human must re-approve the amended text.

## Output
- `docs/work/<id>-<slug>/spec.md`, complete, no template comments, no unresolved marker.
- Assumptions and any risk-level proposal visible in the file and in your handover message.
- `item.yaml` unchanged (`status: draft`); approval requested from the human.

## Definition of done
- The template's `<!-- factory:unfilled ... -->` line is deleted from `spec.md`. It marks a scaffold, and approval and verify refuse the file while it is present. Delete it only when every section is really written.
- Every requirement maps to at least one numbered, testable acceptance criterion, including a failure path.
- Non-goals, edge cases, assumptions and risks are written, not implied.
- Zero NEEDS CLARIFICATION markers left in the file (so approval is not blocked).
- The self-review checklist passed and the spec is committed.
- The human has been asked to approve, and you have stopped.

## Never
- Never run `factory approve` or edit `approvals:` in `item.yaml`. Finish the spec, then ask the human to approve it.
- Never decide a scope-changing question silently; ask or mark it.
- Never bury design, file names or task lists in the spec; that is `factory-plan`.
- Never write an acceptance criterion you cannot imagine a test for.
- Never start planning or coding on an unapproved spec.
