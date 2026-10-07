"""Argparse wiring for owner decisions. Logic lives in swfactory.decisions."""

from __future__ import annotations

from swfactory import decisions
from swfactory.verify import DECISION_TYPES


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "decide",
        help="record the owner's answer to a decision record (never run by an agent)",
        description="Answer a proposed decision record: stamps who and when. The owner runs this; "
        "an agent never does.",
    )
    p.add_argument("id", help="decision id (D-001) or file name, case-insensitive")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--accept", action="store_true", help="accept (the recommended option)")
    mode.add_argument("--reject", action="store_true", help="reject the proposal")
    p.add_argument("--option", type=int, metavar="N", help="with --accept: option number, 1-based")
    p.add_argument("--note", help="a short note stored on the record")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument(
        "--delegated",
        metavar="WHO",
        help="record a decision the named owner explicitly delegated (design and other only)",
    )
    p.set_defaults(
        func=lambda a: decisions.cmd_decide(
            a.id,
            accept=a.accept,
            reject=a.reject,
            option=a.option,
            note=a.note,
            yes=a.yes,
            delegated=a.delegated,
        )
    )

    group = subparsers.add_parser("decision", help="decision records")
    sub = group.add_subparsers(dest="decision_command", required=True, metavar="<action>")
    n = sub.add_parser("new", help="scaffold a proposed decision record (a draft for the agent)")
    n.add_argument("title")
    n.add_argument("--type", dest="dtype", required=True, choices=DECISION_TYPES)
    n.add_argument("--jira", metavar="KEY", help="ticket the decision belongs to (a link only)")
    n.add_argument("--alert", metavar="URL", help="dismissal: the alert URL")
    n.add_argument("--reason", help="dismissal: false positive | won't fix | used in tests")
    n.add_argument("--by", default="agent", help="who proposes it (default: agent)")
    n.set_defaults(
        func=lambda a: decisions.cmd_new(
            a.title,
            dtype=a.dtype,
            jira=a.jira,
            alert=a.alert,
            reason=a.reason,
            by=a.by,
        )
    )

    p = subparsers.add_parser("inbox", help="decisions waiting for the owner, across all projects")
    p.set_defaults(func=lambda a: decisions.cmd_inbox())
