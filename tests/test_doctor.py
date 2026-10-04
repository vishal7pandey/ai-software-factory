from __future__ import annotations

from pathlib import Path

import pytest

from swfactory import __version__, checks, common
from swfactory.cli import main


def fake_env(missing=(), gh_auth=True, docker_up=True, versions=None):
    versions = versions or {}

    def which(name):
        return None if name in missing else f"/bin/{name}"

    def run(argv, timeout):
        if argv[1:] == ["auth", "status"]:
            return (0 if gh_auth else 1), ""
        if argv == ["docker", "info"]:
            return (0 if docker_up else 1), ""
        return 0, versions.get(argv[0], f"{argv[0]} version 1.2.3 (extra 9.9)")

    return which, run


def by_name(findings):
    return {f.name: f for f in findings}


def test_all_tools_ok():
    which, run = fake_env()
    f = by_name(checks.check_tools(which, run, (3, 13, 0)))
    assert all(x.level == checks.OK for x in f.values())
    assert f["git"].detail == "1.2.3"
    assert f["python"].detail == "3.13.0"
    assert "gh auth" in f


def test_version_parsing_variants():
    which, run = fake_env(versions={"node": "v22.1.0", "claude": "2.0.1 (Claude Code)"})
    f = by_name(checks.check_tools(which, run, (3, 12, 0)))
    assert f["node"].detail == "22.1.0"
    assert f["claude"].detail == "2.0.1"


@pytest.mark.parametrize("tool", ["git", "uv"])
def test_missing_required_tool_fails(tool):
    which, run = fake_env(missing=[tool])
    f = by_name(checks.check_tools(which, run, (3, 12, 0)))
    assert f[tool].level == checks.FAIL and f[tool].detail == "MISSING"


@pytest.mark.parametrize("tool", ["gh", "node", "docker", "claude"])
def test_missing_optional_tool_only_warns(tool):
    which, run = fake_env(missing=[tool])
    findings = checks.check_tools(which, run, (3, 12, 0))
    assert by_name(findings)[tool].level == checks.WARN
    assert not checks.failures(findings)


def test_old_python_fails():
    which, run = fake_env()
    f = by_name(checks.check_tools(which, run, (3, 11, 9)))
    assert f["python"].level == checks.FAIL


def test_gh_not_logged_in_warns():
    which, run = fake_env(gh_auth=False)
    f = by_name(checks.check_tools(which, run, (3, 12, 0)))
    assert f["gh"].level == checks.OK
    assert f["gh auth"].level == checks.WARN


def test_docker_daemon_down_warns_not_fails():
    which, run = fake_env(docker_up=False)
    findings = checks.check_tools(which, run, (3, 12, 0))
    assert by_name(findings)["docker"].level == checks.WARN
    assert "daemon" in by_name(findings)["docker"].detail
    assert not checks.failures(findings)


def test_run_cmd_never_raises():
    assert checks.run_cmd(["definitely-not-a-real-binary-xyz"]) == (127, "")


# --- adopted project ----------------------------------------------------------------------------


@pytest.fixture
def factory(tmp_path):
    root = tmp_path / "factory"
    for n in ("factory-spec", "factory-plan"):
        (root / "skills" / n).mkdir(parents=True)
        (root / "skills" / n / "SKILL.md").write_text("x", encoding="utf-8")
    return root


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    (p / ".factory").mkdir(parents=True)
    (p / ".git").mkdir()
    (p / ".factory" / "verify.py").write_text("print(1)\n", encoding="utf-8", newline="\n")
    for t in (".claude/skills", ".github/skills"):
        for n in ("factory-spec", "factory-plan"):
            (p / t / n).mkdir(parents=True)
    write_cfg(p)
    return p


def write_cfg(p: Path, **over):
    cfg = {
        "factory_version": __version__,
        "stack": "python",
        "skill_targets": [".claude/skills", ".github/skills"],
        "managed": {".factory/verify.py": common.sha256_file(p / ".factory" / "verify.py")},
    }
    cfg.update(over)
    common.dump_yaml(cfg, p / ".factory" / "factory.yaml")


def run_project(p, factory):
    return checks.check_project(p, factory_root=factory)


def test_healthy_project(project, factory):
    findings = run_project(project, factory)
    assert [f.level for f in findings if f.level != checks.OK] == []


def test_managed_file_missing_fails(project, factory):
    (project / ".factory" / "verify.py").unlink()
    f = by_name(run_project(project, factory))
    assert f[".factory/verify.py"].level == checks.FAIL


def test_managed_file_drifted_warns(project, factory):
    (project / ".factory" / "verify.py").write_text("changed\n", encoding="utf-8")
    findings = run_project(project, factory)
    f = by_name(findings)[".factory/verify.py"]
    assert f.level == checks.WARN and "drifted" in f.detail
    assert not checks.failures(findings)


def test_crlf_does_not_count_as_drift(project, factory):
    (project / ".factory" / "verify.py").write_bytes(b"print(1)\r\n")
    assert not [f for f in run_project(project, factory) if f.level != checks.OK]


def test_missing_skill_warns(project, factory):
    (project / ".github" / "skills" / "factory-plan").rmdir()
    f = by_name(run_project(project, factory))
    w = f["skills .github/skills"]
    assert w.level == checks.WARN and "factory-plan" in w.detail and "factory sync" in w.detail
    assert f["skills .claude/skills"].level == checks.OK


def test_old_version_warns(project, factory):
    write_cfg(project, factory_version="0.0.1")
    f = by_name(run_project(project, factory))
    assert f["factory_version"].level == checks.WARN


def test_no_git_warns(project, factory):
    (project / ".git").rmdir()
    assert by_name(run_project(project, factory))["git"].level == checks.WARN


def test_not_adopted_fails(tmp_path, factory):
    f = checks.check_project(tmp_path, factory_root=factory)
    assert f[0].level == checks.FAIL


def test_adopted_root_detection(project):
    sub = project / "src"
    sub.mkdir()
    assert checks.adopted_root(sub) == project.resolve()


# --- command ------------------------------------------------------------------------------------


def test_command_with_path_reports_project_only(project, factory, monkeypatch, capsys):
    monkeypatch.setattr(common, "FACTORY_ROOT", factory)
    assert main(["doctor", str(project)]) == 0
    out = capsys.readouterr().out
    assert "managed files" in out and "doctor: 0 failure(s)" in out
    assert "docker" not in out

    (project / ".factory" / "verify.py").unlink()
    assert main(["doctor", str(project)]) == 1
    assert "FAIL  .factory/verify.py" in capsys.readouterr().out


def test_command_tools_table_with_fakes(monkeypatch, tmp_path, capsys):
    which, run = fake_env(missing=["uv"])
    real = checks.check_tools
    monkeypatch.setattr(checks, "check_tools", lambda: real(which, run))
    monkeypatch.chdir(tmp_path)
    assert main(["doctor"]) == 1
    out = capsys.readouterr().out
    assert "FAIL  uv" in out and "MISSING" in out
