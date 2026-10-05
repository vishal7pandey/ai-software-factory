"""Test isolation guard (FACT-18): no test may reach the developer's real ~/.factory."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import REAL_FACTORY_DIR, REAL_HOME

from swfactory import cli, common


def test_registry_and_home_are_inside_tmp(tmp_path_factory):
    base = tmp_path_factory.getbasetemp().resolve()
    assert common.registry_path().resolve().is_relative_to(base)
    assert Path.home().resolve().is_relative_to(base)
    assert not common.registry_path().resolve().is_relative_to(REAL_HOME / ".factory")


def test_forgotten_redirect_does_not_touch_the_real_registry(tmp_path, monkeypatch):
    """A test that never sets FACTORY_REGISTRY (or deletes it) still lands in the temp home."""
    proj = tmp_path / "some-app"
    proj.mkdir()
    (proj / "pyproject.toml").write_text('[project]\nname = "some-app"\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    monkeypatch.delenv("FACTORY_REGISTRY")
    real = REAL_FACTORY_DIR / "registry.yaml"
    before = real.read_bytes() if real.is_file() else None

    assert cli.main(["adopt", str(proj), "--no-check"]) == 0

    written = common.registry_path()
    assert written.is_file() and not written.resolve().is_relative_to(REAL_FACTORY_DIR)
    assert (real.read_bytes() if real.is_file() else None) == before


def test_guard_rejects_a_real_home_registry(monkeypatch):
    monkeypatch.setenv("FACTORY_REGISTRY", str(REAL_FACTORY_DIR / "registry.yaml"))
    with pytest.raises(AssertionError, match="test isolation breach"):
        common.registry_path()
