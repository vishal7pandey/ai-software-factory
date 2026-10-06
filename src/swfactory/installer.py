"""Installation machinery: adopt / sync / new / project registry (Treaty 3.1, 3.5-3.7).

`commands/install.py` only wires argparse to the functions here. Every function raises
`common.FactoryError` for user errors and returns a process exit code (0 ok, 1 conflicts).
"""

from __future__ import annotations

import keyword
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from swfactory import __version__, adopt_inspect, common, dependabot
from swfactory.common import FactoryError

BEGIN = "<!-- factory:begin -->"
END = "<!-- factory:end -->"
CONFIG_REL = ".factory/factory.yaml"

STACKS = ("python", "node", "docs", "other")
AUTONOMY = ("supervised", "trusted")
TRACKERS = ("jira", "github", "none")
MODES = ("create", "managed", "block")
DEFAULT_SKILL_TARGETS = [".claude/skills", ".github/skills"]

# SonarCloud kit files (FACT-35). The one token a create-mode template may contain is filled at
# install time; REPLACE_ME marks what only the owner can know (checks.check_sonar and the workflow
# guard look for it).
SONAR_PLACEHOLDER = "REPLACE_ME"
SONAR_WORKFLOW_DEST = ".github/workflows/sonar.yml"
PROJECT_KEY_TOKEN = "{{project_key}}"


# --- manifest -> desired items ----------------------------------------------------------------


@dataclass
class Item:
    dest: str  # relative to project root, forward slashes
    mode: str
    content: str  # newline-normalised text


