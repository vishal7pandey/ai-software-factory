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
by `adopt`, so it is the marked placeholder `REPLACE_ME_SONAR_ORGANIZATION`.

When `adopt` or `sync` creates them they are fitted to the project (and print what they decided under
`result:`): the push trigger is the repository's default branch (origin/HEAD; `master` stays `master`),
the python test step is the project's own pytest command from its `ci.yml` (markers and `--deselect` lists
kept, coverage options added; a command that cannot be reused safely keeps the template step and says
why), and the python version of the job and of `sonar.python.version` follows the project's CI. The job
installs only from the lock: `uv sync --locked` and `uv run --locked --no-sync python -m pytest ...` (the
flags are left out when there is no `uv.lock`), so `pytest-cov` must be a locked dev dependency
(`uv add --dev pytest-cov`; `adopt` prints a note when it is missing). `astral-sh/setup-uv` and the scan
action are pinned to a commit SHA; Dependabot's github-actions updates keep the pins current. An already
existing file is never rewritten: to adopt a newer template, diff your file against `kit/sonar/` by hand.

The workflow's first step
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

## Two facts that cost real time

A green **sonarcloud** job is not a readable analysis. Both of these make the scan succeed in CI while the
results cannot be read (by the API, by the agent's SonarQube tools, or by anyone without the project):

1. **On the free plan the SonarCloud project must be public.** A CI scan of a private project succeeds, but
   nothing can be read: anonymous API calls answer 404 and the plan does not allow private analysis data.
   A project can be created private: make it public in the project's **Administration** settings (visibility).
2. **The SonarCloud project's main branch name must equal the repository's default branch.** A new project
   is created with the main branch `master`. If the repository's default branch is `main`, the push scans
   of `main` are stored as a short-lived side branch, and SonarCloud refuses to serve data for it on the
   free plan ("Organization is not allowed to access data from non main branches"). Repair, once, with a
   SonarCloud token of an organisation admin in `$SONAR_TOKEN` (from your password manager, never pasted
   anywhere shared). Replace `<owner>_<repo>` with `sonar.projectKey` and `main` with the default branch
   (`factory doctor` prints these lines with the real values filled in): first delete the empty side branch
   that the scans created, then rename the main branch to the default branch's name.

   ```
   curl -s -X POST -u "$SONAR_TOKEN:" "https://sonarcloud.io/api/project_branches/delete?project=<owner>_<repo>&branch=main"
   curl -s -X POST -u "$SONAR_TOKEN:" "https://sonarcloud.io/api/project_branches/rename?project=<owner>_<repo>&name=main"
   ```

   `project_branches/delete` answers 404 when there is no side branch of that name: skip it then. The next
   push to the default branch fills the renamed main branch.

## Check it

```
factory doctor <project>
```

prints `sonar: properties` (does the file still hold `REPLACE_ME`?), `sonar: SONAR_TOKEN` (is the secret
set: the name only, its value is never read or printed; `unknown` when `gh` is not logged in or lacks
rights) and `sonar: server`: read through the public SonarCloud API, no token, it says whether the project
exists and is public (anonymous access cannot tell a private project from a missing one) and whether its
main branch equals the repository's default branch (read from GitHub through `gh`); on a mismatch it prints
the two repair commands above with the real values. It makes no call while `REPLACE_ME` is still in the
properties or without a github.com remote, and says `unknown (...)` when anything cannot be read. These
lines never make `doctor` fail; a project that has not started setup gets a notice, not a warning. Then push
a branch: the **sonarcloud** job should run the scan instead of skipping it, and the analysis appears in
SonarCloud.

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

Generate the coverage report first (python, with `pytest-cov` in the locked dev group
(`uv add --dev pytest-cov`): `uv run --locked --no-sync python -m pytest --cov
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
