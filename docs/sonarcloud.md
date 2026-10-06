# SonarCloud for an adopted project

SonarCloud (https://sonarcloud.io, the hosted SonarQube; SonarSource may brand it "SonarQube Cloud") is
free for public repositories. The kit lays the CI half; you do the SonarCloud half once. Until you do,
the workflow is inert: it skips with a notice and never fails a build. Nothing below needs the factory
to see a token, and none of it should ever be pasted into a chat, a ticket, a PR or a commit.

## What `factory adopt` lays down (python and node projects)

| file | purpose |
|---|---|
| `.github/workflows/sonar.yml` | scans on push to the default branch and on pull requests from the same repository (fork PRs are skipped); `fetch-depth: 0`; `SonarSource/sonarqube-scan-action` pinned to a major; token from the `SONAR_TOKEN` Actions secret |
| `sonar-project.properties` | organisation key, project key, sources, test globs and the coverage report path (`coverage.xml` for python, `coverage/lcov.info` for node) |

Both are create-mode files: written once, never overwritten by `factory sync`, yours to edit. The project
key is `<owner>_<repo>`, filled in from the GitHub `origin` remote. The organisation key is not knowable
by `adopt`, so it is the marked placeholder `REPLACE_ME_SONAR_ORGANIZATION`. The workflow's first step
(the guard) skips the scan, exits 0 and writes a notice in the run summary when any of these hold: the
`SONAR_TOKEN` secret is empty (fork or Dependabot pull request, or not set up yet), the properties file is
missing, or a non-comment line still contains `REPLACE_ME`. A project on another stack, or one adopted
before this existed, can copy the files from `kit/sonar/` in the factory repository.

## Once per owner: the organisation

1. Sign in at https://sonarcloud.io with your GitHub account.
2. Create (or reuse) an organization, importing it from your GitHub account or organisation. Its
   **key** is shown in the URL (`https://sonarcloud.io/organizations/<key>/...`) and in the
   organization settings. The key is not a secret.

## Once per repository

1. In SonarCloud choose **Analyze new project** and import the repository. The project key proposed
   there should equal the `sonar.projectKey` the kit wrote (`<owner>_<repo>`); if it differs, change
   whichever side you prefer, but keep them equal.
2. Open the project, **Administration > Analysis Method**, and turn **Automatic Analysis** off. The
   CI-based scan is the one with coverage; with Automatic Analysis on, the CI scan fails with a
   "you are running CI analysis while Automatic Analysis is enabled" error.
3. In the repository, edit `sonar-project.properties`: replace `REPLACE_ME_SONAR_ORGANIZATION` with
   the organisation key; commit.
4. Generate a token: **My Account > Security > Generate Tokens**. Copy it once.
5. Store it as the repository Actions secret. You run this yourself, at the prompt (the value is typed
   or pasted into the terminal prompt, not into the command line, so it stays out of shell history):

   ```
   gh secret set SONAR_TOKEN -R <owner>/<repo>
   ```

   A fork cannot use the secret and an organisation-level secret is not listed per repository by
   `factory doctor`; set it per repository.
6. Optional: a repository variable `SONAR_HOST_URL` overrides the server; unset, it is
   `https://sonarcloud.io`.

## Check it

```
factory doctor <project>
```

prints `sonar: properties` (does the file still hold `REPLACE_ME`?) and `sonar: SONAR_TOKEN` (is the secret
set: the name only, its value is never read or printed; `unknown` when `gh` is not logged in or lacks
rights). These lines never make `doctor` fail; a project that has not started setup gets a notice, not a
warning. Then push a branch: the **sonarcloud** job should run the scan instead of skipping it, and the
analysis appears in SonarCloud.

## Quality gate

SonarCloud reports the gate result on the pull request once the project is bound to the GitHub
repository. Whether it blocks merging is a per-project human decision (branch protection: require the
SonarCloud status or the `sonarcloud` job). To make the job itself fail on a failed gate, add to the scan
step of `sonar.yml`:

```
        with:
          args: -Dsonar.qualitygate.wait=true
```

## Local scan (when CI cannot reach SonarCloud)

Generate the coverage report first (python: `uv run --with pytest-cov python -m pytest --cov
--cov-report=xml:coverage.xml`; node: `npm test -- --coverage`), then run the scanner with the token in
the environment, never on the command line:

```
export SONAR_TOKEN=...          # from your password manager; do not paste it anywhere shared
sonar-scanner -Dsonar.host.url=https://sonarcloud.io
# or, without installing it:
docker run --rm -e SONAR_TOKEN -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli -Dsonar.host.url=https://sonarcloud.io
```

The scanner reads `sonar-project.properties`; results land in the same SonarCloud project.

## Findings

Once the project is analysed, the agent pulls issues through its SonarQube tools and runs them through
the findings loop (`factory-findings`, `policies/findings.md`). Nothing about that changes here.
