"""The project charter `docs/PROJECT.md` (docs/ARCHITECTURE.md section 3.12, FACT-47).

A charter says what the project is for, when it is done (3 to 7 measurable criteria, each with a
reference the factory can check offline), what it will not do, what is parked, and what maintenance
mode means. It is approved only through a `charter` decision record (FACT-46) whose `subject` is the
file: `decide --accept` stamps the file's sha256, so an edit afterwards shows as `changed`.

Everything here is offline and deterministic. A `jira` reference is read through an injected lookup
(none by default: it is `unknown`). Files are read only inside the project.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from swfactory import common, decisions
from swfactory.common import FactoryError
from swfactory.verify import (
    CHARTER_PATH,
    ID_RE,
    JIRA_RE,
    STATUSES,
    is_project_path,
    load_item,
    split_front_matter,
)

MODES = ("active", "maintenance")
CHECK_KINDS = ("work", "file", "metric", "jira")
BOUNDS = ("min", "max", "equals")
MIN_CRITERIA, MAX_CRITERIA = 3, 7
PURPOSE_MAX = 400
MET, NOT_MET, UNKNOWN = "met", "not met", "unknown"
# Phrases that are not measurable; the real test of measurability is the `check` reference.
VAGUE = (
    "works well",
    "work well",
    "works fine",
    "user-friendly",
    "user friendly",
    "easy to use",
    "intuitive",
    "good enough",
    "high quality",
    "robust",
    "performant",
    "scalable",
    "fast enough",
    "as needed",
    "and so on",
    "etc",
)
_VAGUE_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in VAGUE) + r")\b", re.IGNORECASE)
JiraStatus = Callable[[str], "str | None"]


# --- parse and validate (pure) -----------------------------------------------------------------


def parse_charter(text: str) -> tuple[dict, str, list[str]]:
    """(front matter, body, problems). Never raises. A template (an unfilled marker or a
    placeholder) is reported as one problem containing 'still the template'."""
    try:
        meta, body = split_front_matter(text)
    except ValueError as e:
        return {}, "", [str(e)]
    marker = decisions.placeholder_marker(text)
    if marker:
        return meta, body, [f"{CHARTER_PATH} is still the template ('{marker}' is present)"]
    return meta, body, validate_charter(meta, body)


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_problems(cid: str, check: object) -> list[str]:
    if not isinstance(check, dict):
        return [f"{cid}: check must be a mapping with one of {', '.join(CHECK_KINDS)}"]
    kinds = [k for k in check if k in CHECK_KINDS]
    if len(check) != 1 or len(kinds) != 1:
        return [f"{cid}: check needs exactly one of {', '.join(CHECK_KINDS)}"]
    kind, ref = kinds[0], check[kinds[0]]
    if kind == "work":
        ok = isinstance(ref, str) and ID_RE.match(ref)
        return [] if ok else [f"{cid}: work reference {ref!r} is not a work item id"]
    if kind == "jira":
        ok = isinstance(ref, str) and JIRA_RE.match(ref)
        return [] if ok else [f"{cid}: jira reference {ref!r} is not a Jira key"]
    if kind == "file":
        return [] if is_project_path(ref) else [f"{cid}: file must be a path inside the project"]
    return _metric_problems(cid, ref)


def _metric_problems(cid: str, spec: object) -> list[str]:
    if not isinstance(spec, dict):
        return [f"{cid}: metric must be a mapping with file, key and one of min, max, equals"]
    problems: list[str] = []
    if not is_project_path(spec.get("file")):
        problems.append(f"{cid}: metric file must be a path inside the project")
    if not (isinstance(spec.get("key"), str) and spec["key"].strip()):
        problems.append(f"{cid}: metric needs a 'key' (dotted path into the file)")
    bounds = [b for b in BOUNDS if b in spec]
    if len(bounds) != 1:
        problems.append(f"{cid}: metric needs exactly one of {', '.join(BOUNDS)}")
    elif not _number(spec[bounds[0]]):
        problems.append(f"{cid}: metric {bounds[0]} must be a number")
    return problems


def _criterion_problems(i: int, crit: object, seen: set[str]) -> list[str]:
    if not isinstance(crit, dict):
        return [f"done[{i}] must be a mapping with id, text and check"]
    cid = crit.get("id")
    if not (isinstance(cid, str) and cid.strip()):
        return [f"done[{i}] needs an id"]
    problems: list[str] = []
    if cid in seen:
        problems.append(f"duplicate criterion id '{cid}'")
    seen.add(cid)
    text = crit.get("text")
    if not (isinstance(text, str) and text.strip()):
        problems.append(f"{cid}: text is missing")
    else:
        vague = _VAGUE_RE.search(text)
        if vague:
            problems.append(f"{cid}: '{vague.group(0).lower()}' is not measurable")
        if len(text.split()) < 3:
            problems.append(f"{cid}: text needs at least three words")
    return problems + _check_problems(cid, crit.get("check"))


def _list_of_text(meta: dict, key: str) -> list[str]:
    items = meta.get(key)
    if not isinstance(items, list) or not items:
        return [f"{key} must list at least one entry"]
    return [
        f"{key}[{i}] must be a non-empty string"
        for i, item in enumerate(items, 1)
        if not (isinstance(item, str) and item.strip())
    ]


def _parked_problems(meta: dict) -> list[str]:
    parked = meta.get("parked", [])
    if not isinstance(parked, list):
        return ["parked must be a list"]
    problems: list[str] = []
    for i, entry in enumerate(parked, 1):
        if not (isinstance(entry, dict) and isinstance(entry.get("item"), str) and entry["item"]):
            problems.append(f"parked[{i}] needs an 'item'")
        elif entry.get("jira") is not None and not (
            isinstance(entry["jira"], str) and JIRA_RE.match(entry["jira"])
        ):
            problems.append(f"parked[{i}].jira {entry['jira']!r} is not a Jira key")
    return problems


def _header_problems(meta: dict) -> list[str]:
    problems: list[str] = []
    purpose = meta.get("purpose")
    if not (isinstance(purpose, str) and purpose.strip()):
        problems.append("purpose is missing")
    elif len(purpose) > PURPOSE_MAX:
        problems.append(f"purpose is longer than {PURPOSE_MAX} characters")
    if meta.get("mode") not in MODES:
        problems.append(f"mode {meta.get('mode')!r} is not one of {', '.join(MODES)}")
    decision = meta.get("decision")
    if decision is not None and not (isinstance(decision, str) and re.match(r"^D-\d+$", decision)):
        problems.append("decision must be a D-<number> or null")
    return problems


def validate_charter(meta: dict, body: str) -> list[str]:
    """Schema check of a charter. Empty list means valid. Pure."""
    if not isinstance(meta, dict):
        return ["front matter must be a YAML mapping"]
    problems = _header_problems(meta)
    done = meta.get("done")
    n = len(done) if isinstance(done, list) else 0
    if not MIN_CRITERIA <= n <= MAX_CRITERIA:
        problems.append(f"done must list {MIN_CRITERIA} to {MAX_CRITERIA} criteria (found {n})")
    seen: set[str] = set()
    for i, crit in enumerate(done if isinstance(done, list) else [], 1):
        problems += _criterion_problems(i, crit, seen)
    problems += _list_of_text(meta, "non_goals") + _parked_problems(meta)
    if "## Maintenance mode" not in body:
        problems.append("the body needs a '## Maintenance mode' section")
    return problems


# --- evaluating a criterion (offline) ----------------------------------------------------------


def _eval_work(ref: object, root: Path) -> str:
    wanted = str(ref).lower()
    for path in sorted((root / "docs" / "work").glob("*/item.yaml")):
        try:
            item = load_item(path)
        except (ValueError, OSError):
            continue
        if str(item.get("id", "")).lower() == wanted:
            status = item.get("status")
            merged = status in STATUSES and STATUSES.index(status) >= STATUSES.index("merged")
            return MET if merged else NOT_MET
    return NOT_MET


def _eval_file(ref: object, root: Path) -> str:
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, str(ref)))
    if target.startswith(base + os.sep) and os.path.isfile(target):
        return MET
    return NOT_MET


def _metric_value(spec: dict, root: Path) -> float | int | None:
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, str(spec.get("file"))))
    if not target.startswith(base + os.sep) or not os.path.isfile(target):
        return None
    try:
        with open(target, encoding="utf-8-sig") as fh:
            value = yaml.safe_load(fh)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    for part in str(spec.get("key")).split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value if _number(value) else None


def _eval_metric(spec: object, root: Path) -> str:
    if not isinstance(spec, dict):
        return UNKNOWN
    value = _metric_value(spec, root)
    bound = next((b for b in BOUNDS if b in spec), None)
    if value is None or bound is None or not _number(spec[bound]):
        return UNKNOWN
    ok = {"min": value >= spec[bound], "max": value <= spec[bound], "equals": value == spec[bound]}
    return MET if ok[bound] else NOT_MET


def evaluate(criterion: object, root: Path | str, jira_status: JiraStatus | None = None) -> str:
    """`met`, `not met` or `unknown` for one done criterion. Never raises."""
    check = criterion.get("check") if isinstance(criterion, dict) else None
    if not isinstance(check, dict) or len(check) != 1:
        return UNKNOWN
    kind, ref = next(iter(check.items()))
    root = Path(root)
    if kind == "work":
        return _eval_work(ref, root)
    if kind == "file":
        return _eval_file(ref, root)
    if kind == "metric":
        return _eval_metric(ref, root)
    if kind == "jira":
        status = jira_status(str(ref)) if jira_status else None
        if status is None:
            return UNKNOWN
        return MET if status == "Done" else NOT_MET
    return UNKNOWN


def describe(criterion: dict) -> str:
    """The reference of a criterion as printed: `work FACT-12`, `metric <file> <key> min 0.9`."""
    kind, ref = next(iter(criterion["check"].items()))
    if kind != "metric":
        return f"{kind} {ref}"
    bound = next(b for b in BOUNDS if b in ref)
    return f"metric {ref['file']} {ref['key']} {bound} {ref[bound]}"


# --- approval state ----------------------------------------------------------------------------


@dataclass(frozen=True)
class CharterState:
    """`absent`, `template`, `invalid`, `unapproved`, `changed` or `approved`."""

    state: str
    detail: str = ""
    mode: str = ""
    decision: str = ""
    meta: dict = field(default_factory=dict)


def _approval(meta: dict, doc: Path, root: Path) -> CharterState:
    dec, mode = meta.get("decision"), str(meta.get("mode"))
    if not dec:
        hint = (
            'propose one: factory decision new "<title>" --type charter, then name it in `decision`'
        )
        return CharterState("unapproved", f"no decision record names this charter ({hint})", mode)
    rec = next((r for r in decisions.load_records(root) if r.id == dec), None)
    if rec is None:
        return CharterState("unapproved", f"decision {dec} does not exist", mode, dec)
    if rec.problems:
        return CharterState("unapproved", f"decision {dec} is invalid (factory verify)", mode, dec)
    if rec.type != "charter":
        return CharterState("unapproved", f"decision {dec} is not a charter decision", mode, dec)
    if rec.status != "accepted":
        why = {
            "proposed": "is waiting for the owner",
            "rejected": "was rejected",
            "superseded": "is superseded",
        }[rec.status]
        return CharterState("unapproved", f"decision {dec} {why}", mode, dec)
    if common.sha256_file(doc) != rec.meta.get("subject_sha256"):
        detail = (
            f"{CHARTER_PATH} was edited after {dec} was accepted; a new charter decision is needed"
        )
        return CharterState("changed", detail, mode, dec, meta)
    return CharterState("approved", "", mode, dec, meta)


def charter_state(root: Path | str) -> CharterState:
    root = Path(root)
    doc = root / CHARTER_PATH
    if not doc.is_file():
        return CharterState("absent", f"{CHARTER_PATH} is missing")
    try:
        text = common.normalise_newlines(doc.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError) as e:
        return CharterState("invalid", f"{CHARTER_PATH} cannot be read: {e}")
    meta, _, problems = parse_charter(text)
    if any("still the template" in p for p in problems):
        return CharterState("template", f"{CHARTER_PATH} is still the template")
    if problems:
        return CharterState("invalid", "; ".join(problems[:3]))
    return _approval(meta, doc, root)


def check_acceptable(root: Path | str, rec: decisions.Record) -> None:
    """Pre-accept gate of `decide` for a charter record: the file must be a valid charter that
    names this record. Raises FactoryError."""
    doc = Path(root) / CHARTER_PATH
    if not doc.is_file():
        raise FactoryError(f"{rec.id}: {CHARTER_PATH} does not exist")
    text = common.normalise_newlines(doc.read_text(encoding="utf-8-sig"))
    meta, _, problems = parse_charter(text)
    if problems:
        raise FactoryError(
            f"{rec.id}: {CHARTER_PATH} is not a valid charter: " + "; ".join(problems[:3])
        )
    if meta.get("decision") != rec.id:
        raise FactoryError(
            f"{rec.id}: {CHARTER_PATH} does not name {rec.id} in `decision` "
            f"(it says {meta.get('decision')!r})"
        )


# --- output ------------------------------------------------------------------------------------


def status_lines(root: Path | str, jira_status: JiraStatus | None = None) -> list[str]:
    """What `factory status` prints about the charter; empty when the project has none."""
    st = charter_state(root)
    if st.state == "absent":
        return []
    if st.state != "approved":
        return [f"charter: no approved charter - {st.detail}"]
    if st.mode == "maintenance":
        return [
            f"charter: approved by {st.decision}, maintenance mode - only security and dependency "
            "updates; any other change needs a charter amendment"
        ]
    done = st.meta["done"]
    results = [evaluate(c, root, jira_status) for c in done]
    met = results.count(MET)
    lines = [
        f"charter: approved by {st.decision}, active - done criteria: {met} of {len(done)} met"
    ]
    for crit, result in zip(done, results, strict=True):
        text = common.ascii_line(crit["text"], 60)
        lines.append(f"  {crit['id']}  {result:<7}  {text}  ({describe(crit)})")
    if met == len(done):
        lines.append(
            "ready for maintenance mode: every done criterion is met. The owner decides: set "
            f"`mode: maintenance` in {CHARTER_PATH} and propose a charter decision "
            "(`factory decision new --type charter`); `factory decide` is never run by an agent."
        )
    return lines


def maintenance_warning(root: Path | str) -> str | None:
    """The warning `feature start` prints in maintenance mode, or None."""
    st = charter_state(root)
    if st.state in ("approved", "changed") and st.mode == "maintenance":
        return (
            f"warning: this project is in maintenance mode (charter {st.decision}): a new feature "
            "needs a charter amendment (a `charter` decision the owner accepts); continuing, "
            "because the owner may proceed deliberately"
        )
    return None
