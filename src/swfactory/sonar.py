"""SonarCloud in an adopted project (FACT-40): render the create-mode files from the project, and
read the SonarCloud project through its public API.

Two independent halves, both plain functions:

* `render_workflow` / `render_properties` turn the kit templates into files that fit THIS project
  when `adopt` or `sync` creates them: the default branch, the project's own test command and the
  python version of its CI. They never guess: what is not understood keeps the template text.
* `read_project` asks SonarCloud (anonymous GET, no token) whether the project exists, is public and
  has the repository's default branch as its main branch. Network access goes through ONE function,
  `_request`, which the test suite replaces (conftest), like `harden._run_gh`.

Output is ASCII-only (Windows consoles).
"""

from __future__ import annotations

import json
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from swfactory import adopt_inspect

PROPERTIES_DEST = "sonar-project.properties"
DEFAULT_PYTHON = "3.12"
XML_REPORT = "--cov-report=xml:coverage.xml"
LOCKED_RUN = "uv run --locked --no-sync python -m pytest"
STEP_NAME = (
    "Tests with coverage (the project's own command from ci.yml, plus the XML report for Sonar)"
)


# --- rendering the create-mode files -----------------------------------------------------------


def _logical_lines(run: str) -> list[str]:
    """The commands of a `run:` value: one per line, `\\` continuations joined, comments dropped."""
    out: list[str] = []
    pending = ""
    for raw in run.splitlines():
        piece = raw.strip()
        joined = f"{pending} {piece}".strip() if pending else piece
        if joined.endswith("\\"):
            pending = joined[:-1].rstrip()
            continue
        pending = ""
        if joined and not joined.startswith("#"):
            out.append(joined)
    if pending:
        out.append(pending)
    return out


_PYTEST = re.compile(r"(?<![\w.-])(?:pytest|py\.test)(?![\w-])")
_SHELL = re.compile(r"&&|\|\||[;|<>`$]")
# `uv run` options that take a separate value (their value is not the command).
_UV_VALUE_FLAGS = frozenset(
    {
        "--with",
        "--with-requirements",
        "--with-editable",
        "--extra",
        "--group",
        "--only-group",
        "--no-group",
        "--python",
        "-p",
        "--package",
        "--project",
        "--directory",
        "--env-file",
        "--index",
        "--index-url",
        "--default-index",
        "--config-file",
        "--cache-dir",
        "--isolated-from",
    }
)


def _pytest_arguments(line: str) -> str | None:
    """What follows `pytest` in `[uv run <options>] pytest ...` or `... python -m pytest ...`;
    None when the runner is anything else (poetry, tox, make, `uv pip`)."""
    words = list(re.finditer(r"\S+", line))
    texts = [m.group() for m in words]
    i = 0
    if texts[:2] == ["uv", "run"]:
        i = 2
        while i < len(texts) and texts[i].startswith("-"):
            i += 2 if texts[i] in _UV_VALUE_FLAGS else 1
    if i < len(texts) and texts[i] in ("pytest", "py.test"):
        start = i + 1
    elif texts[i : i + 3] in (["python", "-m", "pytest"], ["python3", "-m", "pytest"]):
        start = i + 3
    else:
        return None
    return line[words[start].start() :] if start < len(words) else ""


def _with_coverage(arguments: str, *, locked: bool) -> str:
    """The locked runner plus the original arguments plus the coverage options that are missing.
    `--cov` goes last: it takes an optional value and would swallow a following path."""
    words = arguments.split()
    parts = [LOCKED_RUN if locked else LOCKED_RUN.replace("--locked ", "")]
    if arguments:
        parts.append(arguments)
    if not any(w == "--cov" or w.startswith("--cov=") for w in words):
        parts.append("--cov")
    if not any(w in ("--cov-report=xml", XML_REPORT) for w in words):
        parts.append(XML_REPORT)
    return " ".join(parts)


def _step_problem(line: str, step: dict, job: dict, doc: dict) -> str | None:
    """Why this command cannot be copied into another workflow as it is, or None."""
    if "${{" in line:
        return "the command has a GitHub expression (never copied into a script)"
    if _SHELL.search(line):
        return "the command has a shell operator or variable"
    for scope in (step, job, doc):
        defaults = scope.get("defaults")
        run_defaults = defaults.get("run") if isinstance(defaults, dict) else None
        if "working-directory" in scope or (
            isinstance(run_defaults, dict) and "working-directory" in run_defaults
        ):
            return "the step runs in a working-directory"
    if any(scope.get("env") for scope in (step, job, doc)):
        return "the step runs with env variables the Sonar job would not have"
    return None


def _pytest_candidates(doc: dict) -> list[tuple[str, dict, dict]]:
    out: list[tuple[str, dict, dict]] = []
    jobs = doc.get("jobs")
    for job in jobs.values() if isinstance(jobs, dict) else []:
        steps = job.get("steps") if isinstance(job, dict) else None
        for step in steps if isinstance(steps, list) else []:
            run = step.get("run") if isinstance(step, dict) else None
            if isinstance(run, str):
                out += [(ln, step, job) for ln in _logical_lines(run) if _PYTEST.search(ln)]
    return out