@dataclass
class Action:
    dest: str
    status: str  # CREATE | UPDATE | BLOCK | SKIP | CONFLICT | OK (no-op)
    detail: str = ""
    data: bytes | None = None  # bytes to write, if any
    key: str | None = None  # key in factory.yaml > managed
    digest: str | None = None  # hash to record under key


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FactoryError(f"kit source missing: {path}")
    try:
        return common.normalise_newlines(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as e:
        raise FactoryError(f"kit source is not UTF-8 text: {path}") from e


def _stack_matches(entry: dict, stack: str) -> bool:
    wanted = entry.get("stack")
    if wanted is None:
        return True
    return stack in ([wanted] if isinstance(wanted, str) else wanted)


def _files_under(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def collect_items(stack: str, skill_targets: list[str]) -> list[Item]:
    root = common.FACTORY_ROOT
    manifest_path = common.kit_dir() / "manifest.yaml"
    if not manifest_path.is_file():
        raise FactoryError(f"kit manifest not found: {manifest_path}")
    manifest = common.load_yaml(manifest_path)

    def mode_of(entry: dict, default: str | None = None) -> str:
        mode = entry.get("mode", default)
        if mode not in MODES:
            raise FactoryError(f"manifest entry {entry}: mode must be one of {', '.join(MODES)}")
        return mode

    items: list[Item] = []
    for e in manifest.get("files") or []:
        if _stack_matches(e, stack):
            items.append(Item(e["dest"], mode_of(e), _read_text(root / e["src"])))
    for e in manifest.get("dirs") or []:
        if not _stack_matches(e, stack):
            continue
        src_dir = root / e["src"]
        if not src_dir.is_dir():
            raise FactoryError(f"kit directory missing: {src_dir}")
        for f in _files_under(src_dir):
            dest = f"{e['dest'].rstrip('/')}/{f.relative_to(src_dir).as_posix()}"
            items.append(Item(dest, mode_of(e, "managed"), _read_text(f)))
    if manifest.get("skills") == "all":
        sdir = common.skills_dir()
        if not sdir.is_dir():
            raise FactoryError(f"skills directory missing: {sdir}")
        skills = sorted(p for p in sdir.iterdir() if p.is_dir())
        for target in skill_targets:
            for skill in skills:
                for f in _files_under(skill):
                    dest = f"{target.rstrip('/')}/{skill.name}/{f.relative_to(skill).as_posix()}"
                    items.append(Item(dest, "managed", _read_text(f)))
    return items


# --- planning (pure: reads the project, writes nothing) ----------------------------------------


def _decide(current: str, recorded: str | None, force: bool) -> str:
    """Overwrite only when the file is unmodified since we installed it (or --force)."""
    return "UPDATE" if force or (recorded is not None and current == recorded) else "CONFLICT"


_CONFLICT_DETAIL = "locally modified; `factory sync --force` overwrites"


def _find_block(raw: str, dest: str) -> tuple[int, int] | None:
    n_begin, n_end = raw.count(BEGIN), raw.count(END)
    if n_begin == 0 and n_end == 0:
        return None
    if n_begin != 1 or n_end != 1 or raw.index(END) < raw.index(BEGIN):
        raise FactoryError(
            f"{dest}: broken factory markers (found {n_begin} '{BEGIN}' and {n_end} '{END}'); "
            "fix the file by hand, nothing was written"
        )
    return raw.index(BEGIN), raw.index(END)


def _plan_block(item: Item, dest: Path, managed: dict, force: bool) -> Action:
    inner = item.content.strip("\n")
    digest = common.sha256_text(inner)
    key = f"{item.dest}#block"
    block = f"{BEGIN}\n{inner}\n{END}"
    if not dest.exists():
        return Action(item.dest, "CREATE", data=(block + "\n").encode(), key=key, digest=digest)
    raw = dest.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    block = block.replace("\n", eol)
    found = _find_block(raw, item.dest)
    if found is None:
        trailing = raw[len(raw.rstrip("\r\n")) :].count("\n")
        sep = eol * max(0, 2 - trailing) if raw else ""
        data = (raw + sep + block + eol).encode()
        return Action(item.dest, "BLOCK", "append block", data, key, digest)
    begin, end = found
    on_disk = common.normalise_newlines(raw[begin + len(BEGIN) : end]).strip("\n")
    current = common.sha256_text(on_disk)
    if current == digest:
        return Action(item.dest, "OK", key=key, digest=digest)
    status = _decide(current, managed.get(key), force)
    if status == "CONFLICT":
        return Action(item.dest, status, f"block {_CONFLICT_DETAIL}")
    data = (raw[:begin] + block + raw[end + len(END) :]).encode()
    return Action(item.dest, "UPDATE", "replace block", data, key, digest)


def _plan_item(item: Item, root: Path, managed: dict, force: bool) -> Action:
    dest = root / item.dest
    if item.mode == "block":
        return _plan_block(item, dest, managed, force)
    if item.mode == "create":
        if dest.exists():
            return Action(item.dest, "SKIP")
        return Action(item.dest, "CREATE", data=item.content.encode())
    digest = common.sha256_text(item.content)
    if not dest.exists():
        return Action(item.dest, "CREATE", data=item.content.encode(), key=item.dest, digest=digest)
    current = common.sha256_file(dest)
    if current == digest:
        return Action(item.dest, "OK", key=item.dest, digest=digest)
    status = _decide(current, managed.get(item.dest), force)
    if status == "CONFLICT":
        return Action(item.dest, status, _CONFLICT_DETAIL)
    return Action(item.dest, "UPDATE", data=item.content.encode(), key=item.dest, digest=digest)


# --- config (factory.yaml, Treaty 3.5) ---------------------------------------------------------


def detect_stack(root: Path) -> str:
    if (root / "pyproject.toml").is_file():
        return "python"
    if (root / "package.json").is_file():
        return "node"
    return "other"


def _check_enum(label: str, value: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise FactoryError(f"invalid {label} '{value}' (expected one of: {', '.join(allowed)})")
    return value


def _tracker(kind: str | None, jira_key: str | None, existing: dict | None) -> dict:
    existing = existing or {}
    kind = _check_enum("tracker", kind or existing.get("kind") or "none", TRACKERS)
    if kind == "jira":
        key = jira_key or (existing.get("key") if existing.get("kind") == "jira" else None)
        if not key:
            raise FactoryError("tracker 'jira' needs --jira-key")
        return {"kind": "jira", "key": key}
    if jira_key:
        raise FactoryError("--jira-key requires --tracker jira")
    return {"kind": kind}


def resolve_config(
    existing: dict | None,
    root: Path,
    *,
    stack: str | None = None,
    tracker: str | None = None,
    jira_key: str | None = None,
    autonomy: str | None = None,
) -> dict:
    """Explicit flags win over the existing factory.yaml, which wins over defaults."""
    ex = existing or {}
    targets = ex.get("skill_targets") or list(DEFAULT_SKILL_TARGETS)
    if not isinstance(targets, list) or not all(isinstance(t, str) and t for t in targets):
        raise FactoryError(f"{CONFIG_REL}: skill_targets must be a list of directories")
    managed = ex.get("managed") or {}
    if not isinstance(managed, dict):
        raise FactoryError(f"{CONFIG_REL}: managed must be a mapping")
    return {
        "factory_version": __version__,
        "stack": _check_enum("stack", stack or ex.get("stack") or detect_stack(root), STACKS),
        "autonomy": _check_enum(
            "autonomy", autonomy or ex.get("autonomy") or "supervised", AUTONOMY
        ),
        "tracker": _tracker(tracker, jira_key, ex.get("tracker")),
        "skill_targets": targets,
        "environments": ex.get("environments") or {"dev": None, "test": None, "prod": None},
        "managed": dict(managed),
    }


# --- adopt / sync ------------------------------------------------------------------------------


def _project_dir(path: str | Path) -> Path:
    p = Path(path).resolve()
    if not p.is_dir():
        raise FactoryError(f"not a directory: {p}")
    return p


def _sonar_project_key(root: Path) -> str:
    """`<owner>_<repo>` from the GitHub origin remote; a marked placeholder when there is none."""
    from swfactory import harden  # imported here: harden imports this module for the git remote

    try:
        owner, repo = harden.repo_slug(root)
    except FactoryError:
        return f"{SONAR_PLACEHOLDER}_OWNER_REPO"
    return f"{owner}_{repo}"


def _insert_todo(action: Action, todo: str) -> None:
    """Put the TODO commands section directly above the factory block of a new/appended block."""
    if action.data is None or BEGIN.encode() not in action.data:
        return
    eol = b"\r\n" if b"\r\n" in action.data else b"\n"
    text = todo.replace("\n", eol.decode()).encode()
    at = action.data.index(BEGIN.encode())
    action.data = action.data[:at] + text + action.data[at:]
    action.detail = (action.detail + " + " if action.detail else "") + "commands TODO section"


def _install(
    root: Path,
    config: dict,
    existing: dict | None,
    *,
    force: bool,
    dry_run: bool,
    inspection: adopt_inspect.Inspection | None = None,
    check: bool = False,
    runner: adopt_inspect.Runner | None = None,
) -> int:
    """`inspection` (adopt only) adapts what is newly written: the generated CI and a new AGENTS.md
    block. Existing files are never changed that way, so sync and a second adopt stay no-ops."""
    managed = dict(config["managed"])
    items = collect_items(config["stack"], config["skill_targets"])
    for item in items:
        if item.mode == "create" and PROJECT_KEY_TOKEN in item.content:
            item.content = item.content.replace(PROJECT_KEY_TOKEN, _sonar_project_key(root))
        if (
            item.mode == "create"
            and item.dest == dependabot.DEST
            and not (root / item.dest).exists()
        ):
            item.content = dependabot.render_for(root, item.content)
        if (
            inspection is not None
            and item.dest == SONAR_WORKFLOW_DEST
            and not (root / item.dest).exists()
        ):
            item.content = adopt_inspect.point_at_branch(item.content, inspection.default_branch)
    ci_report = adopt_inspect.CiReport()
    if inspection is not None:
        for item in items:
            if item.dest == adopt_inspect.CI_DEST and not (root / item.dest).exists():
                item.content, ci_report = adopt_inspect.adapt_ci(
                    item.content,
                    inspection.default_branch,
                    root,
                    check=check and not dry_run,
                    runner=runner,
                )
                if check and dry_run:
                    ci_report.notes.append("checks not run (--dry-run runs no project command)")
    actions = [_plan_item(item, root, managed, force) for item in items]
    todo_added = False
    if inspection is not None and not inspection.has_commands_section:
        for a in actions:
            if a.dest == "AGENTS.md" and (a.status == "CREATE" or a.detail == "append block"):
                _insert_todo(a, adopt_inspect.todo_section(inspection.detected_commands))
                todo_added = True
    for a in actions:
        if a.key is not None and a.digest is not None:
            managed[a.key] = a.digest
    config["managed"] = dict(sorted(managed.items()))
    if existing != config:
        actions.append(Action(CONFIG_REL, "UPDATE" if existing else "CREATE"))

    for a in actions:
        shown = "SKIP(exists)" if a.status == "SKIP" else a.status
        if a.status == "OK" or (a.status == "SKIP" and not dry_run):
            continue
        print(f"{shown:<14}{a.dest}" + (f"  ({a.detail})" if a.detail else ""))

    count = {
        s: sum(a.status == s for a in actions) for s in ("CREATE", "UPDATE", "BLOCK", "CONFLICT")
    }
    created, updated = count["CREATE"], count["UPDATE"] + count["BLOCK"]
    if not dry_run:
        for a in actions:
            if a.data is not None:
                target = root / a.dest
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(a.data)
        if existing != config:
            common.dump_yaml(config, root / CONFIG_REL)

    if inspection is not None:
        result = ci_report.lines()
        if todo_added:
            n = len(inspection.detected_commands)
            verb = "would add" if dry_run else "added"
            result.append(f"AGENTS.md: {verb} a commands TODO section ({n} detected command(s))")
        if result:
            print("result:")
            for line in result:
                print(f"  {line}")

    if not (created or updated or count["CONFLICT"]):
        print("up to date")
        return 0
    tail = f", {count['CONFLICT']} conflict(s)" if count["CONFLICT"] else ""
    verb = "dry-run, nothing written" if dry_run else "done"
    print(f"{verb}: {created} created, {updated} updated{tail}")
    return 1 if count["CONFLICT"] else 0


def adopt(
    path: str | Path,
    *,
    stack: str | None = None,
    tracker: str | None = None,
    jira_key: str | None = None,
    autonomy: str | None = None,
    dry_run: bool = False,
    check: bool = True,
    runner: adopt_inspect.Runner | None = None,
) -> int:
    root = _project_dir(path)
    if not common.is_git_repo(root):
        print(f"warning: {root} is not a git repository (adopting anyway)", file=sys.stderr)
    cfg_path = root / CONFIG_REL
    existing = common.load_yaml(cfg_path) if cfg_path.is_file() else None
    config = resolve_config(
        existing, root, stack=stack, tracker=tracker, jira_key=jira_key, autonomy=autonomy
    )
    inspection = adopt_inspect.inspect_project(root)
    print("findings:")
    print(f"  default branch: {inspection.default_branch or 'unknown'}")
    for line in inspection.findings:
        print(f"  {line}")
    if not inspection.has_commands_section:
        print("  AGENTS.md: no commands section (a TODO section goes above the factory block)")
    code = _install(
        root,
        config,
        existing,
        force=False,
        dry_run=dry_run,
        inspection=inspection,
        check=check,
        runner=runner,
    )
    if not dry_run:
        _register_adopted(root, config)
    from swfactory import harden  # imported here: harden imports this module for the git remote

    for line in harden.adopt_note(root, str(path)):
        print(line)
    return code


def sync(path: str | Path | None = None, *, force: bool = False, dry_run: bool = False) -> int:
    start = _project_dir(path or ".")
    root = common.find_project_root(start)
    cfg_path = root / CONFIG_REL
    if not cfg_path.is_file():
        raise FactoryError(f"{root} is not adopted (no {CONFIG_REL}); run `factory adopt` first")
    existing = common.load_yaml(cfg_path)
    config = resolve_config(existing, root)
    return _install(root, config, existing, force=force, dry_run=dry_run)


def sync_check(path: str | Path | None = None) -> int:
    """Exit 1 if any managed or block file is missing or differs from the factory source."""
    root = common.find_project_root(_project_dir(path or "."))
    cfg_path = root / CONFIG_REL
    if not cfg_path.is_file():
        raise FactoryError(f"{root} is not adopted (no {CONFIG_REL}); run `factory adopt` first")
    config = resolve_config(common.load_yaml(cfg_path), root)
    managed = dict(config["managed"])
    stale = []
    for item in collect_items(config["stack"], config["skill_targets"]):
        a = _plan_item(item, root, managed, False)
        if item.mode != "create" and a.status in ("CREATE", "UPDATE", "BLOCK", "CONFLICT"):
            stale.append(a)
    for a in stale:
        what = "MISSING" if a.status == "CREATE" else "STALE"
        print(f"{what:<8}{a.dest}" + (f"  ({a.detail})" if a.detail else ""))
    if stale:
        print(f"{len(stale)} managed file(s) differ from the factory source; run `factory sync`")
        return 1
    print("in sync with the factory source")
    return 0


# --- registry (Treaty 3.6) ---------------------------------------------------------------------


def _load_registry() -> dict:
    p = common.registry_path()
    try:
        data = common.load_yaml(p) if p.is_file() else {}
    except (OSError, yaml.YAMLError) as e:
        raise FactoryError(f"cannot read the registry {p}: {e}") from e
    if not isinstance(data, dict):
        raise FactoryError(f"the registry {p} must be a mapping with `projects` and `paths`")
    data["projects"] = data.get("projects") or []
    data["paths"] = data.get("paths") or {}
    return data


def _save_registry(data: dict) -> None:
    p = common.registry_path()
    header: list[str] = []
    try:
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.startswith("#"):
                    break
                header.append(line)
        common.dump_yaml(data, p)
        if header:  # keep the file's leading comment; PyYAML would drop it
            body = p.read_text(encoding="utf-8")
            p.write_text("\n".join(header) + "\n" + body, encoding="utf-8", newline="\n")
    except OSError as e:
        raise FactoryError(f"cannot write the registry {p}: {e}") from e


def normalise_repo_url(url: str) -> str:
    """https://host/o/n.git | git@host:o/n.git | ssh://git@host/o/n -> host/o/n"""
    u = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", url.strip())
    u = re.sub(r"^[^@/]+@", "", u)
    head, sep, tail = u.partition("/")
    if ":" in head:  # scp-style host:owner/name
        u = head.replace(":", "/", 1) + sep + tail
    return u.removesuffix("/").removesuffix(".git")


def _git_remote(root: Path) -> str | None:
    if not common.is_git_repo(root):
        return None
    try:
        url = common.git("remote", "get-url", "origin", cwd=root, check=False)
    except FactoryError:
        return None
    return normalise_repo_url(url) if url else None


def _register_adopted(root: Path, config: dict) -> None:
    name = root.name
    reg = _load_registry()
    projects = reg["projects"]
    index = next((i for i, p in enumerate(projects) if p.get("name") == name), None)
    old = projects[index] if index is not None else {}
    fresh = {
        "name": name,
        "repo": _git_remote(root) or old.get("repo"),
        "stack": config["stack"],
        "tracker": dict(config["tracker"]),
        "autonomy": config["autonomy"],
        "adopted": True,
    }
    merged = {**old, **fresh}
    changed = False
    if index is None:
        projects.append(merged)
        changed = True
    elif merged != old:
        projects[index] = merged
        changed = True
    if reg["paths"].get(name) != str(root):
        reg["paths"][name] = str(root)
        changed = True
    if changed:
        _save_registry(reg)


def project_list() -> int:
    if not common.registry_path().is_file():
        where = common.registry_path()
        print(f"no registry yet (`factory adopt` creates it; location: {where})")
        return 0
    reg = _load_registry()
    projects, paths = reg["projects"], reg["paths"]
    if not projects:
        print("no projects registered")
        return 0
    rows = [("name", "stack", "tracker", "adopted", "path")]
    for p in projects:
        t = p.get("tracker") or {}
        tracker = f"{t.get('kind', 'none')}:{t['key']}" if t.get("key") else t.get("kind", "none")
        rows.append(
            (
                str(p.get("name")),
                str(p.get("stack") or "-"),
                tracker,
                "yes" if p.get("adopted") else "no",
                paths.get(p.get("name")) or "-",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r[:4], widths, strict=True)) + "  " + r[4])
    return 0


def project_add(
    name: str,
    *,
    repo: str | None = None,
    stack: str = "other",
    tracker: str | None = None,
    jira_key: str | None = None,
    path: str | Path | None = None,
) -> int:
    _check_enum("stack", stack, STACKS)
    trk = _tracker(tracker, jira_key, None)
    reg = _load_registry()
    if any(p.get("name") == name for p in reg["projects"]):
        raise FactoryError(f"project '{name}' is already registered")
    abs_path = _project_dir(path) if path else None
    reg["projects"].append(
        {
            "name": name,
            "repo": normalise_repo_url(repo) if repo else None,
            "stack": stack,
            "tracker": trk,
            "autonomy": "supervised",
            "adopted": False,
        }
    )
    if abs_path:
        reg["paths"][name] = str(abs_path)
    _save_registry(reg)
    print(f"registered {name}")
    return 0


def project_remove(name: str) -> int:
    reg = _load_registry()
    kept = [p for p in reg["projects"] if p.get("name") != name]
    if len(kept) == len(reg["projects"]):
        raise FactoryError(f"project '{name}' is not registered")
    reg["projects"] = kept
    reg["paths"].pop(name, None)
    _save_registry(reg)
    print(f"removed {name} from the registry (project files untouched)")
    return 0


# --- new ---------------------------------------------------------------------------------------


def package_name(name: str) -> str:
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise FactoryError(f"invalid project name '{name}'")
    pkg = re.sub(r"[^a-z0-9]+", "_", name.lower())
    if not pkg.strip("_") or not pkg.isidentifier() or keyword.iskeyword(pkg):
        raise FactoryError(
            f"cannot derive a Python package name from '{name}' (got '{pkg}'); "
            "it must start with a letter and contain letters or digits"
        )
    return pkg


def new_project(name: str, *, stack: str = "python", parent: str | Path | None = None) -> int:
    pkg = package_name(name)
    template = common.templates_dir() / stack
    if not template.is_dir():
        raise FactoryError(f"no template for stack '{stack}' ({template})")
    base = Path(parent).resolve() if parent else Path.cwd()
    target = base / name
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FactoryError(f"{target} already exists and is not empty")

    for src in sorted(template.rglob("*")):
        rel = src.relative_to(template)
        if "__pycache__" in rel.parts or src.suffix == ".pyc":
            continue
        dst = target.joinpath(*[pkg if part == "__package__" else part for part in rel.parts])
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            dst.write_bytes(data)
            continue
        text = common.normalise_newlines(text)
        text = text.replace("{{name}}", name).replace("{{package}}", pkg)
        dst.write_bytes(text.encode("utf-8"))
    target.mkdir(parents=True, exist_ok=True)

    common.git("init", "-b", "main", cwd=target)
    print(f"created {target}")
    return adopt(target, stack=stack)
