"""Logic behind `factory lint` and `factory doctor`. Commands in commands/ stay thin.

Everything takes its inputs (roots, tool lookup, command runner) as arguments so tests can inject
fixtures instead of touching the real machine. Output is ASCII-only (Windows consoles).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from swfactory import __version__
from swfactory import charter as _charter
from swfactory import common as _common
from swfactory import decisions as _decisions
from swfactory import dependabot as _dependabot
from swfactory import deps as _deps
from swfactory import harden as _harden
from swfactory import installer as _installer
from swfactory import sonar as _sonar
from swfactory.common import FactoryError

OK, WARN, FAIL = "OK", "WARN", "FAIL"


@dataclass(frozen=True)
class Finding:
    level: str  # OK | WARN | FAIL
    name: str  # path (lint) or check name (doctor)
    detail: str


def failures(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.level == FAIL]


# =================================================================================================
# lint
# =================================================================================================

SKILL_SECTIONS = [
    "## When to use",
    "## Inputs",
    "## Steps",
    "## Output",
    "## Definition of done",
    "## Never",
]
MAX_BODY_LINES = 150
MAX_DESCRIPTION = 1024
MODES = {"create", "managed", "block"}
STACKS = {"python", "node", "docs", "other"}

_APPROVE = re.compile(r"factory (?:approve|decide)", re.IGNORECASE)
_PROHIBITION = re.compile(r"\b(never|don't|don’t|do not|must not|human|ask)", re.IGNORECASE)
_REFERENCE = re.compile(r"references/[A-Za-z0-9_\-./]*[A-Za-z0-9_\-]")
_SKILL_NAME = re.compile(r"(?<![A-Za-z0-9_])factory-[a-z0-9]+(?:-[a-z0-9]+)*")
_FILE_EXT = re.compile(r"\.(?:ya?ml|py|md|json|toml|txt)\b")


# Rules a named skill must keep carrying (FACT-21): label and a case-insensitive pattern each.
REQUIRED_RULES: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "factory-implement": [
        (
            "file-editing hazard rule (never rewrite files with inline scripts)",
            re.compile(r"inline script", re.I),
        ),
        ("explicit-staging rule (never `git add -A`)", re.compile(r"git add -A")),
    ],
}


def _skill_findings(skill_dir: Path, all_names: set[str], root: Path) -> list[Finding]:
    rel = skill_dir.relative_to(root).as_posix() + "/SKILL.md"
    out: list[Finding] = []

    def fail(reason: str) -> None:
        out.append(Finding(FAIL, rel, reason))

    name = skill_dir.name
    if not name.startswith("factory-"):
        fail("skill directory name must start with 'factory-'")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail("SKILL.md is missing")
        return out
    try:
        text = skill_md.read_text(encoding="utf-8")
        meta, body = _common.split_frontmatter(text)
    except (FactoryError, yaml.YAMLError, UnicodeDecodeError) as e:
        fail(f"cannot parse frontmatter: {e}".splitlines()[0])
        return out
    if not meta:
        fail("missing YAML frontmatter")

    if meta and meta.get("name") != name:
        fail(f"frontmatter name {meta.get('name')!r} must equal directory name {name!r}")
    desc = meta.get("description") if meta else None
    if meta:
        if not isinstance(desc, str) or not desc.strip():
            fail("frontmatter description is missing or empty")
        else:
            if len(desc) > MAX_DESCRIPTION:
                fail(f"description is {len(desc)} chars (max {MAX_DESCRIPTION})")
            if not desc.strip().startswith("Use when"):
                fail("description must start with 'Use when'")

    lines = body.splitlines()
    if len(lines) > MAX_BODY_LINES:
        fail(f"body is {len(lines)} lines (max {MAX_BODY_LINES})")

    # H2 sections, ignoring fenced code blocks.
    h2: list[str] = []
    fenced = False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            h2.append(line.strip())
    present = [h for h in h2 if h in SKILL_SECTIONS]
    missing = [s for s in SKILL_SECTIONS if s not in h2]
    if missing:
        fail("missing section(s): " + ", ".join(missing))
    elif present != SKILL_SECTIONS:
        fail("sections out of order; expected: " + " > ".join(s[3:] for s in SKILL_SECTIONS))

    for n, line in enumerate(lines, 1):
        gate = _APPROVE.search(line)
        if gate and not _PROHIBITION.search(line):
            cmd = gate.group(0).lower()
            fail(f"line {n} instructs running `{cmd}` (only a prohibition/handoff is ok)")

    seen_refs: set[str] = set()
    for ref in _REFERENCE.findall(body):
        if ref not in seen_refs:
            seen_refs.add(ref)
            if not (skill_dir / ref).exists():
                fail(f"broken link: {ref} does not exist")

    mentioned = (m for m in _SKILL_NAME.finditer(text) if not _FILE_EXT.match(text, m.end()))
    for ref_name in dict.fromkeys(m.group(0) for m in mentioned):  # skips e.g. factory-verify.yml
        if ref_name not in all_names:
            fail(f"references unknown skill {ref_name!r}")

    for label, pattern in REQUIRED_RULES.get(name, []):
        if not pattern.search(text):
            fail(f"missing required rule: {label}")

    if "docs/work/" not in text:
        out.append(Finding(WARN, rel, "never mentions docs/work/"))
    return out


def lint_skills(root: Path) -> list[Finding]:
    sdir = root / "skills"
    if not sdir.is_dir():
        return [Finding(FAIL, "skills", "directory is missing")]
    dirs = sorted(p for p in sdir.iterdir() if p.is_dir())
    names = {p.name for p in dirs}
    out: list[Finding] = []
    for d in dirs:
        out.extend(_skill_findings(d, names, root))
    return out


def _stack_set(entry: dict) -> set[str] | None:
    """None means 'all stacks'. Raises ValueError for malformed values."""
    st = entry.get("stack")
    if st is None:
        return None
    vals = [st] if isinstance(st, str) else st
    if not isinstance(vals, list) or not vals:
        raise ValueError(f"stack must be a name or non-empty list, got {st!r}")
    bad = [v for v in vals if v not in STACKS]
    if bad:
        raise ValueError(f"invalid stack value(s) {bad} (allowed: {sorted(STACKS)})")
    return set(vals)


def lint_manifest(root: Path) -> list[Finding]:
    rel = "kit/manifest.yaml"
    path = root / rel
    out: list[Finding] = []

    def fail(reason: str) -> None:
        out.append(Finding(FAIL, rel, reason))

    if not path.is_file():
        return [Finding(FAIL, rel, "file is missing")]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        return [Finding(FAIL, rel, f"does not parse: {str(e).splitlines()[0]}")]
    if not isinstance(data, dict):
        return [Finding(FAIL, rel, "top level must be a mapping")]

    files = data.get("files") or []
    if not isinstance(files, list):
        fail("`files` must be a list")
        files = []
    by_dest: dict[str, list[set[str] | None]] = {}
    for i, e in enumerate(files):
        label = f"files[{i}]"
        if not isinstance(e, dict):
            fail(f"{label} must be a mapping")
            continue
        missing = [k for k in ("src", "dest", "mode") if not e.get(k)]
        if missing:
            fail(f"{label} missing key(s): {', '.join(missing)}")
            continue
        label = f"files[{i}] ({e['dest']})"
        if e["mode"] not in MODES:
            fail(f"{label}: mode {e['mode']!r} not in {sorted(MODES)}")
        if not (root / str(e["src"])).is_file():
            fail(f"{label}: src {e['src']} does not exist")
        try:
            stacks = _stack_set(e)
        except ValueError as ex:
            fail(f"{label}: {ex}")
            continue
        for other in by_dest.get(str(e["dest"]), []):
            if other is None or stacks is None or other & stacks:
                fail(f"{label}: dest shared with another entry whose stacks overlap")
                break
        by_dest.setdefault(str(e["dest"]), []).append(stacks)

    dirs = data.get("dirs") or []
    if not isinstance(dirs, list):
        fail("`dirs` must be a list")
        dirs = []
    for i, e in enumerate(dirs):
        if not isinstance(e, dict) or not e.get("src") or not e.get("dest"):
            fail(f"dirs[{i}] must be a mapping with src and dest")
            continue
        if e.get("mode") not in MODES:
            fail(f"dirs[{i}] ({e['src']}): mode {e.get('mode')!r} not in {sorted(MODES)}")
        d = root / str(e["src"])
        if not d.is_dir():
            fail(f"dirs[{i}]: src dir {e['src']} does not exist")
        elif not any(p.is_file() for p in d.rglob("*")):
            fail(f"dirs[{i}]: src dir {e['src']} is empty")

    tpls = data.get("work_templates") or {}
    if not isinstance(tpls, dict):
        fail("`work_templates` must be a mapping")
        tpls = {}
    for key, p in tpls.items():
        if not isinstance(p, str) or not (root / p).is_file():
            fail(f"work_templates.{key}: {p} does not exist")

    kit_templates = data.get("templates") or {}
    if not isinstance(kit_templates, dict):
        fail("`templates` must be a mapping")
        kit_templates = {}
    for key, p in kit_templates.items():
        if not isinstance(p, str) or not (root / p).is_file():
            fail(f"templates.{key}: {p} does not exist")

    dep = data.get("dependabot_templates")
    if dep is not None or any(
        isinstance(e, dict) and e.get("dest") == _dependabot.DEST for e in files
    ):
        if not isinstance(dep, dict):
            fail("`dependabot_templates` must be a mapping (the manifest lays in dependabot.yml)")
            dep = {}
        for kind in _dependabot.KINDS:
            p = dep.get(kind)
            if not isinstance(p, str) or not (root / p).is_file():
                fail(f"dependabot_templates.{kind}: {p} does not exist")
        allowed = ", ".join(_dependabot.KINDS)
        for kind in sorted(set(dep) - set(_dependabot.KINDS)):
            fail(f"dependabot_templates.{kind}: unknown ecosystem (allowed: {allowed})")
    return out


# The factory is a generic, public tool: instance data (a project registry, tracker hostnames) must
# not creep back into it. docs/work is the factory's own evidence trail and is not scanned.
GENERIC_DIRS = ("docs", "kit", "skills", "policies", "templates")
GENERIC_SKIP = ("docs/work",)
FORBIDDEN_HOST = "atlassian.net"


def lint_generic(root: Path) -> list[Finding]:
    out: list[Finding] = []
    if (root / "registry").exists():
        out.append(
            Finding(
                FAIL,
                "registry/",
                "the project registry must live outside the repo "
                "(FACTORY_REGISTRY or ~/.factory/registry.yaml)",
            )
        )
    for d in GENERIC_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for f in sorted(p for p in base.rglob("*") if p.is_file()):
            rel = f.relative_to(root).as_posix()
            if any(rel == s or rel.startswith(s + "/") for s in GENERIC_SKIP):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if FORBIDDEN_HOST in text:
                out.append(Finding(FAIL, rel, f"contains `{FORBIDDEN_HOST}`: instance data"))
    return out


def lint_factory(root: Path) -> list[Finding]:
    root = Path(root)
    return lint_skills(root) + lint_manifest(root) + lint_generic(root)


def format_lint(findings: list[Finding]) -> list[str]:
    lines = [f"{f.level} {f.name}: {f.detail}" for f in findings if f.level in (FAIL, WARN)]
    nf, nw = len(failures(findings)), sum(f.level == WARN for f in findings)
    if nf:
        lines.append(f"lint: {nf} problem(s), {nw} warning(s)")
    else:
        lines.append("lint: OK" + (f" ({nw} warning(s))" if nw else ""))
    return lines


# =================================================================================================
# doctor
# =================================================================================================

Runner = Callable[[list[str], float], tuple[int, str]]
Which = Callable[[str], str | None]


def run_cmd(argv: list[str], timeout: float = 5) -> tuple[int, str]:
    """Run a command; never raises. Missing binary -> 127, timeout -> 124."""
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""
    except OSError as e:
        return 126, str(e)
    return r.returncode, (r.stdout or r.stderr or "").strip()


def _version(output: str) -> str:
    first = output.splitlines()[0] if output else ""
    m = re.search(r"\d+(?:\.\d+)+", first)
    return m.group(0) if m else ""


# (binary, required)
TOOLS = [
    ("git", True),
    ("gh", False),
    ("uv", True),
    ("node", False),
    ("docker", False),
    ("claude", False),
]


def check_tools(
    which: Which = shutil.which,
    run: Runner = run_cmd,
    python_version: tuple[int, int, int] | None = None,
) -> list[Finding]:
    pv = python_version or tuple(sys.version_info[:3])
    out: list[Finding] = []
    for binary, required in TOOLS:
        found = which(binary)
        if not found:
            out.append(Finding(FAIL if required else WARN, binary, "MISSING"))
            continue
        _, vout = run([binary, "--version"], 5)
        ver = _version(vout)
        detail = ver or "found (version unknown)"
        if binary == "docker":
            rc, _ = run(["docker", "info"], 10)
            if rc != 0:
                out.append(Finding(WARN, "docker", f"{detail} - daemon not responding"))
                continue
        out.append(Finding(OK, binary, detail))
        if binary == "gh":
            rc, _ = run(["gh", "auth", "status"], 10)
            if rc == 0:
                out.append(Finding(OK, "gh auth", "logged in"))
            else:
                out.append(Finding(WARN, "gh auth", "not logged in - run `gh auth login`"))
    pstr = ".".join(map(str, pv))
    if pv >= (3, 12):
        out.append(Finding(OK, "python", pstr))
    else:
        out.append(Finding(FAIL, "python", f"{pstr} - need >= 3.12"))
    return out


def _vtuple(v: object) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])


def adopted_root(start: Path | str = ".") -> Path | None:
    """Nearest ancestor with .factory/factory.yaml, or None."""
    try:
        p = _common.find_project_root(start)
    except FactoryError:
        return None
    return p if (p / ".factory" / "factory.yaml").is_file() else None


def check_project(
    path: Path | str,
    factory_root: Path | None = None,
    current_version: str = __version__,
) -> list[Finding]:
    project = Path(path).resolve()
    cfg_path = project / ".factory" / "factory.yaml"
    if not cfg_path.is_file():
        return [Finding(FAIL, "project", f"not an adopted project (no {cfg_path})")]
    try:
        cfg = _common.load_yaml(cfg_path)
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        return [Finding(FAIL, "factory.yaml", f"does not parse: {str(e).splitlines()[0]}")]
    out: list[Finding] = []

    managed = cfg.get("managed") or {}
    if not isinstance(managed, dict):
        out.append(Finding(FAIL, "factory.yaml", "`managed` must be a mapping"))
        managed = {}
    drifted = 0
    for rel, recorded in managed.items():
        # "<dest>#block" tracks the factory block inside a user-owned file, not a whole file.
        dest, is_block = str(rel).removesuffix("#block"), str(rel).endswith("#block")
        f = project / dest
        if not f.is_file():
            out.append(Finding(FAIL, str(rel), "managed file missing"))
            continue
        if is_block:
            raw = f.read_text(encoding="utf-8")
            if _installer.BEGIN not in raw or _installer.END not in raw:
                out.append(Finding(FAIL, str(rel), "factory block markers missing"))
                continue
            inner = raw[
                raw.index(_installer.BEGIN) + len(_installer.BEGIN) : raw.index(_installer.END)
            ]
            current = _common.sha256_text(_common.normalise_newlines(inner).strip("\n"))
        else:
            current = _common.sha256_file(f)
        if current != recorded:
            drifted += 1
            out.append(Finding(WARN, str(rel), "drifted - `factory sync` will conflict"))
    bad = sum(1 for r in out if r.name in {str(k) for k in managed})
    if not bad:
        out.append(Finding(OK, "managed files", f"{len(managed)} tracked, all present, unmodified"))

    skills_root = (factory_root / "skills") if factory_root else _common.skills_dir()
    wanted = (
        sorted(p.name for p in skills_root.iterdir() if (p / "SKILL.md").is_file())
        if skills_root.is_dir()
        else []
    )
    targets = cfg.get("skill_targets") or []
    for t in targets:
        have = [n for n in wanted if (project / str(t) / n).is_dir()]
        gone = [n for n in wanted if n not in have]
        if gone:
            out.append(
                Finding(WARN, f"skills {t}", f"missing {', '.join(gone)} - run factory sync")
            )
        else:
            out.append(Finding(OK, f"skills {t}", f"{len(wanted)} present"))

    fv = cfg.get("factory_version")
    if fv is None or not _vtuple(fv):
        out.append(Finding(WARN, "factory_version", f"missing or unreadable ({fv!r})"))
    elif _vtuple(fv) < _vtuple(current_version):
        out.append(Finding(WARN, "factory_version", f"{fv} is older than {current_version}"))
    else:
        out.append(Finding(OK, "factory_version", str(fv)))

    if _common.is_git_repo(project):
        out.append(Finding(OK, "git", "repository found"))
    else:
        out.append(Finding(WARN, "git", "no .git directory - not a git repository"))
    return out


def check_protections(root: Path | str, gh: _harden.Gh | None = None) -> list[Finding]:
    """The four repository protections (FACT-33): ok / off / unknown, plus not available.

    `off` fails on a public repo (a protection that was never turned on or was turned off), warns
    on a private one. `unknown` (gh unusable, no admin) and `not available` only warn: this check
    cannot tell whether the protection is missing. A project with no GitHub remote has nothing on
    GitHub to check: one OK line says it was skipped."""
    try:
        owner, repo = _harden.repo_slug(root)
    except FactoryError:
        return [Finding(OK, "repo protections", "skipped (no github.com origin remote)")]
    state = _harden.read_state(owner, repo, gh or _harden.gh_api)
    out: list[Finding] = []
    for p in state.protections:
        detail = p.state + (f" ({p.detail})" if p.detail else "")
        if p.state == _harden.OK:
            level = OK
        elif p.state == _harden.OFF:
            level = FAIL if state.private is False else WARN
            detail += " - `factory harden` turns it on"
        else:
            level = WARN
        out.append(Finding(level, f"repo: {_harden.LABELS[p.key]}", detail))
    return out


def check_dependencies(
    root: Path | str, gh: _harden.Gh | None = None, now: datetime | None = None
) -> list[Finding]:
    """The dependency summary of `factory status` as doctor findings (FACT-39).

    Never FAIL: a critical or high alert, a failed Dependabot Updates run and a part that could
    not be read are warnings, the rest is OK. A project with no github.com remote has nothing to
    read: one OK line says it was skipped, and no call is made."""
    summary = _deps.for_project(root, gh, now)
    if summary is None:
        return [Finding(OK, "dependencies", "skipped (no github.com origin remote)")]
    return [Finding(WARN if p.warn else OK, f"deps: {p.name}", p.detail) for p in summary.parts()]


def check_decisions(root: Path | str, today: date | None = None) -> list[Finding]:
    """Decision records waiting for the owner (FACT-46), one WARN each; an invalid record is a WARN
    too (`factory verify` is what fails on it). Nothing waiting: no finding at all."""
    today = today or _decisions.today_date()
    out: list[Finding] = []
    for rec in _decisions.load_records(root):
        name = f"decision {rec.id}"
        if rec.problems:
            reasons = "; ".join(rec.problems)
            out.append(Finding(WARN, name, f"invalid: {reasons} - `factory verify` fails on it"))
        elif rec.waiting:
            age = _decisions.age_text(_decisions.age_days(rec, today))
            title = _common.ascii_line(rec.title, _decisions.TEXT_MAX)
            rec_text = _common.ascii_line(rec.recommended, _decisions.TEXT_MAX)
            detail = (
                f"{rec.type}, waiting {age}: {title} (recommended: {rec_text})"
                f"{' [draft]' if rec.draft else ''} - the owner runs `factory decide {rec.id}`"
            )
            out.append(Finding(WARN, name, detail))
    return out


def check_charter(root: Path | str) -> list[Finding]:
    """The project charter (FACT-47): OK when approved, else one WARN saying why. Never FAIL."""
    st = _charter.charter_state(root)
    if st.state == "approved":
        return [Finding(OK, "charter", f"approved by {st.decision} ({st.mode})")]
    return [Finding(WARN, "charter", f"no approved charter: {st.detail}")]


SONAR_PLACEHOLDER = _installer.SONAR_PLACEHOLDER
SONAR_SECRET = "SONAR_TOKEN"
SONAR_PROPERTIES = "sonar-project.properties"
# One page of the repository secret list; a name past it is "unknown", not absent.
SECRETS_PAGE = 100

_PRESENT, _ABSENT, _UNKNOWN, _SKIPPED = "present", "absent", "unknown", "skipped"


def sonar_placeholders(text: str) -> list[str]:
    """Keys of the non-comment lines of a properties file that still hold the placeholder."""
    keys: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and SONAR_PLACEHOLDER in s:
            keys.append(re.split(r"[=:]", s, maxsplit=1)[0].strip())
    return keys


def _sonar_secret(root: Path, gh: _harden.Gh) -> tuple[str, str]:
    """(state, detail) of the repository Actions secret. Reads the secret NAMES only: the endpoint
    never returns a value and nothing but a name is looked at. Failures carry the status only."""
    try:
        owner, repo = _harden.repo_slug(root)
    except FactoryError:
        return _SKIPPED, "skipped (no github.com origin remote)"
    status, data = gh("GET", f"repos/{owner}/{repo}/actions/secrets?per_page={SECRETS_PAGE}", None)
    if status == 0:
        return _UNKNOWN, "unknown (gh unavailable)"
    if status != 200 or not isinstance(data, dict):
        return _UNKNOWN, f"unknown (HTTP {status})"
    listed = data.get("secrets") if isinstance(data.get("secrets"), list) else []
    if SONAR_SECRET in {s.get("name") for s in listed if isinstance(s, dict)}:
        return _PRESENT, "present (name only; its value is never read)"
    total = data.get("total_count")
    if isinstance(total, int) and total > len(listed):
        return _UNKNOWN, f"unknown (more than {SECRETS_PAGE} secrets; not all were listed)"
    return _ABSENT, f"not set - the scan is skipped; the owner runs `gh secret set {SONAR_SECRET}`"


SONAR_SERVER = "sonar: server"
_FREE_PLAN = (
    "project not found or not public: on the free plan the SonarCloud project must be public, and "
    "anonymous access cannot tell a private project from a missing one (docs/sonarcloud.md)"
)


def _github_default_branch(owner: str, repo: str, gh: _harden.Gh) -> tuple[str | None, str]:
    status, data = gh("GET", f"repos/{owner}/{repo}", None)
    if status == 0:
        return None, "the repository default branch is unreadable: gh unavailable"
    if status != 200:
        return None, f"the repository default branch is unreadable: HTTP {status}"
    name = data.get("default_branch") if isinstance(data, dict) else None
    if not _sonar.valid_branch(name):
        return None, "the repository default branch is unreadable: unexpected answer"
    return name, ""


def _server_finding(key: str, default: str, project: _sonar.Project) -> Finding:
    if project.state == _sonar.UNKNOWN:
        return Finding(WARN, SONAR_SERVER, f"unknown ({project.detail})")
    if project.state == _sonar.NOT_FOUND:
        return Finding(WARN, SONAR_SERVER, _FREE_PLAN)
    if project.main == default:
        detail = f"public; main branch '{default}' matches the repository default branch"
        return Finding(OK, SONAR_SERVER, detail)
    fix = " ; ".join(_sonar.repair_commands(key, default, project))
    detail = (
        f"main branch is '{project.main}' but the repository default branch is '{default}', so "
        f"scans of '{default}' are side-branch analyses with no readable data. Repair, with a "
        f"token in $SONAR_TOKEN (docs/sonarcloud.md): {fix}"
    )
    return Finding(WARN, SONAR_SERVER, detail)


def _sonar_tests(props_text: str) -> Finding:
    """`sonar.tests` set? Without it the scanner only guesses test files from their names and warns
    that rules for production code were not run on them (FACT-40)."""
    if _sonar.property_value(props_text, "sonar.tests"):
        return Finding(OK, "sonar: tests", "sonar.tests is set")
    detail = (
        "sonar.tests is not set: test files are guessed from their names; add `sonar.tests=.` "
        "beside sonar.sources (docs/sonarcloud.md)"
    )
    return Finding(WARN, "sonar: tests", detail)


def _sonar_server(
    root: Path, props_text: str, gh: _harden.Gh, fetch: _sonar.Fetch, placeholders: list[str]
) -> Finding:
    """Does the SonarCloud project exist, is it public, is its main branch the repository default
    branch? Anonymous, read-only; no call while setup has not started or without a GitHub remote."""
    if placeholders:
        return Finding(
            OK, SONAR_SERVER, f"skipped (setup has not started: {SONAR_PLACEHOLDER} left)"
        )
    try:
        owner, repo = _harden.repo_slug(root)
    except FactoryError:
        return Finding(OK, SONAR_SERVER, "skipped (no github.com origin remote)")
    key = _sonar.property_value(props_text, "sonar.projectKey")
    if key is None:
        return Finding(WARN, SONAR_SERVER, "unknown (no sonar.projectKey in the properties file)")
    default, why = _github_default_branch(owner, repo, gh)
    if default is None:
        return Finding(WARN, SONAR_SERVER, f"unknown ({why})")
    return _server_finding(key, default, _sonar.read_project(key, fetch))


def check_sonar(
    root: Path | str, gh: _harden.Gh | None = None, fetch: _sonar.Fetch | None = None
) -> list[Finding]:
    """SonarCloud setup (FACT-35): is the secret there, is the properties file still a template?
    And (FACT-40) does the SonarCloud project exist, is it public, is its main branch the
    repository default branch (public API, no token).

    Never FAIL: Sonar is optional. A project with neither Sonar file gets one OK notice and no
    GitHub call. While the placeholder remains, a missing secret is only a notice (setup has not
    started); a missing secret with filled properties, a placeholder with the secret set, and an
    unreadable secret list are warnings."""
    root = Path(root)
    props = root / SONAR_PROPERTIES
    if not props.is_file() and not (root / _installer.SONAR_WORKFLOW_DEST).is_file():
        note = "not configured (optional; docs/sonarcloud.md in the factory repo)"
        return [Finding(OK, "sonar", note)]
    gh = gh or _harden.gh_api
    state, secret_detail = _sonar_secret(root, gh)
    props_text = props.read_text(encoding="utf-8", errors="replace") if props.is_file() else ""
    keys = sonar_placeholders(props_text)
    if not props.is_file():
        props_finding = Finding(
            WARN, "sonar: properties", f"{SONAR_PROPERTIES} is missing; the scan is skipped"
        )
    elif keys:
        level = WARN if state == _PRESENT else OK
        left = ", ".join(keys)
        detail = f"still has {SONAR_PLACEHOLDER} in {left}; the scan is skipped until set"
        props_finding = Finding(level, "sonar: properties", detail)
    else:
        props_finding = Finding(OK, "sonar: properties", "no placeholder left")
    secret_level = {
        _PRESENT: OK,
        _SKIPPED: OK,
        _ABSENT: OK if keys else WARN,
        _UNKNOWN: WARN,
    }[state]
    found = [props_finding, Finding(secret_level, f"sonar: {SONAR_SECRET}", secret_detail)]
    if props.is_file():
        found.append(_sonar_tests(props_text))
        found.append(_sonar_server(root, props_text, gh, fetch or _sonar.http_get, keys))
    return found


def format_findings(findings: list[Finding]) -> list[str]:
    return [f"{f.level:<5} {f.name:<28} {f.detail}" for f in findings]
