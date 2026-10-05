"""`factory doctor [path]` - tool check, plus drift/missing-file check for an adopted project."""

from __future__ import annotations

import argparse

from swfactory import checks


def run(args: argparse.Namespace) -> int:
    findings: list[checks.Finding] = []
    if args.path:
        findings += checks.check_project(args.path)
        adopted = checks.adopted_root(args.path)
        if adopted:  # a path that is not an adopted project already FAILed above: no network then
            findings += checks.check_protections(adopted)
    else:
        findings += checks.check_tools()
        root = checks.adopted_root(".")
        if root:
            findings.append(checks.Finding(checks.OK, "project", str(root)))
            findings += checks.check_project(root)
            findings += checks.check_protections(root)
    for line in checks.format_findings(findings):
        print(line)
    fails = len(checks.failures(findings))
    warns = sum(f.level == checks.WARN for f in findings)
    print(f"doctor: {fails} failure(s), {warns} warning(s)")
    return 1 if fails else 0


def register(subparsers) -> None:
    p = subparsers.add_parser("doctor", help="check tools; with a path, check an adopted project")
    p.add_argument("path", nargs="?", help="adopted project to check (default: tools only)")
    p.set_defaults(func=run)
