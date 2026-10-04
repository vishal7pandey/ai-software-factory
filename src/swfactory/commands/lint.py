"""`factory lint` - validate skills and the kit manifest in the factory repo."""

from __future__ import annotations

import argparse

from swfactory import checks, common


def run(args: argparse.Namespace) -> int:
    findings = checks.lint_factory(common.FACTORY_ROOT)
    for line in checks.format_lint(findings):
        print(line)
    return 1 if checks.failures(findings) else 0


def register(subparsers) -> None:
    p = subparsers.add_parser("lint", help="validate skills and kit manifest in the factory repo")
    p.set_defaults(func=run)
