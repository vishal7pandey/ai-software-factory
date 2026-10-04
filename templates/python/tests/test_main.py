import pytest

from {{package}}.main import greet


def test_greet_returns_greeting():
    assert greet("Ada") == "Hello, Ada!"


def test_greet_strips_whitespace():
    assert greet("  Ada ") == "Hello, Ada!"


def test_greet_rejects_empty_name():
    with pytest.raises(ValueError):
        greet("   ")
