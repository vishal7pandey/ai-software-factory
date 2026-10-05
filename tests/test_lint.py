from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from swfactory import checks, common
from swfactory.cli import main

SECTIONS = [
    "When to use",
    "Inputs",
    "Steps",
    "Output",
    "Definition of done",
    "Never",
]


def skill_text(
    name: str = "factory-demo",
    description: str = "Use when demoing.",
    sections: list[str] | None = None,
    extra: str = "Writes docs/work/<id>/spec.md.\n",
    frontmatter: bool = True,
) -> str:
    secs = SECTIONS if sections is None else sections
    body = "".join(f"## {s}\n\n{extra if s == 'Steps' else 'text'}\n\n" for s in secs)
    fm = f"---\nname: {name}\ndescription: {description}\n---\n" if frontmatter else ""
    return fm + "# Title\n\n" + body


def put_skill(root: Path, name: str = "factory-demo", text: str | None = None) -> Path:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text if text is not None else skill_text(name), encoding="utf-8")
    return d


def reasons(root: Path, level: str = checks.FAIL) -> list[str]:
    return [f.detail for f in checks.lint_skills(root) if f.level == level]


def has(found: list[str], needle: str) -> bool:
    return any(needle in r for r in found)


# --- skills -------------------------------------------------------------------------------------


def test_good_skill_is_clean(tmp_path):
    put_skill(tmp_path)
    assert checks.lint_skills(tmp_path) == []


def test_dir_prefix(tmp_path):
    put_skill(tmp_path, "demo", skill_text("demo"))
    assert has(reasons(tmp_path), "start with 'factory-'")


def test_name_must_match_dir(tmp_path):
    put_skill(tmp_path, "factory-demo", skill_text("factory-other"))
    assert has(reasons(tmp_path), "must equal directory name")


@pytest.mark.parametrize(
    "desc,needle",
    [
        ("''", "missing or empty"),
        ("Do the thing.", "start with 'Use when'"),
        ("Use when " + "x" * 1100, "max 1024"),
    ],
)
def test_description_rules(tmp_path, desc, needle):
    put_skill(tmp_path, text=skill_text(description=desc))
    assert has(reasons(tmp_path), needle)


def test_missing_frontmatter(tmp_path):
    put_skill(tmp_path, text=skill_text(frontmatter=False))
    assert has(reasons(tmp_path), "missing YAML frontmatter")


def test_body_length(tmp_path):
    put_skill(tmp_path, text=skill_text(extra="line\n" * 200))
    assert has(reasons(tmp_path), "max 150")


def test_missing_section(tmp_path):
    put_skill(tmp_path, text=skill_text(sections=[s for s in SECTIONS if s != "Inputs"]))
    assert has(reasons(tmp_path), "missing section(s): ## Inputs")


def test_sections_out_of_order(tmp_path):
    swapped = SECTIONS[:]
    swapped[1], swapped[2] = swapped[2], swapped[1]
    put_skill(tmp_path, text=skill_text(sections=swapped))
    assert has(reasons(tmp_path), "out of order")


def test_section_in_code_fence_does_not_count(tmp_path):
    text = skill_text(sections=SECTIONS[:-1]) + "```\n## Never\n```\n"
    put_skill(tmp_path, text=text)
    assert has(reasons(tmp_path), "missing section(s): ## Never")


@pytest.mark.parametrize(
    "line",
    [
        "Run `factory approve F-001 spec` now.",
        "Then FACTORY APPROVE the plan.",
        "The task: factory approve it.",
    ],
)
def test_approve_instruction_fails(tmp_path, line):
    put_skill(tmp_path, text=skill_text(extra=f"docs/work/\n{line}\n"))
    assert has(reasons(tmp_path), "factory approve")


@pytest.mark.parametrize(
    "line",
    [
        "Never run `factory approve`.",
        "Do not run factory approve.",
        "Ask the human to run `factory approve F-001 spec`.",
        "You must not run factory approve.",
    ],
)
def test_approve_prohibition_passes(tmp_path, line):
    put_skill(tmp_path, text=skill_text(extra=f"docs/work/\n{line}\n"))
    assert reasons(tmp_path) == []


def test_broken_reference(tmp_path):
    put_skill(tmp_path, text=skill_text(extra="docs/work/ see references/long.md.\n"))
    assert has(reasons(tmp_path), "references/long.md does not exist")


def test_existing_reference(tmp_path):
    d = put_skill(tmp_path, text=skill_text(extra="docs/work/ see references/long.md.\n"))
    (d / "references").mkdir()
    (d / "references" / "long.md").write_text("x", encoding="utf-8")
    assert reasons(tmp_path) == []


