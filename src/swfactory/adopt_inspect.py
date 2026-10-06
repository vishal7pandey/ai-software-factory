"""Look at a project before `factory adopt` writes anything (FACT-12).

Plain functions, no plugin system. The command runner is injectable so tests never need uv or npm.
Everything printed here is ASCII-only (Windows consoles).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from swfactory import common

BEGIN = "<!-- factory:begin -->"
END = "<!-- factory:end -->"
CI_DEST = ".github/workflows/ci.yml"
STEP_TIMEOUT = 600  # seconds per CI step run locally

Runner = Callable[[str, Path], tuple[int, str]]


@dataclass
class Inspection:
    default_branch: str | None
    findings: list[str] = field(default_factory=list)
    has_commands_section: bool = False
    detected_commands: list[str] = field(default_factory=list)


@dataclass
class CiReport:
    dropped: list[tuple[str, str]] = field(default_factory=list)  # (command, last output line)
    ran: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"{CI_DEST}: removed failing step `{c}` ({why})" for c, why in self.dropped]
        out += [f"{CI_DEST}: {n}" for n in self.notes]
        if self.ran and not self.dropped and not self.notes:
            out.append(f"{CI_DEST}: all {len(self.ran)} step(s) passed locally")
        return out


def _ascii(text: str, limit: int = 160) -> str:
    return text.encode("ascii", "replace").decode("ascii")[:limit]


_FAILURE_WORDS = re.compile(r"\b(errors?|fail(?:ed|ures?)?|found)\b", re.IGNORECASE)


def _last_line(output: str) -> str:
    """The most telling line: the last one that mentions an error or failure, else the last line."""
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    if not lines:
        return "no output"
    telling = [ln for ln in lines if _FAILURE_WORDS.search(ln)]
    return _ascii((telling or lines)[-1])


# --- default branch and workflow triggers ---------------------------------------------------------


def default_branch(root: Path) -> str | None:
    """origin/HEAD if known, else the current branch, else None."""
    if not common.is_git_repo(root):
        return None
    ref = common.git(
        "symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD", cwd=root, check=False
    )
    if ref:
        return ref.removeprefix("origin/")
    return common.git("symbolic-ref", "--short", "-q", "HEAD", cwd=root, check=False) or None


def _branch_list(value) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return None


def trigger_findings(root: Path, branch: str | None) -> list[str]:
    """Existing workflows whose push/pull_request branch filters do not cover the default branch."""
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    out: list[str] = []
    for f in sorted([*wf_dir.glob("*.yml"), *wf_dir.glob("*.yaml")]):
        rel = f.relative_to(root).as_posix()
        if f.name in ("factory-verify.yml", "factory-verify.yaml"):
            continue
        try:
            wf = yaml.safe_load(f.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError, UnicodeDecodeError):
            out.append(f"{rel}: could not be parsed, triggers not checked")
            continue
        if not branch or not isinstance(wf, dict):
            continue
        on = wf.get("on", wf.get(True))  # PyYAML reads the key `on` as True
        if not isinstance(on, dict):
            continue
        for event in ("push", "pull_request"):
            cfg = on.get(event)
            names = _branch_list(cfg.get("branches")) if isinstance(cfg, dict) else None
            if names and not any(fnmatch.fnmatchcase(branch, pat) for pat in names):
                out.append(
                    f"{rel}: `{event}` runs only on {', '.join(names)}, "
                    f"but the default branch is {branch}"
                )
    return out


# --- AGENTS.md commands section and detected commands ---------------------------------------------

_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.DOTALL | re.MULTILINE)
_HEADING = re.compile(
    r"^#{1,6}\s+.*\b(commands?|build|tests?|testing|run|running|develop|development|scripts?)\b",
    re.IGNORECASE | re.MULTILINE,
)
MAKE_TARGETS = ("install", "build", "test", "lint", "format", "fmt", "check", "run", "dev", "start")


def has_commands_section(agents_text: str) -> bool:
    """A heading about commands, outside code fences and outside the factory block."""
    text = common.normalise_newlines(agents_text)
    if BEGIN in text and END in text and text.index(BEGIN) < text.index(END):
        text = text[: text.index(BEGIN)] + text[text.index(END) + len(END) :]
    return bool(_HEADING.search(_FENCE.sub("", text)))


def detect_commands(root: Path) -> list[str]:
    out: list[str] = []
    makefile = root / "Makefile"
    if makefile.is_file():
        text = makefile.read_text(encoding="utf-8", errors="replace")
        targets = dict.fromkeys(re.findall(r"^([A-Za-z][\w-]*)\s*:(?!=)", text, re.MULTILINE))
        out += [f"make {t}" for t in targets if t in MAKE_TARGETS]
    package = root / "package.json"
    if package.is_file():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts") or {}
        except (ValueError, OSError):
            scripts = {}
        names = [n for n in scripts if isinstance(n, str)][:10]
        out += ["npm test" if n == "test" else f"npm run {n}" for n in names]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            raw = pyproject.read_text(encoding="utf-8")
            tools = (tomllib.loads(raw).get("tool") or {}).keys()
        except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
            raw, tools = "", ()
        if (root / "uv.lock").is_file() or "uv" in tools:
            out.append("uv sync --all-extras --all-groups")
        if "ruff" in tools:
            out += ["uv run ruff check .", "uv run ruff format --check ."]
        if "pytest" in tools or "pytest" in raw:
            out.append("uv run pytest -q")
    return list(dict.fromkeys(out))


def todo_section(commands: list[str]) -> str:
    """The text inserted above the factory block. Ends with a blank line."""
    lines = ["## Commands (TODO: confirm)", ""]
    if commands:
        lines += ["Detected by `factory adopt`, not verified. Edit or replace.", ""]
        lines += [f"* `{c}`" for c in commands]
    else:
        lines += [
            "`factory adopt` found no build, test or lint commands. Write them here: agents and",
            "the factory skills read this section.",
        ]
    return "\n".join(lines) + "\n\n"


def inspect_project(root: Path) -> Inspection:
    branch = default_branch(root)
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    return Inspection(
        default_branch=branch,
        findings=trigger_findings(root, branch),
        has_commands_section=has_commands_section(text),
        detected_commands=detect_commands(root),
    )


# --- the generated CI -----------------------------------------------------------------------------

_RUN = re.compile(r"^(\s*)-\s+run:\s*(\S.*?)\s*$")
_INSTALL = re.compile(r"^(uv sync|npm ci|npm install|pip install)\b")
_BRANCH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def project_env() -> dict[str, str]:
    """The environment for a project's own commands: ours minus the active virtualenv, so that
    `uv run` inside the project uses the project's environment and not the factory's."""
    return {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}


def run_shell(cmd: str, cwd: Path) -> tuple[int, str]:
    """Run one fixed template command. Never raises. 127 = tool missing, 124 = timeout."""
    tool = cmd.split()[0]
    if shutil.which(tool) is None:
        return 127, f"{tool} not found on PATH"
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            env=project_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STEP_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {STEP_TIMEOUT}s"
    except OSError as e:
        return 126, str(e)
    return r.returncode, (r.stdout + "\n" + r.stderr).strip()


def point_at_branch(content: str, branch: str | None) -> str:
    """Point a template's push trigger at the default branch (unchanged for `main` or a name that is
    not a plain branch name)."""
    if branch and branch != "main" and _BRANCH_NAME.match(branch):
        return content.replace("branches: [main]", f"branches: [{branch}]")
    return content


def adapt_ci(
    content: str,
    branch: str | None,
    root: Path,
    *,
    check: bool,
    runner: Runner | None = None,
) -> tuple[str, CiReport]:
    """Point the push trigger at the default branch, then (if `check`) run the `run:` steps locally
    and drop the ones that fail. Install steps are never dropped: if they fail, the report says the
    checks could not run."""
    report = CiReport()
    if branch and branch != "main":
        if _BRANCH_NAME.match(branch):
            content = content.replace("branches: [main]", f"branches: [{branch}]")
        else:
            report.notes.append(f"default branch {_ascii(branch)!r} not used in the push trigger")
    if not check:
        return content, report
    runner = runner or run_shell
    out: list[str] = []
    stopped = False
    for line in content.split("\n"):
        m = _RUN.match(line)
        if stopped or not m:
            out.append(line)
            continue
        indent, cmd = m.group(1), m.group(2)
        code, output = runner(cmd, root)
        if code == 0:
            report.ran.append(cmd)
            out.append(line)
        elif code == 127 or _INSTALL.match(cmd):
            why = "tool missing" if code == 127 else "dependency install failed"
            report.notes.append(
                f"checks could not run ({why}: `{cmd}`: {_last_line(output)}); "
                "CI left as the template"
            )
            out.append(line)
            stopped = True
        else:
            why = _last_line(output)
            report.dropped.append((cmd, why))
            out.append(
                f"{indent}# factory adopt: removed `{cmd}` because it failed locally; re-add it"
            )
            out.append(f"{indent}# once it passes. Last output: {why}")
    return "\n".join(out), report
