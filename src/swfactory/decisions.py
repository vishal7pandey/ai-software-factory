"""Owner decisions as a first-class gate (docs/ARCHITECTURE.md section 3.11, FACT-46).

A decision record is `docs/decisions/D-<n>-<slug>.md`: Markdown with YAML front matter. The pure
validator lives in `verify.py` (it must stay standalone: CI runs it where `swfactory` is absent);
this module reads records, lists the ones waiting for the owner, and answers them (`decide`).

`decide` is a ledger like `approve`: it stamps who and when and never runs on its own. Everything
else here (status, doctor, inbox, `decision new`) is read-only or only creates a proposed draft.
Output is ASCII only (Windows consoles) and deterministic: "today" is `common.today()`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from swfactory import common, installer
from swfactory.common import FactoryError
from swfactory.verify import (
    CLARIFY,
    DECISION_FILE_RE,
    DECISION_KEYS,
    DECISION_TYPES,
    DECISIONS_DIR,
    DELEGATED_SUFFIX,
    DISMISSAL_REASONS,
    JIRA_RE,
    NEVER_DELEGATED,
    UNFILLED,
    decision_option_texts,
    split_front_matter,
    validate_decision,
)

TEXT_MAX = 60  # titles and option text in listings
# What shows a record is still a template or a draft; `decide` refuses it (like `approve` does).
PLACEHOLDERS = (UNFILLED, CLARIFY, "REPLACE_ME", "{{")


def placeholder_marker(text: str) -> str | None:
    """The first marker that shows the text is not finished, or None."""
    return next((m for m in PLACEHOLDERS if m in text), None)


# --- reading -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Record:
    path: Path
    id: str  # from the file name; the front matter may disagree (a validation problem)
    text: str
    meta: dict
    body: str
    problems: tuple[str, ...]  # schema problems, or why the file could not be read

    @property
    def status(self) -> str:
        return str(self.meta.get("status") or "")

    @property
    def type(self) -> str:
        return str(self.meta.get("type") or "")

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.path.stem)

    @property
    def recommended(self) -> str:
        for opt in self.meta.get("options") or []:
            if isinstance(opt, dict) and opt.get("recommended") is True:
                return str(opt.get("text") or "")
        return ""

    @property
    def draft(self) -> bool:
        return placeholder_marker(self.text) is not None

    @property
    def waiting(self) -> bool:
        """Proposed and valid: the owner has something to answer."""
        return self.status == "proposed" and not self.problems


def _read_record(path: Path, did: str) -> Record:
    try:
        text = common.normalise_newlines(path.read_text(encoding="utf-8-sig"))
        meta, body = split_front_matter(text)
    except (ValueError, OSError, UnicodeDecodeError) as e:
        return Record(path, did, "", {}, "", (str(e),))
    return Record(path, did, text, meta, body, tuple(validate_decision(meta, path.name)))


def load_records(root: Path | str) -> list[Record]:
    """Every `docs/decisions/D-<n>-*.md` under `root`, in id order. A file that resolves outside
    the folder (a symlink) is skipped. Never raises: a broken file is a Record with problems."""
    folder = os.path.realpath(os.path.join(root, DECISIONS_DIR))
    if not os.path.isdir(folder):
        return []
    out: list[Record] = []
    for name in sorted(os.listdir(folder)):
        m = DECISION_FILE_RE.match(name)
        real = os.path.realpath(os.path.join(folder, name))
        if m and real.startswith(folder + os.sep):
            out.append(_read_record(Path(real), m.group(1)))
    return sorted(out, key=lambda r: (int(r.id[2:]), r.path.name))


def find_record(root: Path, ident: str) -> Record:
    want = ident.strip().strip("/\\").lower()
    found = [r for r in load_records(root) if want in (r.id.lower(), r.path.stem.lower())]
    if not found:
        raise FactoryError(f"no decision record '{ident}' in docs/decisions/")
    if len(found) > 1:
        names = ", ".join(r.path.name for r in found)
        raise FactoryError(f"decision id '{ident}' is ambiguous: {names}")
    return found[0]


# --- listing (status, doctor, inbox) -----------------------------------------------------------


def today_date() -> date:
    return date.fromisoformat(common.today())


def age_days(rec: Record, today: date) -> int:
    try:
        return max(0, (today - date.fromisoformat(str(rec.meta.get("proposed_at")))).days)
    except ValueError:
        return 0


def age_text(days: int) -> str:
    return "today" if days == 0 else f"{days} day" + ("" if days == 1 else "s")


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def _cells(rec: Record, today: date) -> tuple[str, str, str, str, str]:
    tail = "recommended: " + common.ascii_line(rec.recommended, TEXT_MAX)
    return (
        rec.id,
        common.ascii_line(rec.type, TEXT_MAX),
        age_text(age_days(rec, today)),
        common.ascii_line(rec.title, TEXT_MAX),
        tail + ("  [draft]" if rec.draft else ""),
    )


def _rows(cells: list[tuple[str, str, str, str, str]]) -> list[str]:
    widths = [max(len(c[i]) for c in cells) for i in range(4)]
    return ["  ".join(c[i].ljust(widths[i]) for i in range(4)) + "  " + c[4] for c in cells]


def inbox_lines(records: list[Record], today: date) -> list[str]:
    """The block `factory status` prints; empty when nothing waits for the owner."""
    waiting = [r for r in records if r.waiting]
    if not waiting:
        return []
    rows = _rows([_cells(r, today) for r in waiting])
    return [
        f"waiting for the owner ({_count(len(waiting), 'decision')}):",
        *(f"  {row}" for row in rows),
        "  for the owner: `factory decide <id>` (never run by an agent)",
    ]


# --- inbox across projects ---------------------------------------------------------------------


def cmd_inbox(today: date | None = None) -> int:
    """Waiting records of every registered project that has a local path. Read-only."""
    projects = installer.registry_projects()
    if projects is None:
        where = common.registry_path()
        print(f"inbox: no registry yet (`factory adopt` creates it; location: {where})")
        return 0
    today = today or today_date()
    per_project: list[tuple[str, list[Record]]] = []
    skipped: list[str] = []
    invalid: list[str] = []
    for name in sorted(projects):
        path = projects[name]
        if not path:
            skipped.append(f"{name} (no local path registered)")
        elif not os.path.isdir(path):
            skipped.append(f"{name} (path not found)")
        else:
            records = load_records(path)
            invalid += [f"{name} {r.id}" for r in records if r.problems]
            waiting = [r for r in records if r.waiting]
            if waiting:
                per_project.append((name, waiting))
    total = sum(len(w) for _, w in per_project)
    if not total:
        print("inbox: nothing waiting for the owner")
    else:
        rows = _rows([_cells(r, today) for _, w in per_project for r in w])
        print(f"inbox: {_count(total, 'decision')} waiting for the owner")
        at = 0
        for name, waiting in per_project:
            print(f"{name}:")
            for row in rows[at : at + len(waiting)]:
                print(f"  {row}")
            at += len(waiting)
        print("for the owner: run `factory decide <id>` inside the project (never run by an agent)")
    if invalid:
        print(f"invalid: {', '.join(invalid)} (`factory verify` in that project says why)")
    if skipped:
        print(f"skipped: {', '.join(skipped)}")
    return 0


# --- writing -----------------------------------------------------------------------------------


def render_record(meta: dict, body: str) -> str:
    ordered = {k: meta[k] for k in DECISION_KEYS if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    return "---\n" + common.yaml_text(ordered) + "---\n" + body


def _check_decidable(rec: Record) -> None:
    if rec.problems:
        raise FactoryError(f"{rec.id}: invalid record: " + "; ".join(rec.problems))
    if rec.status != "proposed":
        raise FactoryError(f"{rec.id} is already {rec.status}; only a proposed record is decided")
    marker = placeholder_marker(rec.text)
    if marker:
        raise FactoryError(f"{rec.id} still contains '{marker}'; the record must be written first")


def _choose_option(rec: Record, option: int | None) -> str:
    texts = decision_option_texts(rec.meta)
    if option is None:
        return rec.recommended
    if not 1 <= option <= len(texts):
        raise FactoryError(f"--option must be 1 to {len(texts)} (this record has {len(texts)})")
    return texts[option - 1]


def _subject_digest(root: Path, rec: Record) -> dict:
    """`subject_sha256` of the file the decision covers, so a later edit is visible."""
    subject = rec.meta.get("subject")
    if not subject:
        return {}
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, str(subject)))
    if not target.startswith(base + os.sep):
        raise FactoryError(f"{rec.id}: subject {subject} is outside the project")
    if not os.path.isfile(target):
        raise FactoryError(f"{rec.id}: subject {subject} does not exist")
    return {"subject_sha256": common.sha256_file(Path(target))}


def _confirm(prompt: str, yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        raise FactoryError("not a terminal: re-run with --yes to decide non-interactively")
    print(prompt, end="", flush=True)
    if sys.stdin.readline().strip().lower() != "y":
        print("Not decided.")
        return False
    return True


def cmd_decide(
    ident: str,
    *,
    accept: bool = False,
    reject: bool = False,
    option: int | None = None,
    note: str | None = None,
    yes: bool = False,
    delegated: str | None = None,
    start: Path | str = ".",
) -> int:
    """Answer a proposed record like `approve` answers a spec: stamp who and when, change nothing
    else. Run by the owner (or, for a design or other record, under an explicit recorded
    delegation); never by an agent on its own."""
    if accept == reject:
        raise FactoryError("decide needs exactly one of --accept or --reject")
    if option is not None and not accept:
        raise FactoryError("--option only applies to --accept")
    if delegated is not None and not delegated.strip():
        raise FactoryError("--delegated needs the name of whoever delegated this decision")
    root = common.find_project_root(start)
    rec = find_record(root, ident)
    _check_decidable(rec)
    if delegated is not None and rec.type in NEVER_DELEGATED:
        raise FactoryError(
            f"{rec.id}: a {rec.type} decision is never delegated to an agent; "
            "the owner runs `factory decide` themself"
        )
    chosen = _choose_option(rec, option) if accept else None
    extra = _subject_digest(root, rec) if accept else {}
    who = (
        f"{delegated.strip()}{DELEGATED_SUFFIX}"
        if delegated is not None
        else common.git_user_name(root)
    )
    verb = "Accept" if accept else "Reject"
    shown = f" with '{common.ascii_line(chosen, TEXT_MAX)}'" if chosen else ""
    if not _confirm(
        f"{verb} {rec.id} '{common.ascii_line(rec.title, TEXT_MAX)}'{shown} as {who}? [y/N] ", yes
    ):
        return 1
    meta = dict(rec.meta)
    meta.update(
        status="accepted" if accept else "rejected",
        decision=chosen,
        by=who,
        at=common.today(),
        delegated=delegated is not None,
    )
    if note and note.strip():
        meta["note"] = note.strip()
    meta.update(extra)
    rec.path.write_text(render_record(meta, rec.body), encoding="utf-8", newline="\n")
    print(
        f"{rec.id}: {meta['status']} by {who} on {meta['at']}" + (f" ({chosen})" if chosen else "")
    )
    return 0


# --- decision new ------------------------------------------------------------------------------


def _template_body() -> str:
    manifest = common.load_yaml(common.FACTORY_ROOT / "kit" / "manifest.yaml")
    rel = (manifest.get("templates") or {}).get("decision")
    path = common.FACTORY_ROOT / rel if rel else None
    if path is None or not path.is_file():
        raise FactoryError(f"decision template not found ({rel}) in {common.FACTORY_ROOT}")
    return split_front_matter(common.normalise_newlines(path.read_text(encoding="utf-8")))[1]


def _scaffold_options(dtype: str, alert: str | None, reason: str | None) -> list[dict]:
    if dtype != "dismissal":
        if alert or reason:
            raise FactoryError("--alert and --reason only apply to --type dismissal")
        return [
            {"text": "REPLACE_ME: the option you recommend", "recommended": True},
            {"text": "REPLACE_ME: the alternative"},
        ]
    if not alert or not reason:
        raise FactoryError("a dismissal needs --alert (the alert URL) and --reason")
    if not alert.startswith(("https://", "http://")):
        raise FactoryError("--alert must be an http(s) URL")
    if reason not in DISMISSAL_REASONS:
        raise FactoryError(f"--reason must be one of {', '.join(DISMISSAL_REASONS)}")
    return [
        {"text": f"Dismiss the alert as '{reason}'", "recommended": True},
        {"text": "Do not dismiss: fix the finding instead"},
    ]


def cmd_new(
    title: str,
    *,
    dtype: str,
    jira: str | None = None,
    alert: str | None = None,
    reason: str | None = None,
    by: str = "agent",
    start: Path | str = ".",
) -> int:
    """Scaffold a proposed, draft record from the kit template (the next free D-<n>)."""
    if dtype not in DECISION_TYPES:
        raise FactoryError(f"type must be one of {', '.join(DECISION_TYPES)}")
    if not title.strip():
        raise FactoryError("title must not be empty")
    if jira is not None and not JIRA_RE.match(jira):
        raise FactoryError(f"invalid Jira key {jira!r} (expected like PF-12)")
    options = _scaffold_options(dtype, alert, reason)
    root = common.find_project_root(start)
    did = f"D-{max((int(r.id[2:]) for r in load_records(root)), default=0) + 1:03d}"
    name = f"{did}-{common.slugify(title)}.md"
    meta = {
        "id": did,
        "type": dtype,
        "title": title.strip(),
        "status": "proposed",
        "jira": jira,
        "proposed_by": by.strip() or "agent",
        "proposed_at": common.today(),
    }
    if dtype == "dismissal":
        meta.update(alert=alert, reason=reason)
    meta.update(options=options, decision=None, by=None, at=None, delegated=False)
    body = _template_body().replace("{{title}}", meta["title"])
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, DECISIONS_DIR, name))
    if not target.startswith(base + os.sep):
        raise FactoryError(f"{DECISIONS_DIR}/{name} is outside the project {root}")
    if os.path.exists(target):
        raise FactoryError(f"{DECISIONS_DIR}/{name} already exists")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_record(meta, body))
    print(f"Created {DECISIONS_DIR}/{name}")
    print(
        "Write the context, evidence and options, fix the options in the front matter, delete the "
        "unfilled line; then the owner answers with `factory decide " + did + "`."
    )
    return 0
