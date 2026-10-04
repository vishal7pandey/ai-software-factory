"""Work-item logic: scaffold, status, approve, advance, next. See docs/ARCHITECTURE.md 3.2."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from swfactory import common
from swfactory.common import FactoryError
from swfactory.verify import (
    CLARIFY,
    ITEM_KEYS,
    JIRA_RE,
    RISKS,
    STATUSES,
    check_project,
    dir_id,
    load_item,
    required_approvals,
    validate_item,
)

AGENT_COMMANDS = {"claude": ["claude"], "copilot": ["copilot", "-i"]}

# --- project / config --------------------------------------------------------------------------


def project_root(start: Path | str = ".") -> Path:
    root = common.find_project_root(start)
    if not (root / ".factory" / "factory.yaml").is_file():
        raise FactoryError(f"{root} is not an adopted project: run 'factory adopt' first")
    return root


def load_config(root: Path) -> dict:
    return common.load_yaml(root / ".factory" / "factory.yaml")


def work_dir(root: Path) -> Path:
    return root / "docs" / "work"


def _required(item: dict, config: dict) -> list[str]:
    try:
        return required_approvals(item, config)
    except ValueError as e:
        raise FactoryError(f"factory.yaml: {e}") from e


def plan_waived(item: dict, config: dict) -> bool:
    return "plan" not in _required(item, config)


# --- ids, templates, scaffold ------------------------------------------------------------------


def next_id(root: Path, item_type: str) -> str:
    prefix = "F" if item_type == "feature" else "B"
    pat = re.compile(rf"^{prefix}-(\d+)-")
    nums = [int(m.group(1)) for d in _item_dirs(root) if (m := pat.match(d.name))]
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


def _item_dirs(root: Path) -> list[Path]:
    wd = work_dir(root)
    return sorted(p for p in wd.iterdir() if p.is_dir()) if wd.is_dir() else []


def _render_templates(item_type: str, values: dict[str, str]) -> dict[str, str]:
    manifest = common.load_yaml(common.FACTORY_ROOT / "kit" / "manifest.yaml")
    wanted = manifest.get("work_templates") or {}
    spec_key = "feature_spec" if item_type == "feature" else "bug_spec"
    out = {}
    for fname, key in (("spec.md", spec_key), ("plan.md", "plan"), ("test-plan.md", "test_plan")):
        rel = wanted.get(key)
        path = common.FACTORY_ROOT / rel if rel else None
        if path is None or not path.is_file():
            raise FactoryError(f"work template '{key}' not found ({rel}) in {common.FACTORY_ROOT}")
        text = common.normalise_newlines(path.read_text(encoding="utf-8"))
        for k, v in values.items():
            text = text.replace("{{" + k + "}}", v)
        out[fname] = text
    return out


def start_item(
    root: Path,
    item_type: str,
    title: str,
    *,
    jira: str | None = None,
    risk: str = "medium",
    no_branch: bool = False,
) -> tuple[Path, dict]:
    """Scaffold docs/work/<id>-<slug>/ (+ branch). Returns (item dir, item dict)."""
    if risk not in RISKS:
        raise FactoryError(f"risk must be one of {', '.join(RISKS)}")
    if not title.strip():
        raise FactoryError("title must not be empty")
    if jira is not None and not JIRA_RE.match(jira):
        raise FactoryError(f"invalid Jira key {jira!r} (expected like PF-12)")
    item_id = jira or next_id(root, item_type)
    for d in _item_dirs(root):
        if (dir_id(d.name) or "").lower() == item_id.lower():
            raise FactoryError(f"work item {item_id} already exists: {d.relative_to(root)}")

    slug = common.slugify(title)
    prefix = "feature" if item_type == "feature" else "fix"
    branch = f"{prefix}/{item_id.lower()}-{slug}"
    item_dir = work_dir(root) / f"{item_id}-{slug}"
    if item_dir.exists():
        raise FactoryError(f"{item_dir.relative_to(root)} already exists")
    item = {
        "id": item_id,
        "type": item_type,
        "title": title.strip(),
        "slug": slug,
        "status": "draft",
        "risk": risk,
        "jira": jira,
        "branch": branch,
        "created": common.today(),
        "approvals": {},
        "pr": None,
    }
    docs = _render_templates(
        item_type,
        {
            "id": item_id,
            "title": item["title"],
            "slug": slug,
            "date": item["created"],
            "risk": risk,
            "jira": jira or "none",
        },
    )

    # Everything that can fail is done; create the branch (carries a dirty tree, stages nothing).
    if not no_branch and common.is_git_repo(root):
        common.git("checkout", "-b", branch, cwd=root)

    item_dir.mkdir(parents=True)
    for name, text in docs.items():
        (item_dir / name).write_text(text, encoding="utf-8", newline="\n")
    write_item(item_dir, item)
    return item_dir, item


def write_item(item_dir: Path, item: dict) -> None:
    ordered = {k: item[k] for k in ITEM_KEYS if k in item}
    ordered.update({k: v for k, v in item.items() if k not in ordered})
    common.dump_yaml(ordered, item_dir / "item.yaml")


# --- finding / loading -------------------------------------------------------------------------


def find_item_dir(root: Path, ident: str) -> Path:
    """Match a full dir name or just the id, case-insensitively."""
    want = ident.strip().strip("/\\").lower()
    for d in _item_dirs(root):
        if want in (d.name.lower(), (dir_id(d.name) or "").lower()):
            return d
    raise FactoryError(f"no work item '{ident}' in docs/work/")


def load_valid_item(item_dir: Path) -> dict:
    try:
        item = load_item(item_dir / "item.yaml")
    except (ValueError, OSError) as e:
        raise FactoryError(f"{item_dir.name}: item.yaml unreadable: {e}") from e
    problems = validate_item(item, item_dir.name)
    if problems:
        raise FactoryError(f"{item_dir.name}: invalid item.yaml: " + "; ".join(problems))
    return item


def report_problems(root: Path, item: dict) -> list[str]:
    """check_project filtered to one item; printed as FAIL lines (never fatal)."""
    lines = [p for p in check_project(root) if p.startswith(f"{item['id']}:")]
    for p in lines:
        print(f"FAIL {p}")
    return lines


# --- next-step table ---------------------------------------------------------------------------


def next_step(item: dict, config: dict) -> tuple[list[str], str | None]:
    """(skills, human action or None) for the item's current status."""
    iid, status = item["id"], item["status"]
    if status == "draft":
        skill = "factory-diagnose" if item["type"] == "bug" else "factory-spec"
        return [skill], f"factory approve {iid} spec"
    if status == "spec-approved":
        if plan_waived(item, config):
            return ["factory-plan"], f"factory advance {iid} plan-approved (plan approval waived)"
        return ["factory-plan"], f"factory approve {iid} plan"
    if status == "plan-approved":
        return ["factory-test", "factory-implement"], None
    if status == "implementing":
        return ["factory-implement"], None
    if status == "in-review":
        return ["factory-review"], f"merge the PR, then factory advance {iid} merged"
    if status in ("merged", "released"):
        return ["factory-release"], None
    return [], None


