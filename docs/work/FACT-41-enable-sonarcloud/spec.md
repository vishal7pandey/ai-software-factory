# FACT-41 — Enable SonarCloud

Status: draft · Risk: low · Jira: FACT-41
Created: 2026-10-06 · Slug: enable-sonarcloud

## Problem

FACT-35 shipped the SonarCloud kit (workflow, properties, guard, doctor lines, how-to) and adopted it
in this repository, but the factory repo itself has never been analysed: its `sonar-project.properties`
held the `REPLACE_ME` organisation placeholder, so the guard skipped every scan, and the generic
"adapt to your project" test step of the workflow was never run against this repo's own tests. FACT-35's
last two acceptance criteria (first real analysis, one Sonar issue through the findings loop) therefore
stayed open. The owner has now supplied the organisation key and the `SONAR_TOKEN` Actions secret.

## Users and context

* **The owner**: wants the factory repo analysed on SonarCloud like any adopted project, as the
  dogfood proof that the FACT-35 kit works end to end.
* **The coding agent**: pulls Sonar issues through its SonarQube tools into the findings loop
  (`skills/factory-findings/SKILL.md`).

Read to ground this: `docs/sonarcloud.md`, `.github/workflows/sonar.yml`, `sonar-project.properties`,
`.github/workflows/ci.yml` (the CI installs with uv and runs the suite with pytest), FACT-35 (work item
and Jira comments).

## Goals and non-goals

**Goals**
- The factory repo's Sonar job really scans (guard no longer skips) with this repo's own test
  command and a coverage report in the path the properties file names.
- The first analysis, gate status and issue count are recorded; one real issue (if any) goes through
  the findings loop; the SonarQube MCP connectivity is established.

**Non-goals**
- Making the quality gate a required check or making the job wait for the gate (human decision per
  project, `docs/sonarcloud.md`).
- Changing the kit templates under `kit/sonar/` (the generic template stays as FACT-35 left it).
- Touching the token or any `.env`; adopting ade and chatpid (separate work).

## Requirements

- R1. `sonar-project.properties` carries the real organisation key and the project key
  `vishal7pandey_ai-software-factory`, with no `REPLACE_ME` left.
- R2. The workflow's test step runs this repo's own pytest command under coverage and writes the XML
  at the path `sonar.python.coverage.reportPaths` names; the Python version of the job equals
  `sonar.python.version`; generated reports are not committed.
- R3. On a pull request from this repository the guard enables the scan and the scanner runs.
- R4. After merge the project exists in the SonarCloud organisation; its first analysis, quality
  gate status and open issue count are recorded on FACT-41 and FACT-35.
- R5. If the first analysis has at least one real issue, one of them goes through the findings loop
  and is closed only on SonarCloud's word; otherwise this is recorded as not applicable.
- R6. Whether the agent's SonarQube MCP server sees the organisation is established and recorded.

## Acceptance criteria

- AC1. (R1) `sonar-project.properties` has `sonar.organization` set to a non-placeholder value and
  `sonar.projectKey=vishal7pandey_ai-software-factory`; the guard's `REPLACE_ME` grep finds nothing in it.
- AC2. (R2, R3) On the PR, the `sonar` job's guard step reports enabled, the test step runs
  `python -m pytest` with coverage XML at `coverage.xml`, and the SonarCloud scan step runs and
  succeeds; a workflow edited to write the XML elsewhere or to use another Python version fails
  the repository test that pins these.
- AC3. (R4) After merge, the public SonarCloud API lists the project in the organisation (project
  count 1), returns a quality gate status for it, and an issue search returns a count; all three are
  recorded on FACT-41 and FACT-35.
- AC4. (R5) With N >= 1 open issues: one Jira Bug labelled `finding-sonar-<issue key>` carries the
  fix through the bug path with a regression test, and is Done only when the SonarCloud API shows
  that issue CLOSED/resolved after a new analysis, with nothing dismissed. With N = 0: recorded as
  not applicable. FACT-35 moves to Done only when this and AC5 hold.
- AC5. (R6) The result of the `mcp__sonarqube__projects` call (project count, whether the
  organisation's project is listed) is recorded; if the tool does not see the organisation, the
  reason and the owner action are recorded and the ticket stays open.

## Edge cases and failure modes

- SonarCloud refuses the scan (project key mismatch, Automatic Analysis enabled, project not
  imported): the job log's exact reason is recorded; if it needs the owner (UI switch), work stops there.
- Fork PRs get no secret: the guard skips (unchanged kit behaviour).
- The SonarQube MCP server is bound to another instance or a different token: AC5 is then a
  recorded negative, not a failure of the scan.

## Non-functional requirements

- Security: the token is never printed, read or logged; the workflow keeps `permissions` read-only
  (`policies/security.md`). Public SonarCloud API reads are made without a token.

## Assumptions

- The CI test step may depend on `uv run --with pytest-cov` (no change to `pyproject.toml`, no new
  lock entry); coverage is measured on `src/swfactory` with branch coverage.
- The default branch is analysed on push to `main` and PRs are analysed as pull requests.

## Risks and dependencies

Risk low: one workflow line, one properties line, a test and docs; reversible by revert. Depends on
the owner's SonarCloud organisation and secret (done) and, possibly, on Automatic Analysis being off
for the new project.
