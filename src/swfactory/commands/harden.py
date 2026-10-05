"""`factory harden [path] [--dry-run]` - argparse wiring only. Logic lives in swfactory.harden."""

from __future__ import annotations

import argparse

from swfactory import common, harden


def run(args: argparse.Namespace) -> int:
    root = common.find_project_root(args.path)
    lines, code = harden.run(root, dry_run=args.dry_run)
    for line in lines:
        print(line)
    return code


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "harden",
        help="enable secret scanning, Dependabot and CodeQL on the project's GitHub repo",
        description=(
            "Enable, through `gh api`, secret scanning with push protection, Dependabot alerts and "
            "security updates, and CodeQL default setup for the repository named by the project's "
            "origin remote. Reads the current state first and skips what is already on."
        ),
    )
    p.add_argument("path", nargs="?", default=".", help="project (default: current directory)")
    p.add_argument(
        "--dry-run", action="store_true", help="print the API calls it would make; change nothing"
    )
    p.set_defaults(func=run)