def build_prompt(item: dict, item_dir: Path, config: dict) -> tuple[str, str | None]:
    """(agent prompt, human-step line or None). Prompt is '' when there is nothing to do."""
    skills, human = next_step(item, config)
    if not skills:
        return "", None
    target = f"work item docs/work/{item_dir.name}/ (id {item['id']})"
    use = " skill, then the ".join(f"{s}" for s in skills)
    prompt = (
        f"Use the {use} skill on {target}. Read item.yaml, spec.md and plan.md first. "
        "Do not run 'factory approve'; ask the human to approve."
    )
    if item["status"] == "implementing":
        prompt += " Continue the implementation where it left off."
    if item["status"] == "released":
        prompt += " Verify the release and close out."
    return prompt, (f"Next human step: {human}" if human else None)


def print_handoff(item: dict, item_dir: Path, config: dict) -> str:
    prompt, human = build_prompt(item, item_dir, config)
    if not prompt:
        print(f"Nothing to do: {item['id']} is done.")
        return ""
    print(prompt)
    if human:
        print(human)
    return prompt


def launch_agent(agent: str, prompt: str, cwd: Path) -> int:
    if agent not in AGENT_COMMANDS:
        raise FactoryError(f"unknown agent {agent!r} (expected claude or copilot)")
    cmd = AGENT_COMMANDS[agent]
    exe = shutil.which(cmd[0])
    if not exe:
        raise FactoryError(
            f"'{cmd[0]}' not found on PATH. Paste this prompt into your agent:\n{prompt}"
        )
    return subprocess.run([exe, *cmd[1:], prompt], cwd=str(cwd)).returncode


# --- commands' logic ---------------------------------------------------------------------------


def cmd_start(
    item_type: str,
    title: str,
    *,
    jira: str | None,
    risk: str,
    no_branch: bool,
    run: str | None,
    start: Path | str = ".",
) -> int:
    root = project_root(start)
    item_dir, item = start_item(root, item_type, title, jira=jira, risk=risk, no_branch=no_branch)
    config = load_config(root)
    print(f"Created {item_dir.relative_to(root).as_posix()}/")
    for name in ("item.yaml", "spec.md", "plan.md", "test-plan.md"):
        print(f"  {(item_dir / name).relative_to(root).as_posix()}")
    if not no_branch and common.is_git_repo(root):
        print(f"Branch: {item['branch']}")
    print()
    prompt = print_handoff(item, item_dir, config)
    return launch_agent(run, prompt, root) if run else 0


