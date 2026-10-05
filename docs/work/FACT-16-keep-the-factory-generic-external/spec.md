# FACT-16 — Keep the factory generic: external project registry

Status: in-review · Risk: low · Jira: FACT-16
Created: 2026-10-04 · Slug: keep-the-factory-generic-external

## Problem

The factory is a generic, public tool, but its repo contains instance data: `registry/projects.yaml` lists the maintainer's own projects with their repo URLs and Jira/Confluence keys, docs examples use a real person's name and a deleted Jira key, and test fixtures use real project names. Anyone who clones the factory gets someone else's setup, and every `factory adopt` rewrites a committed file inside the tool's own repository.

## Users and context

The factory maintainer (single user) and any agent running `factory adopt` or `factory project`. Today the registry is `registry/projects.yaml` (committed) plus `registry/local.yaml` (gitignored, machine paths), both resolved from the factory repo root by `common.registry_path()` and `common.local_registry_path()` and used by the registry functions in `installer.py` and the `project list|add|remove` commands. Nothing else reads it.

## Goals and non-goals

**Goals:** no instance data in the factory repo; the registry stays available as an external file; one file instead of two.

**Non-goals:** syncing the registry anywhere (Jira, Confluence and GitHub remain the shared record); changing the fields of a project entry; removing the `project` commands; migrating old data automatically.

## Requirements

- R1. The registry lives outside the factory repo: the path comes from the environment variable `FACTORY_REGISTRY`, otherwise `~/.factory/registry.yaml`.
- R2. One file holds both project facts and local paths: top-level keys `projects` (a list, same fields as today) and `paths` (project name to absolute path). There is no `registry/` directory and no `local.yaml` in the repo.
- R3. `factory adopt` and `factory project add|remove|list` read and write that file. The file and its parent directory are created on first write.
- R4. When the file does not exist, `project list` prints one line saying there is no registry yet and exits 0. Nothing else fails because the file is missing.
- R5. The repo ships `docs/registry.example.yaml` with neutral placeholder entries, and ARCHITECTURE.md (section 3.6 and the repository tree) and `docs/jira-workflow.md` describe R1 and R2.
- R6. Examples in docs and fixtures in tests use neutral names (person `Jane Doe`, key `PROJ-123`, projects such as `sample-app`).
- R7. `factory lint` fails if the repo contains a `registry/` directory, or if a file under `docs/` (except `docs/work/`), `kit/`, `skills/`, `policies/` or `templates/` contains an `atlassian.net` hostname.

## Acceptance criteria

- AC1. With `FACTORY_REGISTRY` set to a temp path, `adopt` creates the file with matching `projects` and `paths` entries; `project list` shows the entry; `project remove` removes both the entry and its path.
- AC2. With no environment variable and no file, `project list` exits 0 with the "no registry yet" message; after `adopt`, the file exists at `~/.factory/registry.yaml` (home directory redirected in the test).
- AC3. The repository has no `registry/` directory, and `.gitignore` no longer mentions `registry/local.yaml`.
- AC4. `factory lint` passes on the repo and fails on fixtures that contain a `registry/` directory or an `atlassian.net` hostname in a skill.
- AC5. A search of the tracked files for the maintainer's name, the former Jira key and the real project names finds hits only in the factory's own adoption files (`.factory/`, `.claude/`, `.github/`), `docs/work/`, `LICENSE` (copyright holder) and the lint rule's own hostname literal and tests (amended, see notes.md).
- AC6. All existing tests pass, updated for the new location, on Windows and Linux (CI).

## Edge cases and failure modes

- Registry at the old location: it is not read. The maintainer copies the values into the new file once by hand (noted on FACT-16).
- Unwritable home directory or a bad `FACTORY_REGISTRY` path: the kit is still installed, and the registry failure is reported as an error with the path (exit 1), with no traceback.
- A relative `FACTORY_REGISTRY` is resolved against the current directory.
- Two commands writing at once: not handled (single user).

## Non-functional requirements

No new dependency (stdlib and PyYAML only). LF newlines. Identical behaviour on Windows and Linux.

## Assumptions

- A1. The maintainer is the only user of the registry, so no compatibility shim for the old location is needed (decision recorded on FACT-16: "we can have a registry, but it has to be external to the factory").
- A2. `~/.factory/registry.yaml` is an acceptable default; the environment variable lets someone put the file elsewhere, for example next to their projects.
- A3. The factory's own self-adoption config (`.factory/factory.yaml`, Jira key FACT) may name the factory as a project: it is the factory acting as an ordinary adopted project, not instance data built into the tool.

## Risks and dependencies

- Low risk: only `adopt` and the `project` commands touch the registry.
- The old committed registry content leaves the working tree (it stays in git history) and is copied by hand to the new location.
- The pull request depends on FACT-9 only because the `verify` workflow exists on that branch; this work is stacked on it.

## Open questions

None.
