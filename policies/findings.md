# Findings policy

Rules for security and quality findings raised by scanners: code scanning (CodeQL or any tool that uploads
results), Dependabot, secret scanning, and SonarQube where a project exists. The procedure is the skill
`factory-findings`; the rules below are what it must not drift from.

## Closure rule

* A finding is tracked as one Jira Bug (labels in the skill). That issue goes to Done **only** when the scanner
  confirms the finding is gone: the alert, re-queried, has `state` = `fixed` (code scanning, Dependabot), or the
  SonarQube issue is closed by a new analysis. A merged PR, a green build or "the code looks fixed" is not
  confirmation: the scanner has to say it.
* A secret-scanning alert has no `fixed` state. It is closed only when a human confirms the secret was revoked
  (rotated) and the alert is `resolved` with resolution `revoked`. Removing it from the code does not close it.
* An alert that is still `open` never allows Done, whatever else is true. Cite the re-queried state in the
  closing Jira comment (alert URL, state, date).
* A closed finding whose alert is `open` again is reopened (the same issue), never filed a second time.

## Dismissal gate

* A dismissal (false positive, won't fix, used in tests) is a security exception. The agent only **proposes** it:
  alert URL, the reason below, and a sentence of evidence. The human says yes in words; only then does the agent
  apply it, and records the reason, the approver and the date on the Jira issue.
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
  most 10 issues in one run. Every later run also files at most 10 new issues.
* Order: secret-scanning alerts first, then by severity: `critical`, `high`, `medium`, `low` (code scanning:
  `rule.security_severity_level`, falling back to `rule.severity` where `error` counts as high, `warning` as
  medium and `note` as low; Dependabot: `security_advisory.severity`).
* The rest is reported to the human as counts per severity, never as an issue per alert. The human decides what
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
