"""FACT-48: the supported-today matrix (docs/SUPPORT.md) cannot rot.

`support.check_support(root)` compares the matrix with what the repository contains. The real
repository must pass; synthetic trees (a minimal valid one, then one change each) must fail with a
finding that names the problem.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from swfactory import checks, common, decisions, support
from swfactory.cli import main

ROOT = Path(__file__).resolve().parent.parent

HEADER = "| dimension | value | status | proven by | known gaps |\n|---|---|---|---|---|\n"


def row(
    dim: str, value: str, status: str = "supported", proven: str = "tests only", gaps="none known"
):
    return f"| {dim} | `{value}` | {status} | {proven} | {gaps} |\n"


def good_rows() -> list[str]:
    rows = [row("stack", s) for s in ("python", "node", "docs", "other")]
    rows += [row("stack", "go", "not supported", "nothing", "no template")]
    rows += [row("tracker", "jira"), row("hosting", "github.com"), row("ci", "github actions")]
    rows += [row("scanner", "codeql"), row("os", "windows")]
    rows += [row("dependabot ecosystem", e) for e in ("python", "npm", "github-actions")]
    return rows


MANIFEST = {
    "version": 1,
    "files": [
        {
            "src": "kit/ci/python.yml",
            "dest": ".github/workflows/ci.yml",
            "mode": "create",
            "stack": "python",
        },
        {
            "src": "kit/ci/node.yml",
            "dest": ".github/workflows/ci.yml",
            "mode": "create",
            "stack": "node",
        },
        {
            "src": "kit/ci/generic.yml",
            "dest": ".github/workflows/ci.yml",
            "mode": "create",
            "stack": ["docs", "other"],
        },
    ],
    "dependabot_templates": {
        "python": "kit/dependabot/python.yml",
        "npm": "kit/dependabot/npm.yml",
        "github-actions": "kit/dependabot/github-actions.yml",
    },
}


def write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_tree(root: Path, rows: list[str] | None = None) -> Path:
    """A minimal factory repository that passes the check."""
    write(
        root / "docs" / "SUPPORT.md",
        "# Supported today\n\n" + HEADER + "".join(rows or good_rows()),
    )
    write(root / "docs" / "ARCHITECTURE.md", "# Treaty\n\nSee [SUPPORT.md](SUPPORT.md).\n")
    write(root / "docs" / "ROADMAP.md", "# Roadmap\n\nSee [SUPPORT.md](SUPPORT.md).\n")
    write(root / "kit" / "manifest.yaml", yaml.safe_dump(MANIFEST))
    for stem in ("python", "node", "generic"):
        write(root / "kit" / "ci" / f"{stem}.yml")
    for stem in ("python", "node"):
        write(root / "kit" / "sonar" / f"{stem}.yml")
        write(root / "kit" / "sonar" / f"{stem}.properties")
    write(root / "templates" / "python" / "README.md")
    return root


def problems(root: Path) -> list[str]:
    return support.check_support(root)


def has(found: list[str], *needles: str) -> bool:
    return any(all(n in line for n in needles) for line in found)


# --- the real repository ------------------------------------------------------------------------


def test_real_matrix_is_current():
    assert problems(ROOT) == []


def test_real_matrix_has_the_rows_the_ticket_names():
    rows = support.parse_rows((ROOT / "docs" / "SUPPORT.md").read_text(encoding="utf-8"))
    have = {(r.dimension, r.value) for r in rows}
    for stack in (
        "python",
        "node",
        "docs",
        "other",
        "go",
        "java",
        "rust",
        "dotnet",
        "static site",
        "iac",
    ):
        assert ("stack", stack) in have, stack
    for tracker in ("jira", "none", "github", "other"):
        assert ("tracker", tracker) in have, tracker
    for dim in support.REQUIRED_DIMENSIONS | {"agent", "shape", "owners"}:
        assert any(r.dimension == dim for r in rows), dim


def test_real_matrix_is_honest_about_the_inert_github_tracker():
    # `adopt --tracker github` is accepted but nothing reads it: the row must say so
    rows = support.parse_rows((ROOT / "docs" / "SUPPORT.md").read_text(encoding="utf-8"))
    github = next(r for r in rows if (r.dimension, r.value) == ("tracker", "github"))
    assert github.status == "not supported"
    assert "inert" in github.gaps.lower() or "nothing reads" in github.gaps.lower()


def test_treaty_and_roadmap_link_the_matrix_and_the_page():
    for name in ("ARCHITECTURE.md", "ROADMAP.md"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert "SUPPORT.md" in text, name
        assert "Factory generality: assumptions and roadmap" in text, name


# --- the minimal tree is valid; each change breaks it in a named way (AC2, AC3) -----------------


def test_minimal_tree_is_clean(tmp_path):
    assert problems(make_tree(tmp_path)) == []


@pytest.mark.parametrize(
    "path",
    [
        "templates/go/main.go",
        "kit/ci/go.yml",
        "kit/sonar/go.properties",
        "kit/sonar/go.yml",
    ],
)
def test_stack_from_a_file_without_a_row_fails(tmp_path, path):
    make_tree(tmp_path, [r for r in good_rows() if "`go`" not in r])
    assert problems(tmp_path) == []  # not there yet, so no row is needed
    write(tmp_path / path)
    found = problems(tmp_path)
    assert has(found, "go", "no row", "docs/SUPPORT.md"), found


@pytest.mark.parametrize("stack", ["rust", ["rust", "docs"]])
def test_stack_from_the_manifest_without_a_row_fails(tmp_path, stack):
    make_tree(tmp_path)
    manifest = dict(MANIFEST)
    manifest["files"] = [
        *MANIFEST["files"],
        {"src": "kit/ci/rust.yml", "dest": "x.yml", "mode": "create", "stack": stack},
    ]
    write(tmp_path / "kit" / "manifest.yaml", yaml.safe_dump(manifest))
    found = problems(tmp_path)
    assert has(found, "rust", "no row"), found


def test_stack_from_the_code_constant_needs_a_row(tmp_path, monkeypatch):
    make_tree(tmp_path)
    monkeypatch.setattr(support, "STACKS", (*support.STACKS, "swift"))
    assert has(problems(tmp_path), "swift", "no row")


def test_shared_generic_stem_needs_no_row(tmp_path):
    make_tree(tmp_path, [r for r in good_rows() if "`generic`" not in r])
    assert (tmp_path / "kit" / "ci" / "generic.yml").is_file()
    assert problems(tmp_path) == []


def test_stack_directories_are_the_only_templates_counted(tmp_path):
    make_tree(tmp_path)
    write(tmp_path / "templates" / "stray.txt")  # a file, not a stack directory
    assert problems(tmp_path) == []


def test_not_supported_row_for_an_absent_stack_is_fine(tmp_path):
    make_tree(
        tmp_path, good_rows() + [row("stack", "static site", "not supported", "nothing", "x")]
    )
    assert problems(tmp_path) == []


def test_row_claiming_support_for_a_stack_that_does_not_exist_fails(tmp_path):
    for status in ("supported", "partial"):
        rows = [r for r in good_rows() if "`go`" not in r] + [row("stack", "go", status)]
        make_tree(tmp_path, rows)
        found = problems(tmp_path)
        assert has(found, "go", "claims", status, "no template"), found


def test_missing_file_fails(tmp_path):
    make_tree(tmp_path)
    (tmp_path / "docs" / "SUPPORT.md").unlink()
    assert has(problems(tmp_path), "docs/SUPPORT.md", "missing")


def test_file_without_a_table_fails(tmp_path):
    make_tree(tmp_path)
    write(tmp_path / "docs" / "SUPPORT.md", "# Supported today\n\nEverything works.\n")
    assert has(problems(tmp_path), "no table rows")


def test_unknown_status_fails(tmp_path):
    rows = [r.replace("| supported |", "| works |", 1) if "`jira`" in r else r for r in good_rows()]
    make_tree(tmp_path, rows)
    assert has(problems(tmp_path), "works", "status")


def test_status_words_are_exact(tmp_path):
    assert support.STATUSES == ("supported", "partial", "not supported")
    rows = [
        r.replace("| supported |", "| Supported |", 1) if "`jira`" in r else r for r in good_rows()
    ]
    make_tree(tmp_path, rows)
    assert problems(tmp_path) == []  # case does not matter, the word does


@pytest.mark.parametrize("cell", ["proven by", "known gaps"])
def test_empty_cell_fails(tmp_path, cell):
    broken = row(
        "tracker",
        "jira",
        proven="" if cell == "proven by" else "tests only",
        gaps="" if cell == "known gaps" else "none known",
    )
    rows = [r for r in good_rows() if "`jira`" not in r] + [broken]
    make_tree(tmp_path, rows)
    assert has(problems(tmp_path), "jira", cell)


def test_row_with_too_few_or_too_many_cells_fails(tmp_path):
    for bad in (
        "| tracker | `jira` | supported | tests only |\n",
        "| tracker | `jira` | supported | a | b | c |\n",
    ):
        rows = [r for r in good_rows() if "`jira`" not in r] + [bad]
        make_tree(tmp_path, rows)
        assert has(problems(tmp_path), "5 cells"), bad


def test_required_dimension_missing_fails(tmp_path):
    make_tree(tmp_path, [r for r in good_rows() if not r.startswith("| os ")])
    found = problems(tmp_path)
    assert has(found, "os", "no row"), found
    assert support.REQUIRED_DIMENSIONS == {"stack", "tracker", "hosting", "ci", "scanner", "os"}


def test_dependabot_ecosystem_without_a_row_fails(tmp_path):
    make_tree(tmp_path, [r for r in good_rows() if "`npm`" not in r])
    found = problems(tmp_path)
    assert has(found, "npm", "dependabot ecosystem", "no row"), found


@pytest.mark.parametrize("doc", ["ARCHITECTURE.md", "ROADMAP.md"])
def test_doc_without_a_link_fails(tmp_path, doc):
    make_tree(tmp_path)
    write(tmp_path / "docs" / doc, "# nothing here\n")
    assert has(problems(tmp_path), doc, "SUPPORT.md")


def test_missing_roadmap_fails(tmp_path):
    make_tree(tmp_path)
    (tmp_path / "docs" / "ROADMAP.md").unlink()
    assert has(problems(tmp_path), "ROADMAP.md", "missing")


def test_unreadable_manifest_is_a_finding_not_a_crash(tmp_path):
    make_tree(tmp_path)
    write(tmp_path / "kit" / "manifest.yaml", "files: [unclosed\n")
    assert has(problems(tmp_path), "kit/manifest.yaml")


def test_header_and_separator_lines_are_not_rows():
    rows = support.parse_rows(HEADER + row("stack", "python"))
    assert [(r.dimension, r.value, r.status) for r in rows] == [("stack", "python", "supported")]


# --- wired into `factory lint` (AC4) ------------------------------------------------------------


def copy_factory_files(dest: Path) -> Path:
    for name in ("kit", "skills", "policies", "templates"):
        shutil.copytree(ROOT / name, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        ROOT / "docs",
        dest / "docs",
        ignore=shutil.ignore_patterns("work", "decisions", "__pycache__"),
    )
    (dest / "src" / "swfactory").mkdir(parents=True)
    shutil.copy(ROOT / "src" / "swfactory" / "verify.py", dest / "src" / "swfactory" / "verify.py")
    return dest


def test_lint_catches_a_new_stack_directory_without_a_row(tmp_path, monkeypatch, capsys):
    copy_factory_files(tmp_path)
    monkeypatch.setattr(common, "FACTORY_ROOT", tmp_path)
    assert main(["lint"]) == 0, capsys.readouterr().out
    capsys.readouterr()

    write(tmp_path / "templates" / "go" / "main.go")
    assert main(["lint"]) == 1
    out = capsys.readouterr().out
    assert "FAIL docs/SUPPORT.md:" in out and "go" in out and "no row" in out


def test_lint_checks_the_matrix_only_in_a_factory_repository(tmp_path):
    write(tmp_path / "templates" / "go" / "main.go")  # no docs/ARCHITECTURE.md: not a factory repo
    assert [f for f in checks.lint_factory(tmp_path) if "SUPPORT" in f.name] == []

    write(
        tmp_path / "docs" / "ARCHITECTURE.md", "# Treaty\n"
    )  # now it is one, and the matrix is missing
    found = [f for f in checks.lint_factory(tmp_path) if "SUPPORT" in f.name]
    assert found and all(f.level == checks.FAIL for f in found)


# --- the proposed decision (AC6) -----------------------------------------------------------------


def test_the_proposed_extension_is_a_valid_unanswered_design_record():
    records = {r.id: r for r in decisions.load_records(ROOT)}
    assert "D-003" in records
    rec = records["D-003"]
    assert rec.problems == ()
    assert rec.type == "design" and rec.status == "proposed"
    assert rec.meta["jira"] and "FACT-48" in str(rec.meta["jira"])
    assert rec.meta["decision"] is None and rec.meta["by"] is None and rec.meta["at"] is None
    assert rec.meta["delegated"] is False
    options = rec.meta["options"]
    assert len(options) >= 3
    assert sum(1 for o in options if o.get("recommended") is True) == 1
    assert any("do nothing" in o["text"].lower() for o in options)
    assert not any("do nothing" in o["text"].lower() for o in options if o.get("recommended"))
    assert not rec.draft  # no unfilled marker or REPLACE_ME left


def test_no_decision_was_answered_by_this_item():
    for rec in decisions.load_records(ROOT):
        if rec.id in ("D-001", "D-002", "D-003"):
            assert rec.status == "proposed", rec.id
