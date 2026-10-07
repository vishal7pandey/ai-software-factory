# Findings policy

Rules for security and quality findings raised by scanners: code scanning (CodeQL or any tool that uploads
results), Dependabot, secret scanning, and SonarQube where a project exists. The procedure is the skill
`factory-findings`; the rules below are what it must not drift from.

## Closure rule

* A finding (one alert) is tracked on one Jira Bug (labels in the skill); a Bug may carry several alerts when they
  are grouped (see Grouping). That issue goes to Done **only** when the scanner confirms every finding it carries
  is gone: each alert, re-queried, has `state` = `fixed` (code scanning, Dependabot), or the SonarQube issue is
  closed by a new analysis. A merged PR, a green build or "the code looks fixed" is not confirmation: the scanner
  has to say it.
* A grouped issue goes to Done only when all of its alerts are settled: every alert re-queried as `fixed`
  (secrets: revoked), or dismissed under an `accepted` dismissal record cited on the issue. One alert still `open`, or
  `dismissed` without an accepted record, anywhere in the group blocks Done.
* A secret-scanning alert has no `fixed` state. It is closed only when a human confirms the secret was revoked
  (rotated) and the alert is `resolved` with resolution `revoked`. Removing it from the code does not close it.
* An alert that is still `open` never allows Done, whatever else is true. Cite the re-queried state in the
  closing Jira comment (alert URL, state, date).
* A closed finding whose alert is `open` again is reopened (the same issue, the one that carries its label),
  never filed a second time.

## Grouping

Grouping is the default: one Jira issue is the unit of work, and one upgrade or one fix pattern is one unit.

* One issue may carry several `finding-<source>-<id>` labels when the alerts are (a) the same Dependabot package in
  the same manifest file, or (b) the same code-scanning rule in the same file or the same module. Same module means
  the same directory: the part of the file path before the last `/` (the repo root is one directory, `./`), not
  subdirectories. A file is in its own directory, so one rule covers same file and same module.
* Secret-scanning alerts and SonarQube issues are never grouped: one issue per alert. A code-scanning alert without a
  file path is not grouped either.
* Every alert keeps its own label and its own re-query. Grouping changes how many issues there are, never the closure
  rule above.
* A group is found again by the issue summary: Dependabot `[<package>] <manifest path>`, code scanning
  `[<rule id>] <directory>/`. An open group is an issue labelled `finding`, not Done, whose summary equals that text.
* A new alert (no label in Jira yet) that fits an open group adds its label and a comment to that issue; it does not
  create an issue. A new alert that fits only a Done group is filed as a new issue; a Done group is not reopened for
  it. An alert that already has a label and is `open` again reopens the issue that carries it (closure rule).
* The group's priority is the highest severity among its alerts.
* Per-alert issues remain available when the human asks: file one issue per alert, with the per-alert summary (code
  scanning `[<rule id>] <path>:<line>`, Dependabot `[<package>] <manifest path> (alert <id>)`). They are never join
  targets.

## Dismissal gate

* A dismissal (false positive, won't fix, used in tests) is a security exception. The agent only **proposes** it,
  as a `dismissal` decision record in `docs/decisions/` (`factory decision new --type dismissal`): the alert URL,
  the reason below, a sentence of evidence, the dismissal as the recommended option. The owner answers with
  `factory decide`; an agent never runs it, and a dismissal is never delegated to an agent. The agent applies the
  dismissal **only when the record is `accepted`** (`status: accepted`, with `by` and `at`; `factory verify` fails
  an accepted record without them) and then records the record id, the reason, the approver and the date on the
  Jira issue. A `rejected` record means the finding is fixed instead. No accepted record, no call.
* Allowed reasons, exactly these three: `false positive`, `won't fix`, `used in tests`. Anything else is a
  fix, or a question for the human. Apply them with the nearest value the API accepts:

  | Reason | Code scanning (`dismissed_reason`) | Dependabot (`dismissed_reason`) | Secret scanning (`resolution`) |
  |---|---|---|---|
  | `false positive` | `false positive` | `inaccurate` | `false_positive` |
  | `won't fix` | `won't fix` | `tolerable_risk` | `wont_fix` |
  | `used in tests` | `used in tests` | `not_used` | `used_in_tests` |

  SonarQube: the agent's tools for false positive and won't fix, same gate.
* **Never dismiss a finding to make a check go green**, to clear a backlog, or because a fix is hard.
  An agent that cannot fix a finding says so and asks.
* A finding a human dismissed in the scanner's own UI is recorded on its Jira issue (who, reason) and not re-filed.

## Batch limits

* A first sweep (no issue with the label `finding` exists yet) files only `critical` and `high` findings, and at
  most 10 issues in one run. Every later run also files at most 10 new issues. The cap counts issues, not alerts:
  alerts that join a group, in the same run or an open one, do not use it up.
* Order: secret-scanning alerts first, then by severity: `critical`, `high`, `medium`, `low` (code scanning:
  `rule.security_severity_level`, falling back to `rule.severity` where `error` counts as high, `warning` as
  medium and `note` as low; Dependabot: `security_advisory.severity`).
* The rest is reported to the human as counts of alerts per severity, never as an issue per alert. Every report
  gives the numbers in alerts and in issues (alerts found, alerts filed, issues created). The human decides what
  to file next. Never file the whole backlog "to be safe".
* Secret values, tokens and keys never go into Jira, a PR or a prompt (`security.md`).

## Enabling the scanners by hand

`factory harden` does this where the factory version has it. Without it, as a repo admin with `gh`
(`gh auth status`; scope `repo`), in the repo directory (`{owner}` and `{repo}` are filled in by `gh`):

```bash
# CodeQL default setup (languages are detected; add -f "languages[]=python" to pin them)
gh api -X PATCH repos/{owner}/{repo}/code-scanning/default-setup -f state=configured -f query_suite=default
# Dependabot alerts and security updates
gh api -X PUT repos/{owner}/{repo}/vulnerability-alerts
gh api -X PUT repos/{owner}/{repo}/automated-security-fixes
# Secret scanning and push protection
gh api -X PATCH repos/{owner}/{repo} -f "security_and_analysis[secret_scanning][status]=enabled" -f "security_and_analysis[secret_scanning_push_protection][status]=enabled"
```

Check with `gh api repos/{owner}/{repo}/code-scanning/default-setup` (state `configured`) and
`gh api repos/{owner}/{repo} --jq .security_and_analysis`. Changing repo security settings is ASK FIRST
(`autonomy.md`). Private repositories may need a paid plan for code and secret scanning; say so rather than guess.
