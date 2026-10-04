"""Argparse wiring for work-item commands. Logic lives in swfactory.work."""

from __future__ import annotations

from swfactory import verify, work
from swfactory.verify import RISKS, STATUSES

AGENTS = ["claude", "copilot"]


def _add_start(sub, item_type: str, help_text: str) -> None:
    p = sub.add_parser("start", help=help_text, description=help_text)
    p.add_argument("title")
    p.add_argument("--jira", metavar="KEY", help="Jira key to use as the id (e.g. PF-12)")
    p.add_argument("--risk", choices=RISKS, default="medium")
    p.add_argument("--no-branch", action="store_true", help="do not create/checkout a git branch")
    p.add_argument("--run", choices=AGENTS, help="launch this agent with the handoff prompt")
    p.set_defaults(
        func=lambda a: work.cmd_start(
            item_type, a.title, jira=a.jira, risk=a.risk, no_branch=a.no_branch, run=a.run
        )
    )


def register(subparsers) -> None:
    for item_type, noun in (("feature", "feature"), ("bug", "bug fix")):
        grp = subparsers.add_parser(item_type, help=f"{noun} work items")
        sub = grp.add_subparsers(dest=f"{item_type}_command", required=True, metavar="<action>")
        _add_start(sub, item_type, f"Scaffold a {noun} work item, branch and handoff prompt.")

    p = subparsers.add_parser("status", help="table of work items")
    p.add_argument("--all", action="store_true", help="include items that are done")
    p.set_defaults(func=lambda a: work.cmd_status(a.all))

    p = subparsers.add_parser("approve", help="record a human approval (spec or plan)")
    p.add_argument("id", help="work item id or directory name (case-insensitive)")
    p.add_argument("kind", choices=["spec", "plan"])
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(func=lambda a: work.cmd_approve(a.id, a.kind, a.yes))

    p = subparsers.add_parser("advance", help="move a work item one status forward")
    p.add_argument("id")
    p.add_argument("status", choices=STATUSES)
    p.add_argument("--pr", metavar="URL", help="record the pull request URL")
    p.set_defaults(func=lambda a: work.cmd_advance(a.id, a.status, a.pr))

    p = subparsers.add_parser("next", help="print (or launch) the prompt for the next step")
    p.add_argument("id")
    p.add_argument("--run", choices=AGENTS, help="launch this agent with the prompt")
    p.set_defaults(func=lambda a: work.cmd_next(a.id, a.run))

    p = subparsers.add_parser("verify", help="the CI gate: check work items against the rules")
    verify.add_arguments(p)
    p.set_defaults(func=verify.run)
