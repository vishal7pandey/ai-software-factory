"""The CI gate (docs/ARCHITECTURE.md section 3.3).

STANDALONE: stdlib + PyYAML only, and it must never import from `swfactory`. This file is copied
verbatim into adopted projects as `.factory/verify.py` and run with `python .factory/verify.py`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path

import yaml

STATUSES = [
    "draft",
    "spec-approved",
    "plan-approved",
    "implementing",
    "in-review",
    "merged",
    "released",
    "done",
]
TYPES = ["feature", "bug"]
RISKS = ["low", "medium", "high"]
AUTONOMY = ["supervised", "trusted"]

JIRA_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
ID_RE = re.compile(r"^(?:[FB]|[A-Z][A-Z0-9]+)-\d+$")
_DIR_ID_RE = re.compile(r"^((?:[FB]|[A-Z][A-Z0-9]+)-\d+)-")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BRANCH_RE = re.compile(r"^(?:feature|fix)/((?:[fb]|[a-z][a-z0-9]+)-\d+)-", re.IGNORECASE)

# A delegated approval (FACT-19): `by: "<who> (delegated to agent)"`, plus `delegated: true`.
DELEGATED_SUFFIX = " (delegated to agent)"


def is_delegated(record: object) -> bool:
    """True for an approval record written with `--delegated` or by hand in the same wording."""
    if not isinstance(record, dict):
        return False
    by = record.get("by")
    return record.get("delegated") is True or (
        isinstance(by, str) and by.endswith(DELEGATED_SUFFIX)
    )


# Order in which item.yaml keys are written (docs/ARCHITECTURE.md section 3.2).
ITEM_KEYS = [
    "id",
    "type",
    "title",
    "slug",
    "status",
    "risk",
    "jira",
    "branch",
    "created",
    "approvals",
    "pr",
]


# --- small helpers -----------------------------------------------------------------------------


def dir_id(dirname: str) -> str | None:
    """'PF-12-add-login' -> 'PF-12'; None if the name has no id prefix."""
    m = _DIR_ID_RE.match(dirname)
    return m.group(1) if m else None


def _norm_dates(obj):
    """YAML turns unquoted 2026-10-04 into a date; we want ISO strings everywhere."""
    if isinstance(obj, dt.date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _norm_dates(v) for k, v in obj.items()}
    return obj


def load_item(path: Path | str) -> dict:
    """Read an item.yaml (CRLF ok, dates normalised to str). ValueError if it is not a mapping."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        raise ValueError(f"not valid YAML: {str(e).splitlines()[0] if str(e) else e}") from e
    if not isinstance(data, dict):
        raise ValueError("item.yaml must be a YAML mapping")
    return _norm_dates(data)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


CLARIFY = "[NEEDS CLARIFICATION"
UNFILLED = "factory:unfilled"  # sentinel line in scaffolded templates; deleted once really written


def open_marker(text: str) -> str | None:
    """Return the marker that shows a work doc is not finished, or None."""
    for marker in (UNFILLED, CLARIFY):
        if marker in text:
            return marker
    return None


def _nonempty(path: Path) -> bool:
    return _read(path).strip() != ""


def _load_config(root: Path) -> dict:
    path = root / ".factory" / "factory.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        raise ValueError(f"factory.yaml is not valid YAML: {e}") from e
    return data if isinstance(data, dict) else {}


# --- the rules ---------------------------------------------------------------------------------


def required_approvals(item: dict, config: dict) -> list[str]:
    """THE autonomy rule. supervised: spec+plan. trusted: plan waived for risk 'low' only."""
    autonomy = config.get("autonomy", "supervised")
    if autonomy == "supervised":
        return ["spec", "plan"]
    if autonomy == "trusted":
        return ["spec"] if item.get("risk") == "low" else ["spec", "plan"]
    raise ValueError(f"unknown autonomy {autonomy!r} (expected supervised or trusted)")


def validate_item(item: dict, dirname: str) -> list[str]:
    """Schema check (rule 1). Returns a list of problems; empty means valid."""
    if not isinstance(item, dict):
        return ["item.yaml must be a YAML mapping"]
    problems: list[str] = []

    for key in ("id", "type", "title", "slug", "status", "risk", "created"):
        if item.get(key) in (None, ""):
            problems.append(f"missing required field '{key}'")

    iid = item.get("id")
    if iid not in (None, ""):
        if not isinstance(iid, str) or not ID_RE.match(iid):
            problems.append(f"id {iid!r} is not F-###, B-### or a Jira key")
        elif not dirname.startswith(f"{iid}-"):
            problems.append(f"id {iid!r} does not match directory name {dirname!r}")

    for key, allowed in (("type", TYPES), ("status", STATUSES), ("risk", RISKS)):
        val = item.get(key)
        if val not in (None, "") and val not in allowed:
            problems.append(f"{key} {val!r} is not one of {', '.join(allowed)}")

    for key in ("title", "slug"):
        val = item.get(key)
        if val not in (None, "") and not isinstance(val, str):
            problems.append(f"{key} must be a string")

    created = item.get("created")
    if created not in (None, "") and not (isinstance(created, str) and _DATE_RE.match(created)):
        problems.append(f"created {created!r} is not an ISO date (YYYY-MM-DD)")

    jira = item.get("jira")
    if jira is not None and not (isinstance(jira, str) and JIRA_RE.match(jira)):
        problems.append(f"jira {jira!r} is not a Jira key or null")

    for key in ("branch", "pr"):
        if item.get(key) is not None and not isinstance(item.get(key), str):
            problems.append(f"{key} must be a string or null")

    approvals = item.get("approvals")
    if approvals is None:
        approvals = {}
    if not isinstance(approvals, dict):
        problems.append("approvals must be a mapping")
    else:
        for kind, rec in approvals.items():
            if kind not in ("spec", "plan"):
                problems.append(f"approvals has unknown key {kind!r}")
            elif not (
                isinstance(rec, dict)
                and isinstance(rec.get("by"), str)
                and rec["by"].strip()
                and isinstance(rec.get("at"), str)
                and _DATE_RE.match(rec["at"])
            ):
                problems.append(f"approvals.{kind} must be {{by: <name>, at: YYYY-MM-DD}}")
            elif "delegated" in rec and not isinstance(rec["delegated"], bool):
                problems.append(f"approvals.{kind}.delegated must be true or false")
            elif rec.get("delegated") is True and not rec["by"].endswith(DELEGATED_SUFFIX):
                problems.append(
                    f"approvals.{kind} is delegated but 'by' does not end with '{DELEGATED_SUFFIX}'"
                )
    return problems


