# FACT-21 — Teach agents the file-editing hazards

Status: in-review · Risk: low · Jira: FACT-21
Created: 2026-10-05 · Slug: teach-agents-the-file-editing-hazards

## Problem

Coding agents that rewrite files through inline scripts (a Python heredoc, `sed`, `awk`) in a shell tool
have repeatedly corrupted files: backslash escapes are lost or changed (`\n` became a real newline, `\b` became
an invisible backspace character that `grep` and the file viewer did not show). Agents also stage changes with
`git add -A`, which sweeps an unrelated uncommitted change into a commit. Both happened more than once in real
projects, and nothing in the method says how to avoid them.

## Users and context

Any agent following the `factory-implement` skill (`skills/factory-implement/SKILL.md`), in any adopted project.
The factory's lint (`src/swfactory/checks.py`, `lint_skills`) enforces the mechanical shape of skills.

## Goals and non-goals

**Goals**
- `factory-implement` tells the agent to use the editor tools for edits and never rewrite files with inline scripts,
  to re-read changed lines after any scripted edit, and to stage explicit paths.
- `factory lint` fails if `factory-implement` stops carrying both rules, so they cannot be edited out silently.
- The repo's own managed copies are synced, so adopted projects get the wording on their next `factory sync`.

**Non-goals**
- Detecting corrupted files automatically, or blocking `git add -A` with a hook.
- Syncing other repositories (each project runs `factory sync` itself).
- Rules for other skills.

## Requirements

- R1. `skills/factory-implement/SKILL.md` states, in generic wording, that files are changed with the editor tools,
  that files are never rewritten through inline scripts, and that changed lines are re-read after any scripted edit.
- R2. The same skill states that changes are staged by explicit path and that `git add -A` (and `git add .`) is not used.
- R3. `factory lint` fails when `factory-implement` lacks the inline-script rule or the explicit-staging rule.
- R4. The repo's managed copies of the skill (`.claude/skills`, `.github/skills`) match `skills/` (`factory sync --check` passes).
- R5. The wording is generic: no machine, project or person names.

## Acceptance criteria

- AC1. (R1, R2, R5) `skills/factory-implement/SKILL.md` contains the file-editing rule (editor tools; no inline
  scripts; re-read after a scripted edit) and the staging rule (explicit paths; not `git add -A`), and still
  passes the skill lint (<= 150 lines, section order).
- AC2. (R3) Linting a `factory-implement` skill that lacks the inline-script rule fails, naming the missing rule;
  likewise for a skill lacking the staging rule; the real skill passes. Other skills are not subject to the rule.
- AC3. (R4) After `factory sync .`, `factory sync --check .` exits 0 and the managed copies are byte-identical to the source.
- AC4. (R5) `factory lint` passes on the repo, including the generic-content rules.
