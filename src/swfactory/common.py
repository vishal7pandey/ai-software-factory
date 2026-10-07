"""Shared helpers. Keep small: stdlib + PyYAML only."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import subprocess
from pathlib import Path

import yaml


class FactoryError(Exception):
    """User-facing error: the CLI prints the message to stderr and exits 1."""


# --- locating things ---------------------------------------------------------------------------

# src/swfactory/common.py -> parents[2] is the factory repo root (editable/src-layout install).
FACTORY_ROOT = Path(os.environ.get("FACTORY_HOME") or Path(__file__).resolve().parents[2])


def skills_dir() -> Path:
    return FACTORY_ROOT / "skills"


def kit_dir() -> Path:
    return FACTORY_ROOT / "kit"


def policies_dir() -> Path:
    return FACTORY_ROOT / "policies"


def templates_dir() -> Path:
    return FACTORY_ROOT / "templates"


def registry_path() -> Path:
    """The project registry lives outside the factory repo (Treaty 3.6).

    `FACTORY_REGISTRY` (relative paths resolve against the cwd), else `~/.factory/registry.yaml`.
    """
    env = os.environ.get("FACTORY_REGISTRY")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".factory" / "registry.yaml"


def find_project_root(start: Path | str = ".") -> Path:
    """Nearest ancestor containing .factory/factory.yaml, else nearest containing .git."""
    p = Path(start).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".factory" / "factory.yaml").is_file():
            return cand
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    raise FactoryError(f"no project found at or above {p}")


# --- text / hashing ----------------------------------------------------------------------------


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) > max_len:
        cut = s[:max_len]
        # Prefer ending on a whole word, unless that would throw away most of the slug.
        s = cut.rsplit("-", 1)[0] if "-" in cut[max_len // 2 :] else cut
    return s.strip("-") or "item"


def today() -> str:
    return dt.date.today().isoformat()


def normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalise_newlines(text).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(Path(path).read_text(encoding="utf-8"))


# --- yaml / frontmatter ------------------------------------------------------------------------


def load_yaml(path: Path | str) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data if data is not None else {}


def yaml_text(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


def dump_yaml(data: dict, path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml_text(data), encoding="utf-8", newline="\n")


_FM = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """('---\\nk: v\\n---\\nbody') -> ({'k': 'v'}, 'body'). No frontmatter -> ({}, text)."""
    m = _FM.match(normalise_newlines(text))
    if not m:
        return {}, normalise_newlines(text)
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise FactoryError("frontmatter must be a YAML mapping")
    return meta, m.group(2)


def read_frontmatter(path: Path | str) -> tuple[dict, str]:
    return split_frontmatter(Path(path).read_text(encoding="utf-8"))


# --- git ---------------------------------------------------------------------------------------


def git(*args: str, cwd: Path | str = ".", check: bool = True) -> str:
    """Run git, return stripped stdout. Raises FactoryError on failure when check=True."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8"
        )
    except FileNotFoundError as e:
        raise FactoryError("git is not installed or not on PATH") from e
    if check and r.returncode != 0:
        raise FactoryError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def git_user_name(cwd: Path | str = ".") -> str:
    name = git("config", "user.name", cwd=cwd, check=False)
    if not name:
        raise FactoryError("git user.name is not set (needed to record who approved)")
    return name


def is_git_repo(path: Path | str) -> bool:
    return (Path(path) / ".git").exists()
