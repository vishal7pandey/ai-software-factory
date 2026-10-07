"""The supported-today matrix cannot rot (FACT-48).

`docs/SUPPORT.md` says, per dimension and value, what the factory supports, what proves it and the
known gaps. `check_support(root)` compares that file with what the repository contains and returns
one problem line per mismatch: a stack with no row, a claim with nothing behind it, a row that is
not filled in, a doc that does not link the matrix. Pure and offline: it reads files under `root`
and writes nothing. `factory lint` runs it in a factory repository (checks.lint_factory).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from swfactory.installer import STACKS

SUPPORT_REL = "docs/SUPPORT.md"
MANIFEST_REL = "kit/manifest.yaml"
STATUSES = ("supported", "partial", "not supported")
REQUIRED_DIMENSIONS = {"stack", "tracker", "hosting", "ci", "scanner", "os"}
LINKING_DOCS = ("ARCHITECTURE.md", "ROADMAP.md")  # under docs/, each must mention SUPPORT.md
SHARED_STEMS = {"generic"}  # kit/ci/generic.yml serves the stacks `docs` and `other`; not a stack
STACK_FILE_DIRS = ("ci", "sonar")  # kit/<dir>/<stack>.<ext>
COLUMNS = ("dimension", "value", "status", "proven by", "known gaps")
ECOSYSTEM = "dependabot ecosystem"


@dataclass(frozen=True)
class Row:
    dimension: str  # lower case
    value: str  # backticks removed, lower case
    status: str  # lower case
    proven: str
    gaps: str
    line: int  # 1-based line in the file


def _is_separator(cells: list[str]) -> bool:
    return all(c and set(c) <= set(":-") for c in cells)


def _table_lines(text: str) -> list[tuple[int, list[str]]]:
    """(line number, cells) of every table line except the separator and the header line."""
    out: list[tuple[int, list[str]]] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if _is_separator(cells) or cells[0].lower() == COLUMNS[0]:
            continue
        out.append((n, cells))
    return out


def parse_rows(text: str) -> list[Row]:
    """The well-formed rows (five cells); `check_support` reports the malformed lines."""
    return [
        Row(
            dimension=c[0].lower(),
            value=c[1].replace("`", "").strip().lower(),
            status=c[2].lower(),
            proven=c[3],
            gaps=c[4],
            line=n,
        )
        for n, c in _table_lines(text)
        if len(c) == len(COLUMNS)
    ]


# --- what the repository contains ----------------------------------------------------------------


def _stack_names(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _load_manifest(root: Path) -> tuple[dict, list[str]]:
    path = root / MANIFEST_REL
    if not path.is_file():
        return {}, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
        return {}, [f"{MANIFEST_REL} cannot be read: {str(e).splitlines()[0]}"]
    return (data, []) if isinstance(data, dict) else ({}, [f"{MANIFEST_REL} is not a mapping"])


def _manifest_stacks(manifest: dict) -> dict[str, str]:
    found: dict[str, str] = {}
    for section in ("files", "dirs"):
        for entry in manifest.get(section) or []:
            for name in _stack_names(entry.get("stack") if isinstance(entry, dict) else None):
                found.setdefault(name.lower(), f"a `stack:` value in {MANIFEST_REL}")
    return found


def _file_stacks(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    templates = root / "templates"
    if templates.is_dir():
        for d in sorted(p for p in templates.iterdir() if p.is_dir()):
            found.setdefault(d.name.lower(), f"directory templates/{d.name}")
    for sub in STACK_FILE_DIRS:
        folder = root / "kit" / sub
        if not folder.is_dir():
            continue
        for f in sorted(p for p in folder.iterdir() if p.is_file()):
            if f.stem.lower() not in SHARED_STEMS:
                found.setdefault(f.stem.lower(), f"file kit/{sub}/{f.name}")
    return found


def existing_stacks(root: Path, manifest: dict | None = None) -> dict[str, str]:
    """Every stack the repository has, with where it was found (the first source wins)."""
    if manifest is None:
        manifest = _load_manifest(root)[0]
    found = {name: "the STACKS constant in installer.py" for name in STACKS}
    for source in (_manifest_stacks(manifest), _file_stacks(root)):
        for name, where in source.items():
            found.setdefault(name, where)
    return found


# --- the checks ----------------------------------------------------------------------------------


def _row_problems(rows: list[Row]) -> list[str]:
    out: list[str] = []
    for r in rows:
        who = f"{SUPPORT_REL} line {r.line} ({r.dimension} {r.value})"
        if r.status not in STATUSES:
            out.append(f"{who}: status '{r.status}' is not one of {', '.join(STATUSES)}")
        cells = {
            "dimension": r.dimension,
            "value": r.value,
            "proven by": r.proven,
            "known gaps": r.gaps,
        }
        out += [f"{who}: the '{name}' cell is empty" for name, text in cells.items() if not text]
    return out


def _shape_problems(text: str) -> list[str]:
    return [
        f"{SUPPORT_REL} line {n}: expected {len(COLUMNS)} cells, found {len(cells)}"
        for n, cells in _table_lines(text)
        if len(cells) != len(COLUMNS)
    ]


def _dimension_problems(rows: list[Row]) -> list[str]:
    have = {r.dimension for r in rows}
    return [
        f"{SUPPORT_REL}: dimension '{d}' has no row" for d in sorted(REQUIRED_DIMENSIONS - have)
    ]


def _stack_problems(rows: list[Row], stacks: dict[str, str]) -> list[str]:
    rowed = {r.value for r in rows if r.dimension == "stack"}
    out = [
        f"stack '{name}' ({where}) has no row in {SUPPORT_REL}"
        for name, where in sorted(stacks.items())
        if name not in rowed
    ]
    for r in (r for r in rows if r.dimension == "stack"):
        if r.status == "not supported" and r.value in stacks:
            out.append(
                f"{SUPPORT_REL} line {r.line}: stack '{r.value}' is marked not supported "
                f"but it exists ({stacks[r.value]}); update the row"
            )
        elif r.status in ("supported", "partial") and r.value not in stacks:
            out.append(
                f"{SUPPORT_REL} line {r.line}: stack '{r.value}' claims {r.status} but no "
                "template, manifest entry or stack constant exists for it"
            )
    return out


def _ecosystem_problems(rows: list[Row], manifest: dict) -> list[str]:
    templates = manifest.get("dependabot_templates")
    kinds = sorted(templates) if isinstance(templates, dict) else []
    rowed = {r.value for r in rows if r.dimension == ECOSYSTEM}
    return [
        f"{ECOSYSTEM} '{kind}' (from dependabot_templates) has no row in {SUPPORT_REL}"
        for kind in kinds
        if str(kind).lower() not in rowed
    ]


def _link_problems(root: Path) -> list[str]:
    out: list[str] = []
    for name in LINKING_DOCS:
        path = root / "docs" / name
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            out.append(f"docs/{name} is missing (it must link SUPPORT.md)")
        except (OSError, UnicodeDecodeError) as e:
            out.append(f"docs/{name} cannot be read: {e}")
        else:
            if "SUPPORT.md" not in text:
                out.append(f"docs/{name} does not link SUPPORT.md")
    return out


def check_support(root: Path | str) -> list[str]:
    """Problems that make the matrix stale or untrustworthy; an empty list means it is current."""
    root = Path(root)
    path = root / SUPPORT_REL
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{SUPPORT_REL} is missing (the supported-today matrix)", *_link_problems(root)]
    except (OSError, UnicodeDecodeError) as e:
        return [f"{SUPPORT_REL} cannot be read: {e}"]
    rows = parse_rows(text)
    if not rows and not _table_lines(text):
        return [f"{SUPPORT_REL} has no table rows", *_link_problems(root)]
    manifest, problems = _load_manifest(root)
    problems += _shape_problems(text) + _row_problems(rows) + _dimension_problems(rows)
    problems += _stack_problems(rows, existing_stacks(root, manifest))
    problems += _ecosystem_problems(rows, manifest)
    return problems + _link_problems(root)