def test_warn_without_docs_work(tmp_path):
    put_skill(tmp_path, text=skill_text(extra="nothing\n"))
    assert reasons(tmp_path) == []
    assert has(reasons(tmp_path, checks.WARN), "docs/work/")


def test_unknown_cross_reference(tmp_path):
    put_skill(tmp_path, text=skill_text(extra="docs/work/ then factory-ghost.\n"))
    assert has(reasons(tmp_path), "unknown skill 'factory-ghost'")


def test_known_cross_reference_and_workflow_filename(tmp_path):
    put_skill(tmp_path, "factory-other")
    text = skill_text(extra="docs/work/ then factory-other; CI is factory-verify.yml.\n")
    put_skill(tmp_path, text=text)
    assert reasons(tmp_path) == []


def test_skill_dir_without_skill_md(tmp_path):
    (tmp_path / "skills" / "factory-empty").mkdir(parents=True)
    assert has(reasons(tmp_path), "SKILL.md is missing")


EDIT_RULE = "Never rewrite files with inline scripts.\n"
STAGE_RULE = "Never stage with git add -A.\n"


def implement_skill(*rules: str) -> str:
    return skill_text(name="factory-implement", extra="docs/work/\n" + "".join(rules))


def test_implement_skill_must_carry_editing_rules(tmp_path):
    put_skill(tmp_path, "factory-implement", implement_skill(EDIT_RULE, STAGE_RULE))
    assert reasons(tmp_path) == []

    put_skill(tmp_path, "factory-implement", implement_skill(STAGE_RULE))
    missing = reasons(tmp_path)
    assert has(missing, "missing required rule: file-editing hazard") and len(missing) == 1

    put_skill(tmp_path, "factory-implement", implement_skill(EDIT_RULE))
    missing = reasons(tmp_path)
    assert has(missing, "missing required rule: explicit-staging") and len(missing) == 1

    # only the named skill is subject to the rule
    put_skill(tmp_path, "factory-implement", implement_skill(EDIT_RULE, STAGE_RULE))
    put_skill(tmp_path)  # factory-demo, no rules
    assert reasons(tmp_path) == []


