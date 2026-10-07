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
    if isinstance(obj, list):
        return [_norm_dates(v) for v in obj]
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

    problems.extend(check_decisions(root))

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


# --- decision records (FACT-46, docs/ARCHITECTURE.md section 3.11) -----------------------------

DECISION_TYPES = ["dismissal", "design", "charter", "other"]
DECISION_STATUSES = ["proposed", "accepted", "rejected", "superseded"]
DISMISSAL_REASONS = ["false positive", "won't fix", "used in tests"]
# Never decided on the owner's behalf, even with an explicit delegation: a security exception and
# the project charter.
NEVER_DELEGATED = ("charter", "dismissal")
DECISION_KEYS = [
    "id",
    "type",
    "title",
    "status",
    "jira",
    "proposed_by",
    "proposed_at",
    "alert",
    "reason",
    "options",
    "decision",
    "by",
    "at",
    "delegated",
    "note",
    "subject",
    "subject_sha256",
    "superseded_by",
]
DECISIONS_DIR = "docs/decisions"
DECISION_ID_RE = re.compile(r"^D-\d+$")
DECISION_FILE_RE = re.compile(r"^(D-\d+)-.+\.md$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


def split_front_matter(text: str) -> tuple[dict, str]:
    """('---\\nk: v\\n---\\nbody') -> ({'k': 'v'}, 'body'). ValueError without a YAML mapping."""
    text = text.replace("\r\n", "\n").lstrip("﻿")
    m = _FRONT_RE.match(text)
    if not m:
        raise ValueError("no YAML front matter (the file must start with a '---' line)")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        first = str(e).splitlines()[0] if str(e) else e
        raise ValueError(f"front matter is not valid YAML: {first}") from e
    if not isinstance(meta, dict):
        raise ValueError("front matter must be a YAML mapping")
    return _norm_dates(meta), m.group(2)


def load_decision(path: Path | str) -> tuple[dict, str]:
    """Read a decision record: (front matter, body). ValueError without valid front matter."""
    return split_front_matter(Path(path).read_text(encoding="utf-8-sig"))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def decision_option_texts(meta: dict) -> list[str]:
    """The text of every well-formed option, in order."""
    options = meta.get("options")
    if not isinstance(options, list):
        return []
    return [o["text"] for o in options if isinstance(o, dict) and _text(o.get("text"))]


def _decision_identity(meta: dict, filename: str) -> list[str]:
    problems = [
        f"missing required field '{key}'"
        for key in ("id", "type", "title", "status", "proposed_by", "proposed_at")
        if meta.get(key) in (None, "")
    ]
    did = meta.get("id")
    if did in (None, ""):
        pass
    elif not isinstance(did, str) or not DECISION_ID_RE.match(did):
        problems.append(f"id {did!r} is not D-<number>")
    elif not filename.startswith(f"{did}-"):
        problems.append(f"id {did!r} does not match file name {filename!r}")
    for key, allowed in (("type", DECISION_TYPES), ("status", DECISION_STATUSES)):
        val = meta.get(key)
        if val not in (None, "") and val not in allowed:
            problems.append(f"{key} {val!r} is not one of {', '.join(allowed)}")
    return problems


def _decision_scalars(meta: dict) -> list[str]:
    problems = [
        f"{key} must be a non-empty string"
        for key in ("title", "proposed_by")
        if meta.get(key) not in (None, "") and not _text(meta.get(key))
    ]
    proposed_at = meta.get("proposed_at")
    if proposed_at not in (None, "") and not (
        isinstance(proposed_at, str) and _DATE_RE.match(proposed_at)
    ):
        problems.append(f"proposed_at {proposed_at!r} is not an ISO date (YYYY-MM-DD)")
    jira = meta.get("jira")
    if jira is not None and not (isinstance(jira, str) and JIRA_RE.match(jira)):
        problems.append(f"jira {jira!r} is not a Jira key or null")
    return problems


def _option_problems(options: list) -> tuple[list[str], int]:
    """(problems, number recommended) of the `options` list entries."""
    problems: list[str] = []
    recommended = 0
    for i, opt in enumerate(options, 1):
        if not isinstance(opt, dict) or not _text(opt.get("text")):
            problems.append(f"options[{i}] must be a mapping with a non-empty 'text'")
        elif "recommended" in opt and not isinstance(opt["recommended"], bool):
            problems.append(f"options[{i}].recommended must be true or false")
        elif opt.get("recommended"):
            recommended += 1
    return problems, recommended


def _decision_options(meta: dict) -> list[str]:
    options = meta.get("options")
    if not isinstance(options, list) or not options:
        return ["options must be a non-empty list"]
    problems, recommended = _option_problems(options)
    texts = decision_option_texts(meta)
    if len(set(texts)) != len(texts):
        problems.append("option texts must be distinct")
    if recommended > 1:
        problems.append("at most one option may be recommended")
    elif recommended == 0 and meta.get("status") == "proposed" and not problems:
        problems.append("a proposed record needs one recommended option")
    return problems


def _decision_answer(meta: dict) -> list[str]:
    """The owner's answer: by/at/decision must fit the status."""
    status, by, at = meta.get("status"), meta.get("by"), meta.get("at")
    problems: list[str] = []
    if status in ("accepted", "rejected"):
        if not _text(by):
            problems.append(f"status is {status} but 'by' is missing")
        if not (isinstance(at, str) and _DATE_RE.match(at)):
            problems.append(f"status is {status} but 'at' is missing or not YYYY-MM-DD")
    if status == "accepted" and meta.get("decision") not in decision_option_texts(meta):
        problems.append("status is accepted but 'decision' is not the text of one of the options")
    if status in ("proposed", "rejected") and meta.get("decision") not in (None, ""):
        problems.append(f"status is {status} but 'decision' is set")
    if status == "proposed":
        problems.extend(
            f"status is proposed but '{key}' is set"
            for key in ("by", "at")
            if meta.get(key) not in (None, "")
        )
    return problems


def _decision_delegation(meta: dict) -> list[str]:
    """A delegation must be honest, and is never allowed for a charter or a dismissal."""
    problems: list[str] = []
    delegated, by = meta.get("delegated", False), meta.get("by")
    if not isinstance(delegated, bool):
        problems.append("delegated must be true or false")
    elif delegated and not (isinstance(by, str) and by.endswith(DELEGATED_SUFFIX)):
        problems.append(f"delegated is true but 'by' does not end with '{DELEGATED_SUFFIX}'")
    if is_delegated(meta) and meta.get("type") in NEVER_DELEGATED:
        problems.append(f"a {meta.get('type')} decision is never delegated to an agent")
    return problems


def _decision_type_fields(meta: dict) -> list[str]:
    problems: list[str] = []
    if meta.get("type") == "dismissal":
        alert = meta.get("alert")
        if not (isinstance(alert, str) and alert.startswith(("https://", "http://"))):
            problems.append("a dismissal needs 'alert': the alert URL (http or https)")
        if meta.get("reason") not in DISMISSAL_REASONS:
            problems.append(f"a dismissal needs 'reason', one of {', '.join(DISMISSAL_REASONS)}")
    superseded_by = meta.get("superseded_by")
    if meta.get("status") == "superseded" and not (
        isinstance(superseded_by, str) and DECISION_ID_RE.match(superseded_by)
    ):
        problems.append("status is superseded but 'superseded_by' is not a D-<number>")
    return problems


def _decision_subject(meta: dict) -> list[str]:
    subject = meta.get("subject")
    if subject is None:
        return []
    parts = str(subject).replace("\\", "/").split("/")
    escapes = parts[0] == "" or ".." in parts or re.match(r"^[A-Za-z]:", parts[0])
    if not _text(subject) or escapes:
        return ["subject must be a path inside the project (no '..', not absolute)"]
    digest = str(meta.get("subject_sha256") or "")
    if meta.get("status") == "accepted" and not _SHA_RE.match(digest):
        return ["status is accepted but 'subject_sha256' is not a sha256 hex digest"]
    return []


def validate_decision(meta: dict, filename: str) -> list[str]:
    """Schema check of one decision record's front matter. Empty list means valid. Pure."""
    if not isinstance(meta, dict):
        return ["front matter must be a YAML mapping"]
    return [
        problem
        for check in (
            lambda m: _decision_identity(m, filename),
            _decision_scalars,
            _decision_options,
            _decision_answer,
            _decision_delegation,
            _decision_type_fields,
            _decision_subject,
        )
        for problem in check(meta)
    ]


def check_decisions(root: Path | str) -> list[str]:
    """Rule 6: every `docs/decisions/D-<n>-<slug>.md` is valid. Other files there (ADRs, the
    template) are not decision records and are ignored. Returns '<id>: <reason>' lines."""
    folder = Path(root) / DECISIONS_DIR
    if not folder.is_dir():
        return []
    problems: list[str] = []
    seen: dict[str, str] = {}
    for path in sorted(folder.glob("*.md")):
        m = DECISION_FILE_RE.match(path.name)
        if not m:
            continue
        did = m.group(1)
        if did in seen:
            problems.append(f"{did}: duplicate id in {seen[did]} and {path.name}")
        seen.setdefault(did, path.name)
        try:
            meta, _ = load_decision(path)
        except (ValueError, OSError) as e:
            problems.append(f"{did}: {path.name}: {e}")
            continue
        problems.extend(f"{did}: {p}" for p in validate_decision(meta, path.name))
    return problems


# --- warnings (never fail the gate) ------------------------------------------------------------

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def audit_is_placeholder(text: str) -> bool:
    """True when `test-plan.md` has an `## Audit` section that is empty apart from comments."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## Audit")), None)
    if start is None:
        return False
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = "\n".join(lines[start + 1 : end])
    return not _HTML_COMMENT_RE.sub("", body).strip()


def warn_project(root: Path | str) -> list[str]:
    """Warnings as '<id>: <reason>' (run() prefixes 'WARN '). They never change the exit code.

    An item at `in-review` or later whose test-plan Audit is still the template placeholder."""
    root = Path(root)
    out: list[str] = []
    work = root / "docs" / "work"
    item_files = sorted(work.glob("*/item.yaml")) if work.is_dir() else []
    for path in item_files:
        try:
            item = load_item(path)
            if validate_item(item, path.parent.name):
                continue
            if STATUSES.index(item["status"]) < STATUSES.index("in-review"):
                continue
            text = (path.parent / "test-plan.md").read_text(encoding="utf-8-sig")
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        if audit_is_placeholder(text):
            out.append(
                f"{item['id']}: status is {item['status']} but the Audit section of "
                "test-plan.md is still the template placeholder"
            )
    return out


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
    warnings = warn_project(root)
    for w in warnings:
        print(f"WARN {w}")
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        print(f"verify: {len(problems)} problem(s)")
    else:
        suffix = f" ({len(warnings)} warning(s))" if warnings else ""
        print(f"verify: OK{suffix}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify", description="Factory CI gate (work items).")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