def _check_approvals_and_docs(item: dict, item_dir: Path, config: dict) -> list[str]:
    """Rule 2. Assumes the item already passed validate_item."""
    problems: list[str] = []
    idx = STATUSES.index(item["status"])
    required = required_approvals(item, config)
    approvals = item.get("approvals") or {}
    if idx >= STATUSES.index("spec-approved") and "spec" in required and "spec" not in approvals:
        problems.append(f"status is {item['status']} but approvals.spec is missing")
    if idx >= STATUSES.index("plan-approved") and "plan" in required and "plan" not in approvals:
        problems.append(f"status is {item['status']} but approvals.plan is missing")
    if idx >= STATUSES.index("implementing"):
        for name in ("spec.md", "plan.md", "test-plan.md"):
            if not _nonempty(item_dir / name):
                problems.append(f"status is {item['status']} but {name} is missing or empty")
            elif marker := open_marker(_read(item_dir / name)):
                problems.append(f"status is {item['status']} but {name} still has {marker}")
    return problems


DOCS_ONLY_PREFIX = "docs/work/"


def only_work_docs(changed: list[str] | None) -> bool:
    """True when a changed-files list is given and every path is under docs/work/ (empty = True)."""
    if changed is None:
        return False
    return all(
        p.strip().replace("\\", "/").removeprefix("./").startswith(DOCS_ONLY_PREFIX)
        for p in changed
    )


def read_changed_files(path: Path | str | None) -> list[str] | None:
    """Lines of a changed-files list, or None when no list was given or it cannot be read."""
    if not path:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return None
    return [ln for ln in text.splitlines() if ln.strip()]


def check_project(
    root: Path | str, branch: str | None = None, changed_files: list[str] | None = None
) -> list[str]:
    """Run rules 1-3. Returns problems as '<id>: <reason>' (main() prefixes 'FAIL ').

    `changed_files` (the branch's diff) relaxes rule 3's status check for docs-only branches."""
    root = Path(root)
    problems: list[str] = []
    try:
        config = _load_config(root)
        required_approvals({}, config)
    except ValueError as e:
        problems.append(f"factory.yaml: {e}")
        config = {}  # fall back to supervised so the item checks still run

    items: dict[str, dict] = {}
    work = root / "docs" / "work"
    item_files = sorted(work.glob("*/item.yaml")) if work.is_dir() else []
    for path in item_files:
        dirname = path.parent.name
        try:
            item = load_item(path)
        except (ValueError, OSError, UnicodeDecodeError) as e:
            problems.append(f"{dirname}: item.yaml: {e}")
            continue
        bad = validate_item(item, dirname)
        if bad:
            problems.extend(f"{dirname}: {p}" for p in bad)
            continue
        items[item["id"]] = item
        problems.extend(
            f"{item['id']}: {p}" for p in _check_approvals_and_docs(item, path.parent, config)
        )

    m = _BRANCH_RE.match(branch) if branch else None
    if m:
        bid = m.group(1).upper()
        item = items.get(bid)
        if item is None:
            problems.append(f"{bid}: branch '{branch}' has no valid work item in docs/work/")
        elif STATUSES.index(item["status"]) < STATUSES.index("implementing") and not only_work_docs(
            changed_files
        ):
            problems.append(
                f"{bid}: branch '{branch}' carries code but status is {item['status']} "
                "(must be implementing or later)"
            )
    return problems


# --- CLI ---------------------------------------------------------------------------------------


def current_branch(root: Path) -> str | None:
    """Current git branch (also on an unborn branch), or None if not a repo/detached."""
    try:
        r = subprocess.run(
            ["git", "symbolic-ref", "--short", "-q", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    name = r.stdout.strip()
    return name if r.returncode == 0 and name else None


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="project root (default: .)")
    parser.add_argument(
        "--branch", help="branch to check against rule 3 (default: current git branch, if any)"
    )
    parser.add_argument(
        "--changed-files-from",
        metavar="FILE",
        help="file listing the branch's changed paths, one per line; a branch that only changes "
        "docs/work/ may sit at any status",
    )


def run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    branch = args.branch if args.branch else current_branch(root)
    problems = check_project(root, branch, read_changed_files(args.changed_files_from))
    for p in problems:
        print(f"FAIL {p}")
    print("verify: OK" if not problems else f"verify: {len(problems)} problem(s)")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify", description="Factory CI gate (work items).")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