def test_command(ci_text: str | None, *, locked: bool) -> tuple[str | None, str]:
    """(the project's own pytest command made fit for the Sonar job, note).

    The command is None, with the reason in the note, whenever it cannot be reused safely; the
    caller then keeps the template's step. On success the note may still say something (several
    pytest steps)."""
    if ci_text is None:
        return None, "no ci.yml to take the test command from"
    try:
        doc = yaml.safe_load(ci_text)
    except yaml.YAMLError:
        return None, "ci.yml does not parse"
    candidates = _pytest_candidates(doc) if isinstance(doc, dict) else []
    if not candidates:
        return None, "no pytest step in ci.yml"
    reason = ""
    for line, step, job in candidates:
        problem = _step_problem(line, step, job, doc)
        arguments = _pytest_arguments(line) if problem is None else None
        if problem is None and arguments is None:
            problem = "the runner is not uv run, python -m pytest or pytest"
        if problem is None and arguments is not None:
            extra = f"{len(candidates)} pytest steps in ci.yml; took the first usable one"
            return _with_coverage(arguments, locked=locked), extra if len(candidates) > 1 else ""
        reason = reason or problem or ""
    return None, reason


def _versions_in(text: str) -> list[str]:
    found: list[str] = []
    lines = text.splitlines()
    for n, raw in enumerate(lines):
        line = raw.split("#", 1)[0]
        if "python-version:" in line:
            found += re.findall(r"\d+\.\d+", line.split("python-version:", 1)[1])
            if not line.split("python-version:", 1)[1].strip():  # a block list on the next lines
                for follow in lines[n + 1 :]:
                    item = follow.split("#", 1)[0].strip()
                    if not item.startswith("-"):
                        break
                    found += re.findall(r"\d+\.\d+", item)
        found += re.findall(r"uv python install\s+(\d+\.\d+)", line)
        found += re.findall(r"--python[ =]+(\d+\.\d+)", line)
    return found


def ci_python_versions(ci_text: str | None) -> list[str]:
    """The python versions a CI file names, in order, without repeats."""
    return list(dict.fromkeys(_versions_in(ci_text or "")))


def python_versions(ci_text: str | None, pyproject_text: str | None) -> list[str]:
    """CI first, else the lower bound of `requires-python`, else the kit default."""
    found = ci_python_versions(ci_text)
    if found:
        return found
    try:
        project = (tomllib.loads(pyproject_text or "").get("project")) or {}
    except tomllib.TOMLDecodeError:
        project = {}
    requires = project.get("requires-python") if isinstance(project, dict) else None
    bound = (
        re.search(r"(?:>=|~=|===?|>)\s*(\d+\.\d+)", requires) if isinstance(requires, str) else None
    )
    return [bound.group(1)] if bound else [DEFAULT_PYTHON]


def _folded(command: str, indent: int = 10, width: int = 100) -> list[str]:
    """`command` wrapped for a YAML folded scalar; quoted strings are never split."""
    lines: list[str] = []
    current = ""
    for token in re.findall(r"""(?:"[^"]*"|'[^']*'|\S)+""", command):
        if current and indent + len(current) + 1 + len(token) > width:
            lines.append(current)
            current = token
        else:
            current = f"{current} {token}".strip()
    return [" " * indent + ln for ln in [*lines, current]]


_TEST_STEP = re.compile(
    r"^(      - name: )Tests with coverage[^\n]*\n(        if: [^\n]*\n)        run: [^\n]*\n",
    re.MULTILINE,
)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    except OSError:
        return None


def render_workflow(
    content: str,
    *,
    stack: str,
    root: Path,
    ci_text: str | None,
    branch: str | None,
) -> tuple[str, list[str]]:
    """The new `sonar.yml` for this project and the notes to print (each says what was decided)."""
    notes: list[str] = []
    pointed = adopt_inspect.point_at_branch(content, branch)
    if pointed == content and branch not in (None, "main"):
        notes.append(
            f"the default branch {branch!r} is not a plain name: the push trigger stays main"
        )
    content = pointed
    if stack != "python":
        return content, notes
    locked = (root / "uv.lock").is_file()
    if not locked:
        content = content.replace("uv sync --locked", "uv sync").replace(
            "uv run --locked", "uv run"
        )
    pyproject = _read(root / "pyproject.toml")
    versions = python_versions(ci_text, pyproject)
    content = content.replace(
        f'python-version: "{DEFAULT_PYTHON}"', f'python-version: "{versions[0]}"'
    )
    command, why = test_command(ci_text, locked=locked)
    if command is None:
        notes.append(
            f"test step left as the template ({why}): adapt it to the project's own test command"
        )
    else:
        body = "\n".join(_folded(command))

        def step(m: re.Match[str]) -> str:
            return f"{m.group(1)}{STEP_NAME}\n{m.group(2)}        run: >-\n{body}\n"

        content = _TEST_STEP.sub(step, content, count=1)
        taken = f"test step taken from {adopt_inspect.CI_DEST}; python {', '.join(versions)}"
        notes.append(f"{taken} ({why})" if why else taken)
    if pyproject is not None and not re.search(r"pytest[-_]cov", pyproject, re.IGNORECASE):
        notes.append(
            "pytest-cov is not in pyproject.toml: add it to the locked dev group "
            "(uv add --dev pytest-cov) or the coverage step fails"
        )
    return content, notes


