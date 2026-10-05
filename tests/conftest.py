"""Shared test setup."""

from __future__ import annotations

import pytest

from swfactory import adopt_inspect


@pytest.fixture(autouse=True)
def no_project_commands(monkeypatch, request):
    """`adopt` runs the generated CI commands (uv, npm). Tests never spawn them: the default runner
    is replaced by one that always succeeds. A test that wants the real one is marked `real_runner`;
    a test that wants to observe or fail commands passes its own runner."""
    if request.node.get_closest_marker("real_runner"):
        return
    monkeypatch.setattr(adopt_inspect, "run_shell", lambda cmd, cwd: (0, ""))
