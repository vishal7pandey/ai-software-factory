---
# The project charter. The owner approves it through a decision record (type charter):
#   factory decision new "Approve the project charter" --type charter
# then name that record in `decision:` below; the owner answers with `factory decide`.
# An agent never approves it. Editing this file after approval needs a new charter decision.
purpose: "REPLACE_ME: two sentences. What this project is for, and for whom."
mode: active   # active | maintenance (maintenance: see the section below)
decision: null   # D-<n> of the charter decision record that approves this file
done:   # 3 to 7 measurable criteria. Each needs exactly one checkable reference:
  #   check: {work: <work item id>}                    met when that item is merged or later
  #   check: {file: <path in the project>}             met when the file exists
  #   check: {metric: {file: <path>, key: a.b, min: 0.9}}   min, max or equals; a YAML or JSON file
  #   check: {jira: <KEY>}                             met when the ticket is Done
  - id: C1
    text: "REPLACE_ME: one outcome someone else can verify"
    check: {work: REPLACE_ME}
non_goals:   # what a reasonable reader might assume is included, but is not
  - "REPLACE_ME: a thing this project will not do"
parked: []   # deliberately not pursued: [{item: "a thing", jira: KEY-1}] (label the ticket `parked`)
---
# Project charter

<!-- factory:unfilled - delete this line when the charter is really written; `factory decide` refuses it -->

Write the purpose, done criteria, non-goals and parked list in the front matter above. Avoid words that
cannot be checked ("works well", "user-friendly", "robust"): a criterion is a fact a reference can show.

## Maintenance mode

When every done criterion is met the project enters maintenance mode (`mode: maintenance`, approved through a new
charter decision). In maintenance mode only security and dependency updates are made, through the findings and
dependency loops (`factory-findings`, `factory-dependencies`). Any other change needs a charter amendment: a new
charter decision the owner accepts. `factory feature start` warns, but does not block, so the owner can proceed
deliberately.
