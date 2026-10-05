"""`factory harden`: enable and check the repository-level protections of a GitHub-hosted project.

Four protections: secret scanning with push protection, Dependabot alerts, Dependabot security
updates, CodeQL default setup. All GitHub access goes through ONE function, `gh_api`, so tests replace
it and never touch the network. Failures are reported by HTTP status only: a response body is parsed
for state on reads and is never printed. Output is ASCII-only (Windows consoles).
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
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
    """`gh api -i` output (status line, headers, blank line, body) -> (status, JSON body or None)."""
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
