"""adopt / sync / new / project: argparse wiring only. Logic lives in swfactory.installer."""

from __future__ import annotations

import argparse

from swfactory import installer


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("adopt", help="lay the factory kit into a project and register it")
    p.add_argument("path")
    p.add_argument("--stack", help="python | node | docs | other (default: autodetect)")
    p.add_argument("--tracker", help="jira | github | none (default: none)")
    p.add_argument("--jira-key")
    p.add_argument("--autonomy", help="supervised | trusted (default: supervised)")
    p.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    p.set_defaults(
        func=lambda a: installer.adopt(
            a.path,
            stack=a.stack,
            tracker=a.tracker,
            jira_key=a.jira_key,
            autonomy=a.autonomy,
            dry_run=a.dry_run,
        )
    )

    p = subparsers.add_parser("sync", help="refresh factory-managed files in an adopted project")
    p.add_argument("path", nargs="?")
    p.add_argument("--force", action="store_true", help="overwrite locally modified managed files")
    p.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    p.set_defaults(func=lambda a: installer.sync(a.path, force=a.force, dry_run=a.dry_run))

    p = subparsers.add_parser("new", help="create a project from a stack template and adopt it")
    p.add_argument("name")
    p.add_argument("--stack", default="python")
    p.add_argument("--dir", help="parent directory (default: current directory)")
    p.set_defaults(func=lambda a: installer.new_project(a.name, stack=a.stack, parent=a.dir))

    project = subparsers.add_parser(
        "project", help="manage the project registry (FACTORY_REGISTRY or ~/.factory/registry.yaml)"
    )
    psub = project.add_subparsers(dest="project_command", required=True, metavar="<action>")

    p = psub.add_parser("list", help="list registered projects")
    p.set_defaults(func=lambda a: installer.project_list())

    p = psub.add_parser("add", help="register a project without adopting it")
    p.add_argument("name")
    p.add_argument("--repo")
    p.add_argument("--stack", default="other", help="python | node | docs | other")
    p.add_argument("--tracker", help="jira | github | none (default: none)")
    p.add_argument("--jira-key")
    p.add_argument("--path", help="local checkout (stored in the user-level registry file)")
    p.set_defaults(
        func=lambda a: installer.project_add(
            a.name,
            repo=a.repo,
            stack=a.stack,
            tracker=a.tracker,
            jira_key=a.jira_key,
            path=a.path,
        )
    )

    p = psub.add_parser("remove", help="remove a project from the registry")
    p.add_argument("name")
    p.set_defaults(func=lambda a: installer.project_remove(a.name))