def collect_status(root: Path, show_all: bool) -> list[tuple[str, str, str, str, str]]:
    config = load_config(root)
    rows = []
    for d in _item_dirs(root):
        if not (d / "item.yaml").is_file():
            continue
        try:
            item = load_item(d / "item.yaml")
            problems = validate_item(item, d.name)
        except (ValueError, OSError) as e:
            item, problems = {}, [str(e)]
        if problems:
            rows.append((dir_id(d.name) or d.name, "?", "INVALID", "-", problems[0]))
            continue
        if item["status"] == "done" and not show_all:
            continue
        skills, human = next_step(item, config) if item["status"] != "done" else ([], None)
        nxt = " + ".join(skills) or "-"
        if human:
            nxt += f" | human: {human}"
        rows.append((item["id"], item["type"], item["status"], item.get("branch") or "-", nxt))
    return rows


def format_table(rows: list[tuple[str, ...]]) -> str:
    header = ("id", "type", "status", "branch", "next")
    table = [header, *rows]
    widths = [max(len(r[i]) for r in table) for i in range(len(header))]
    return "\n".join(
        "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in table
    )


def cmd_status(show_all: bool, start: Path | str = ".") -> int:
    root = project_root(start)
    rows = collect_status(root, show_all)
    if not rows:
        print("No work items." if show_all else "No open work items (use --all to include done).")
        return 0
    print(format_table(rows))
    return 0


def _doc_ok(path: Path, label: str) -> None:
    if not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
        raise FactoryError(f"{label} is missing or empty")
    if CLARIFY in path.read_text(encoding="utf-8-sig"):
        raise FactoryError(f"{label} still contains '{CLARIFY}'; resolve open questions first")


def cmd_approve(ident: str, kind: str, yes: bool, start: Path | str = ".") -> int:
    root = project_root(start)
    item_dir = find_item_dir(root, ident)
    item = load_valid_item(item_dir)
    target = f"{kind}-approved"
    idx, tidx = STATUSES.index(item["status"]), STATUSES.index(target)
    if idx == tidx - 1:
        advancing = True
    elif tidx <= idx <= STATUSES.index("in-review"):
        advancing = False  # re-approval of an amended doc: refresh the ledger, keep status
    else:
        raise FactoryError(
            f"cannot approve {kind} for {item['id']}: status is {item['status']} "
            f"(must be {STATUSES[tidx - 1]}, or {target} up to in-review to re-approve)"
        )
    doc = f"{kind}.md"
    _doc_ok(item_dir / doc, f"{item_dir.name}/{doc}")
    who = common.git_user_name(root)
    if not yes:
        if not sys.stdin.isatty():
            raise FactoryError("not a terminal: re-run with --yes to approve non-interactively")
        lines = len((item_dir / doc).read_text(encoding="utf-8-sig").splitlines())
        print(
            f"Approve {kind} for {item['id']} '{item['title']}' "
            f"(risk {item['risk']}, {doc} {lines} lines) as {who}? [y/N] ",
            end="",
            flush=True,
        )
        if sys.stdin.readline().strip().lower() != "y":
            print("Not approved.")
            return 1
    item["approvals"] = {**(item.get("approvals") or {}), kind: {"by": who, "at": common.today()}}
    if advancing:
        item["status"] = target
    write_item(item_dir, item)
    print(f"{item['id']}: {kind} approved by {who}; status is {item['status']}")
    report_problems(root, item)
    return 0


def cmd_advance(ident: str, target: str, pr: str | None, start: Path | str = ".") -> int:
    root = project_root(start)
    item_dir = find_item_dir(root, ident)
    item = load_valid_item(item_dir)
    config = load_config(root)
    if target not in STATUSES:
        raise FactoryError(f"unknown status {target!r} (one of {', '.join(STATUSES)})")
    cur, new = STATUSES.index(item["status"]), STATUSES.index(target)
    if new <= cur:
        raise FactoryError(f"{item['id']} is already {item['status']}; status only moves forward")
    if new != cur + 1:
        raise FactoryError(
            f"cannot skip from {item['status']} to {target}; next status is {STATUSES[cur + 1]}"
        )
    if target == "spec-approved" or (target == "plan-approved" and not plan_waived(item, config)):
        kind = target.removesuffix("-approved")
        raise FactoryError(f"{target} is a human gate: use 'factory approve {item['id']} {kind}'")
    if target == "implementing":
        _doc_ok(item_dir / "test-plan.md", f"{item_dir.name}/test-plan.md")
    item["status"] = target
    if pr:
        item["pr"] = pr
    write_item(item_dir, item)
    print(f"{item['id']}: status is now {target}")
    report_problems(root, item)
    return 0


def cmd_next(ident: str, run: str | None, start: Path | str = ".") -> int:
    root = project_root(start)
    item_dir = find_item_dir(root, ident)
    item = load_valid_item(item_dir)
    prompt = print_handoff(item, item_dir, load_config(root))
    return launch_agent(run, prompt, root) if run and prompt else 0