def test_repo_implement_skill_carries_the_editing_rules():
    text = (common.FACTORY_ROOT / "skills" / "factory-implement" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert (
        "inline scripts" in text and "git add -A" in text and "re-read every changed line" in text
    )
    assert [f for f in checks.lint_skills(common.FACTORY_ROOT) if f.level == checks.FAIL] == []


# --- manifest -----------------------------------------------------------------------------------


def make_kit(root: Path) -> dict:
    for p in ["kit/a.md", "kit/ci/py.yml", "kit/ci/node.yml", "kit/w/t.md", "pol/x.md"]:
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text("x", encoding="utf-8")
    return {
        "version": 1,
        "files": [
            {"src": "kit/a.md", "dest": "A.md", "mode": "create"},
            {"src": "kit/ci/py.yml", "dest": "ci.yml", "mode": "create", "stack": "python"},
            {"src": "kit/ci/node.yml", "dest": "ci.yml", "mode": "create", "stack": ["node"]},
        ],
        "dirs": [{"src": "pol", "dest": ".factory/pol", "mode": "managed"}],
        "skills": "all",
        "work_templates": {"plan": "kit/w/t.md"},
    }


def lint_manifest(root: Path, data) -> list[str]:
    (root / "kit").mkdir(exist_ok=True)
    (root / "kit" / "manifest.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return [f.detail for f in checks.lint_manifest(root)]


def test_good_manifest(tmp_path):
    assert lint_manifest(tmp_path, make_kit(tmp_path)) == []


def test_manifest_missing(tmp_path):
    assert has([f.detail for f in checks.lint_manifest(tmp_path)], "missing")


def test_manifest_unparseable(tmp_path):
    (tmp_path / "kit").mkdir()
    (tmp_path / "kit" / "manifest.yaml").write_text("files: [unclosed\n", encoding="utf-8")
    assert has([f.detail for f in checks.lint_manifest(tmp_path)], "does not parse")


def test_bad_mode(tmp_path):
    m = make_kit(tmp_path)
    m["files"][0]["mode"] = "overwrite"
    assert has(lint_manifest(tmp_path, m), "mode 'overwrite'")


def test_missing_key(tmp_path):
    m = make_kit(tmp_path)
    del m["files"][0]["dest"]
    assert has(lint_manifest(tmp_path, m), "missing key(s): dest")


def test_src_missing(tmp_path):
    m = make_kit(tmp_path)
    m["files"][0]["src"] = "kit/nope.md"
    assert has(lint_manifest(tmp_path, m), "kit/nope.md does not exist")


def test_bad_stack(tmp_path):
    m = make_kit(tmp_path)
    m["files"][1]["stack"] = "rust"
    assert has(lint_manifest(tmp_path, m), "invalid stack")


def test_dest_collision_overlapping_stacks(tmp_path):
    m = make_kit(tmp_path)
    m["files"][2]["stack"] = ["node", "python"]
    assert has(lint_manifest(tmp_path, m), "stacks overlap")


def test_dest_collision_without_stack(tmp_path):
    m = make_kit(tmp_path)
    m["files"].append({"src": "kit/a.md", "dest": "ci.yml", "mode": "create"})
    assert has(lint_manifest(tmp_path, m), "stacks overlap")


def test_dir_missing_and_empty(tmp_path):
    m = make_kit(tmp_path)
    m["dirs"] = [
        {"src": "nodir", "dest": "d", "mode": "managed"},
        {"src": "emptydir", "dest": "e", "mode": "managed"},
    ]
    (tmp_path / "emptydir").mkdir()
    found = lint_manifest(tmp_path, m)
    assert has(found, "src dir nodir does not exist")
    assert has(found, "src dir emptydir is empty")


def test_work_template_missing(tmp_path):
    m = make_kit(tmp_path)
    m["work_templates"]["bug_spec"] = "kit/w/none.md"
    assert has(lint_manifest(tmp_path, m), "work_templates.bug_spec")


# --- command ------------------------------------------------------------------------------------


def test_command_exit_codes_and_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(common, "FACTORY_ROOT", tmp_path)
    lint_manifest(tmp_path, make_kit(tmp_path))
    put_skill(tmp_path)
    assert main(["lint"]) == 0
    assert "lint: OK" in capsys.readouterr().out

    put_skill(tmp_path, "demo", skill_text("demo"))
    assert main(["lint"]) == 1
    out = capsys.readouterr().out
    assert "FAIL skills/demo/SKILL.md:" in out
    assert "lint: 1 problem(s)" in out


# --- generic factory (no instance data) ----------------------------------------------------------


def test_instance_data_rules(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ok.md").write_text("see https://example.com/wiki\n", encoding="utf-8")
    assert checks.lint_generic(tmp_path) == []

    (tmp_path / "docs" / "bad.md").write_text("https://x.atlassian.net/wiki\n", encoding="utf-8")
    found = checks.lint_generic(tmp_path)
    assert [f.name for f in found] == ["docs/bad.md"] and found[0].level == checks.FAIL

    # the same hostname in a skill, kit or tests dir: skills/kit fail, tests are not scanned
    put_skill(tmp_path)
    (tmp_path / "skills" / "factory-demo" / "ref.md").write_text(
        "a.atlassian.net\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("x = 'a.atlassian.net'\n", encoding="utf-8")
    names = {f.name for f in checks.lint_generic(tmp_path)}
    assert names == {"docs/bad.md", "skills/factory-demo/ref.md"}

    # the factory's own evidence trail is not scanned
    (tmp_path / "docs" / "bad.md").unlink()
    (tmp_path / "skills" / "factory-demo" / "ref.md").unlink()
    (tmp_path / "docs" / "work").mkdir()
    (tmp_path / "docs" / "work" / "n.md").write_text("a.atlassian.net\n", encoding="utf-8")
    assert checks.lint_generic(tmp_path) == []


def test_registry_directory_fails_lint(tmp_path, monkeypatch, capsys):
    (tmp_path / "registry").mkdir()
    (tmp_path / "registry" / "projects.yaml").write_text("projects: []\n", encoding="utf-8")
    found = checks.lint_generic(tmp_path)
    assert [(f.level, f.name) for f in found] == [(checks.FAIL, "registry/")]

    # wired into `factory lint`: a valid kit and skill alone pass, the registry dir makes it fail
    monkeypatch.setattr(common, "FACTORY_ROOT", tmp_path)
    lint_manifest(tmp_path, make_kit(tmp_path))
    put_skill(tmp_path)
    assert main(["lint"]) == 1
    assert "FAIL registry/:" in capsys.readouterr().out
    (tmp_path / "registry" / "projects.yaml").unlink()
    (tmp_path / "registry").rmdir()
    assert main(["lint"]) == 0


def test_repo_has_no_registry_dir():
    root = common.FACTORY_ROOT
    assert not (root / "registry").exists()
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "registry" not in gi