def render_properties(content: str, *, stack: str, root: Path, ci_text: str | None) -> str:
    """The new `sonar-project.properties`: `sonar.python.version` follows the project's CI."""
    if stack != "python":
        return content
    versions = python_versions(ci_text, _read(root / "pyproject.toml"))
    return content.replace(
        f"sonar.python.version={DEFAULT_PYTHON}", f"sonar.python.version={','.join(versions)}"
    )


# --- reading the SonarCloud project (doctor) ---------------------------------------------------

API = "https://sonarcloud.io/api"
REQUEST_TIMEOUT = 20  # seconds

# (status, parsed JSON or None). Status 0 means SonarCloud could not be reached at all.
Fetch = Callable[[str], "tuple[int, Any]"]

_PLAIN_KEY = re.compile(r"^[A-Za-z0-9_.:-]+$")
_PLAIN_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _request(url: str) -> tuple[int, str]:
    """The only place that opens a connection: an anonymous GET of the public SonarCloud API.
    Never raises; 0 means unreachable, anything else the HTTP status."""
    if not url.startswith(API + "/"):
        return 0, ""
    req = urllib.request.Request(
        url, method="GET", headers={"Accept": "application/json", "User-Agent": "swfactory-doctor"}
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (OSError, ValueError):  # URLError, timeouts, resets are all OSError
        return 0, ""


def http_get(url: str) -> tuple[int, Any]:
    status, text = _request(url)
    try:
        return status, json.loads(text) if text.strip() else None
    except ValueError:
        return status, None


def property_value(text: str, key: str) -> str | None:
    """The value of `key` in a `.properties` text (comment lines ignored), or None."""
    for line in text.splitlines():
        m = re.match(r"^([^=:\s#][^=:\s]*)\s*[=:]\s*(.*)$", line.strip())
        if m and m.group(1) == key:
            return m.group(2).strip()
    return None


@dataclass(frozen=True)
class Project:
    state: str  # OK | NOT_FOUND | UNKNOWN
    detail: str = ""
    main: str | None = None
    side_branches: tuple[str, ...] = ()


OK, NOT_FOUND, UNKNOWN = "ok", "not-found", "unknown"


def _unreachable(status: int) -> Project:
    return Project(UNKNOWN, "SonarCloud unreachable" if status == 0 else f"HTTP {status}")


def read_project(key: str, fetch: Fetch) -> Project:
    """Does the project exist, is it public, which branch is its main branch? Never raises, never
    sends a token, and prints nothing from a response body."""
    if not _PLAIN_KEY.match(key):
        return Project(UNKNOWN, "sonar.projectKey is not a plain key")
    quoted = urllib.parse.quote(key, safe="")
    status, data = fetch(f"{API}/components/show?component={quoted}")
    if status == 404:
        return Project(NOT_FOUND)
    if status != 200:
        return _unreachable(status)
    component = data.get("component") if isinstance(data, dict) else None
    visibility = component.get("visibility") if isinstance(component, dict) else None
    if not isinstance(visibility, str):
        return Project(UNKNOWN, "unexpected answer (no visibility)")
    if visibility != "public":
        return Project(NOT_FOUND, f"visibility is {visibility}")
    status, data = fetch(f"{API}/project_branches/list?project={quoted}")
    if status != 200:
        return _unreachable(status)
    listed = data.get("branches") if isinstance(data, dict) else None
    branches = [b for b in listed if isinstance(b, dict)] if isinstance(listed, list) else []
    mains = [b.get("name") for b in branches if b.get("isMain") is True]
    if len(mains) != 1 or not isinstance(mains[0], str):
        return Project(UNKNOWN, "unexpected answer (no single main branch)")
    side = tuple(
        b["name"]
        for b in branches
        if b.get("isMain") is not True and isinstance(b.get("name"), str)
    )
    return Project(OK, main=mains[0], side_branches=side)


def valid_branch(name: object) -> bool:
    return isinstance(name, str) and bool(_PLAIN_BRANCH.match(name))


def repair_commands(key: str, default: str, project: Project) -> list[str]:
    """The calls that make the SonarCloud main branch `default`: delete the side branch of that
    name (only when one exists), then rename the main branch. The token comes from $SONAR_TOKEN."""
    base = f'curl -s -X POST -u "$SONAR_TOKEN:" "{API}/project_branches'
    q_key, q_branch = urllib.parse.quote(key, safe=""), urllib.parse.quote(default, safe="")
    out: list[str] = []
    if default in project.side_branches:
        out.append(f'{base}/delete?project={q_key}&branch={q_branch}"')
    out.append(f'{base}/rename?project={q_key}&name={q_branch}"')
    return out
