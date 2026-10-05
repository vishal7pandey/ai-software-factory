"""`factory` entry point. Each command module in COMMAND_MODULES exposes register(subparsers)."""

from __future__ import annotations

import argparse
import importlib
import sys

from swfactory import __version__
from swfactory.common import FactoryError

COMMAND_MODULES = ["install", "doctor", "harden", "lint", "work"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factory", description="AI software factory — method, skills and thin glue."
    )
    parser.add_argument("--version", action="version", version=f"factory {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    for name in COMMAND_MODULES:
        try:
            mod = importlib.import_module(f"swfactory.commands.{name}")
        except ModuleNotFoundError as e:
            # Tolerate only a not-yet-written command module, never a broken import inside one.
            if e.name != f"swfactory.commands.{name}":
                raise
            continue
        mod.register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except FactoryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
