"""Shared test setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from swfactory import adopt_inspect, common, harden

# The developer's real home, captured at import time, before any test can redirect it. The registry
# is user-level data outside the repo (Treaty 3.6): no test may read or write it (FACT-18).
REAL_HOME = Path.home().resolve()
REAL_FACTORY_DIR = REAL_HOME / ".factory"


def under_real_factory_dir(path: Path) -> bool:
    return Path(path).resolve().is_relative_to(REAL_FACTORY_DIR)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory, monkeypatch):
    """Every test runs with HOME, USERPROFILE and FACTORY_REGISTRY inside a temp directory, so a
    test that forgets its own redirect cannot touch `~/.factory/registry.yaml`. As a second line,
    the registry path resolver fails loudly if it ever returns a path under the real `~/.factory`.
    A test that wants a specific registry or home sets it itself, after this fixture."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("FACTORY_REGISTRY", str(home / ".factory" / "registry.yaml"))

    real_registry_path = common.registry_path

    def guarded_registry_path() -> Path:
        path = real_registry_path()
        assert not under_real_factory_dir(path), (
            f"test isolation breach: registry_path() resolved to {path}, inside the real "
            f"{REAL_FACTORY_DIR}. Tests must redirect FACTORY_REGISTRY/HOME into tmp_path."
        )
        return path

    monkeypatch.setattr(common, "registry_path", guarded_registry_path)


@pytest.fixture(autouse=True)
def no_project_commands(monkeypatch, request):
    """`adopt` runs the generated CI commands (uv, npm). Tests never spawn them: the default runner
    is replaced by one that always succeeds. A test that wants the real one is marked `real_runner`;
    a test that wants to observe or fail commands passes its own runner."""
    if request.node.get_closest_marker("real_runner"):
        return
    monkeypatch.setattr(adopt_inspect, "run_shell", lambda cmd, cwd: (0, ""))


@pytest.fixture(autouse=True)
def no_real_gh(monkeypatch):
    """`factory harden`, `doctor` and `adopt` talk to GitHub through `harden.gh_api`. The suite
    never reaches the network: the one function that starts `gh` answers "gh unusable" (FACT-33).
    A test that wants GitHub answers passes its own runner or monkeypatches `harden.gh_api`."""
    monkeypatch.setattr(harden, "_run_gh", lambda argv, stdin: (127, ""))
