"""`factory harden`: enable and check the repository-level protections of a GitHub-hosted project.

Four protections: secret scanning with push protection, Dependabot alerts, Dependabot security
updates, CodeQL default setup. All GitHub access goes through ONE function, `gh_api`, so tests
replace it and never touch the network. Failures are reported by HTTP status only: a response body
is parsed for state on reads and is never printed. Output is ASCII-only (Windows consoles).
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from swfactory import common, installer
from swfactory.common import FactoryError

GH_TIMEOUT = 30  # seconds per `gh api` call

# (status, parsed JSON body or None). Status 0 means gh could not be used at all (not installed, not
# logged in, timed out, unparseable output).
Gh = Callable[[str, str, "dict | None"], "tuple[int, Any]"]

_STATUS_LINE = re.compile(r"^HTTP/\S+\s+(\d{3})")
_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _run_gh(argv: list[str], stdin: str | None) -> tuple[int, str]:
    """The only place that starts a process. Never raises; a missing binary or timeout -> 127."""
    try:
        r = subprocess.run(
            ["gh", *argv],
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return r.returncode, r.stdout or ""


def parse_response(text: str) -> tuple[int, Any]:
    """`gh api -i` output (status line, headers, blank line, body) -> (status, JSON or None)."""
    text = common.normalise_newlines(text).lstrip()
    m = _STATUS_LINE.match(text)
    if not m:
        return 0, None
    _, _, body = text.partition("\n\n")
    try:
        data = json.loads(body) if body.strip() else None
    except ValueError:
        data = None
    return int(m.group(1)), data


def gh_api(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    """Call the GitHub REST API through `gh api`. The body, if any, goes in on stdin as JSON."""
    argv = ["api", "-i", "-X", method, path]
    if body is not None:
        argv += ["--input", "-"]
    _, out = _run_gh(argv, json.dumps(body) if body is not None else None)
    return parse_response(out)


# --- state ----------------------------------------------------------------------------------------

OK, OFF, UNAVAILABLE, UNKNOWN = "ok", "off", "not available", "unknown"

SECRET, ALERTS, UPDATES, CODEQL = (
    "secret-scanning",
    "dependabot-alerts",
    "dependabot-updates",
    "code-scanning",
)
KEYS = (SECRET, ALERTS, UPDATES, CODEQL)  # apply order: alerts must be on before security updates
LABELS = {
    SECRET: "secret scanning + push protection",
    ALERTS: "dependabot alerts",
    UPDATES: "dependabot security updates",
    CODEQL: "codeql default setup",
}
# Statuses that mean "this repo/plan cannot have the feature" when the repository is private.
_NOT_AVAILABLE = (403, 404, 422)


@dataclass(frozen=True)
class Protection:
    key: str
    state: str  # OK | OFF | UNAVAILABLE | UNKNOWN
    detail: str = ""


@dataclass(frozen=True)
class RepoState:
    owner: str
    repo: str
    private: bool | None  # None: the repository could not be read
    protections: tuple[Protection, ...]

    def get(self, key: str) -> Protection:
        return next(p for p in self.protections if p.key == key)


def _unreadable(key: str, status: int, private: bool) -> Protection:
    if status == 0:
        return Protection(key, UNKNOWN, "gh unavailable")
    if private and status in _NOT_AVAILABLE:
        return Protection(key, UNAVAILABLE, f"HTTP {status}")
    return Protection(key, UNKNOWN, f"HTTP {status}")


def _secret_scanning(meta: dict, private: bool) -> Protection:
    sa = meta.get("security_and_analysis")
    if not isinstance(sa, dict):
        return Protection(SECRET, UNKNOWN, "not visible (needs repository admin)")

    def status(name: str) -> str | None:
        part = sa.get(name)
        return part.get("status") if isinstance(part, dict) else None

    scanning, push = status("secret_scanning"), status("secret_scanning_push_protection")
    if scanning is None and push is None:
        return Protection(SECRET, UNAVAILABLE if private else UNKNOWN, "not offered for this repo")
    missing = [n for n, s in (("scanning", scanning), ("push protection", push)) if s != "enabled"]
    return (
        Protection(SECRET, OFF, f"{' and '.join(missing)} off")
        if missing
        else Protection(SECRET, OK)
    )


def read_state(owner: str, repo: str, gh: Gh) -> RepoState:
    """Read the four protections with GET calls. Never writes; never raises."""
    base = f"repos/{owner}/{repo}"
    status, meta = gh("GET", base, None)
    if status != 200 or not isinstance(meta, dict):
        why = f"HTTP {status}" if status else "gh unavailable"
        unknown = tuple(Protection(k, UNKNOWN, f"cannot read repository ({why})") for k in KEYS)
        return RepoState(owner, repo, None, unknown)
    private = bool(meta.get("private"))

    out = [_secret_scanning(meta, private)]

    status, _ = gh("GET", f"{base}/vulnerability-alerts", None)
    if status == 204:
        out.append(Protection(ALERTS, OK))
    elif status == 404 and not private:
        out.append(Protection(ALERTS, OFF))
    else:
        out.append(_unreadable(ALERTS, status, private))

    status, data = gh("GET", f"{base}/automated-security-fixes", None)
    if status == 200 and isinstance(data, dict):
        out.append(Protection(UPDATES, OK if data.get("enabled") is True else OFF))
    elif status == 404 and not private:
        out.append(Protection(UPDATES, OFF))
    else:
        out.append(_unreadable(UPDATES, status, private))

    status, data = gh("GET", f"{base}/code-scanning/default-setup", None)
    if status == 200 and isinstance(data, dict):
        out.append(Protection(CODEQL, OK if data.get("state") == "configured" else OFF))
    else:
        out.append(_unreadable(CODEQL, status, private))
    return RepoState(owner, repo, private, tuple(out))


def repo_slug(root: Path | str) -> tuple[str, str]:
    """(owner, repo) from the project's `origin` remote; the host must be github.com."""
    url = installer._git_remote(Path(root))
    if not url:
        raise FactoryError(f"{root} has no `origin` git remote; add the GitHub remote first")
    host, _, rest = url.partition("/")
    parts = rest.split("/")
    if host.lower() != "github.com" or len(parts) != 2 or not all(_NAME.match(p) for p in parts):
        raise FactoryError(f"origin is not a github.com repository ({url}); harden is GitHub-only")
    return parts[0], parts[1]
