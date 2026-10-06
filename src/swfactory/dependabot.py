"""Render `.github/dependabot.yml` for the ecosystems a project really uses (FACT-39).

The kit holds one header (`kit/dependabot/dependabot.yml`, with an `{{updates}}` token) and one
fragment per ecosystem (`dependabot_templates` in `kit/manifest.yaml`). `detect` looks for manifests
in the project and `render` fills the header with one fragment per find, so a project with no
`package.json` is never offered `npm`. The result is written once, in `create` mode, and never
touched again. Stdlib only; no network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from swfactory import common
from swfactory.common import FactoryError

DEST = ".github/dependabot.yml"
UPDATES_TOKEN = "{{updates}}"
KINDS = ("python", "npm", "github-actions")

# Directories that never hold the project's own manifests.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "site-packages",
        "__pycache__",
        "dist",
        "build",
        "vendor",
        "third_party",
        ".tox",
        ".nox",
        ".next",
        ".factory",
        ".claude",
        ".github",
    }
)
MAX_DEPTH = 3  # directories below the project root that are searched


@dataclass(frozen=True)
class Entry:
    kind: str  # python | npm | github-actions
    ecosystem: str  # the `package-ecosystem` value: uv | pip | npm | github-actions
    directory: str  # "/" or "/sub/dir", as Dependabot wants it

    def key(self) -> tuple[str, str, str]:
        return (self.kind, self.ecosystem, self.directory)


def _directory(root: Path, here: Path) -> str:
    rel = here.relative_to(root).as_posix()
    return "/" if rel == "." else f"/{rel}"


def detect(root: Path | str) -> list[Entry]:
    """Ecosystems the project uses, each with the directory its manifest lives in.

    python: `uv` where a `pyproject.toml` has a `uv.lock` beside it, else `pip` where there is a
    `pyproject.toml` or a `requirements*.txt`. npm: where a `package.json` is (a pnpm or yarn
    lockfile is covered by the same ecosystem). github-actions: always, at `/` (the kit lays
    workflows in)."""
    root = Path(root).resolve()
    found: dict[tuple[str, str, str], Entry] = {}

    def add(entry: Entry) -> None:
        found.setdefault(entry.key(), entry)

    for current, dirs, files in os.walk(root):
        here = Path(current)
        depth = len(here.relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS) if depth < MAX_DEPTH else []
        names = set(files)
        directory = _directory(root, here)
        if "pyproject.toml" in names:
            eco = "uv" if "uv.lock" in names else "pip"
            add(Entry("python", eco, directory))
        elif any(n.startswith("requirements") and n.endswith(".txt") for n in names):
            add(Entry("python", "pip", directory))
        if "package.json" in names:
            add(Entry("npm", "npm", directory))
    add(Entry("github-actions", "github-actions", "/"))
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(found.values(), key=lambda e: (order[e.kind], e.directory, e.ecosystem))


def load_fragments(factory_root: Path | None = None) -> dict[str, str]:
    """The per-ecosystem fragments named by `dependabot_templates` in the kit manifest."""
    base = factory_root or common.FACTORY_ROOT
    manifest = common.load_yaml(common.kit_dir() / "manifest.yaml")
    listed = manifest.get("dependabot_templates") or {}
    if not isinstance(listed, dict) or set(listed) != set(KINDS):
        raise FactoryError(
            f"kit manifest: dependabot_templates must name exactly {', '.join(KINDS)}"
        )
    out: dict[str, str] = {}
    for kind, rel in listed.items():
        path = base / str(rel)
        if not path.is_file():
            raise FactoryError(f"kit source missing: {path}")
        out[kind] = common.normalise_newlines(path.read_text(encoding="utf-8")).rstrip("\n")
    return out


def render(header: str, entries: list[Entry], fragments: dict[str, str]) -> str:
    """The header with `{{updates}}` replaced by one filled fragment per entry."""
    if UPDATES_TOKEN not in header:
        raise FactoryError(f"the dependabot header has no {UPDATES_TOKEN} token")
    parts = [
        fragments[e.kind]
        .replace("{{ecosystem}}", e.ecosystem)
        .replace("{{directory}}", e.directory)
        for e in entries
    ]
    body = "\n\n".join(parts)
    return common.normalise_newlines(header).replace(UPDATES_TOKEN, body).rstrip("\n") + "\n"


def render_for(root: Path | str, header: str) -> str:
    """Convenience for the installer: detect the project's ecosystems and render."""
    return render(header, detect(root), load_fragments())
