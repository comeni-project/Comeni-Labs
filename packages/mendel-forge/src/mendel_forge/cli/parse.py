"""argparse and nothing else.

Split out for the reason `mendel_compiler.cli.parse` is: a parser that also decides things
is a parser you cannot read the surface off. Every verb here maps to exactly one function
in `ops.py`.

**`--registry` defaults everywhere except `land`.** Reading a registry to propose a draft
is harmless and constant; writing to one is the single action in this package with a git
commit behind it, and `registry/` in Comeni-Labs is a submodule at a detached HEAD. A
defaulted target there means somebody eventually commits into it by accident.
"""

import argparse
from pathlib import Path

_REGISTRY = Path("registry")
_VENDOR = Path("vendor")
_WORKSPACE = Path(".forge")


def _reads_a_draft(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("name")
    sub.add_argument("--registry", type=Path, default=_REGISTRY)
    sub.add_argument("--source-root", type=Path, default=_VENDOR)
    sub.add_argument("--workspace", type=Path, default=_WORKSPACE)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="forge", description="Scaffold and verify registry data")
    root.add_argument("--json", action="store_true", help="print the result model verbatim")
    verbs = root.add_subparsers(dest="command", required=True)

    verbs.add_parser("sources", help="the ingestion sources that are registered")

    discover = verbs.add_parser("discover", help="every tool a source can read")
    discover.add_argument("--source", default=None)
    discover.add_argument("--source-root", type=Path, default=_VENDOR)

    draft = verbs.add_parser("draft", help="ingest a tool into a new draft")
    draft.add_argument("ref", help="<source>:<tool>, e.g. nf-core:fastqc")
    draft.add_argument("--name", required=True)
    draft.add_argument("--version", default="0.0.0")
    draft.add_argument("--registry", type=Path, default=_REGISTRY)
    draft.add_argument("--source-root", type=Path, default=_VENDOR)
    draft.add_argument("--workspace", type=Path, default=_WORKSPACE)

    listing = verbs.add_parser("list", help="the drafts in the workspace")
    listing.add_argument("--workspace", type=Path, default=_WORKSPACE)

    _reads_a_draft(verbs.add_parser("show", help="a draft's filled fields and open holes"))
    _reads_a_draft(verbs.add_parser("verify", help="run the five-rung ladder over a draft"))

    fill = verbs.add_parser("fill", help="answer one hole, by hand or with a model")
    fill.add_argument("name")
    fill.add_argument("field", nargs="?", help="omit with --model to attempt every hole")
    fill.add_argument("value", nargs="?")
    fill.add_argument("--by")
    fill.add_argument("--why")
    fill.add_argument("--list", action="store_true", help="the value is a comma-separated list")
    fill.add_argument(
        "--model",
        nargs="?",
        const="",
        default=None,
        help="attempt candidate-bearing holes with a model. Bare --model reads MENDEL_MODEL",
    )
    fill.add_argument("--workspace", type=Path, default=_WORKSPACE)

    propose = verbs.add_parser(
        "propose", help="decline a hole: nothing declared fits, and here is what would"
    )
    propose.add_argument("name")
    propose.add_argument("field")
    propose.add_argument("id", help="the type id being proposed")
    propose.add_argument("--description", required=True)
    propose.add_argument("--by", required=True)
    propose.add_argument("--why", required=True)
    propose.add_argument("--workspace", type=Path, default=_WORKSPACE)

    check = verbs.add_parser("check", help="does the registry still match its sources")
    check.add_argument("--registry", type=Path, default=_REGISTRY)
    check.add_argument("--source-root", type=Path, default=_VENDOR)

    update = verbs.add_parser("update", help="re-draft one contract from its source")
    update.add_argument("contract_id")
    update.add_argument("--name", required=True)
    update.add_argument("--registry", type=Path, default=_REGISTRY)
    update.add_argument("--source-root", type=Path, default=_VENDOR)
    update.add_argument("--workspace", type=Path, default=_WORKSPACE)

    land = verbs.add_parser("land", help="commit a finished draft onto a branch")
    land.add_argument("name")
    land.add_argument("--registry", type=Path, required=True)
    land.add_argument("--branch", default=None, help="defaults to forge/<name>")
    land.add_argument("--by", required=True)
    land.add_argument("--on", default=None, help="approval date; defaults to today")
    land.add_argument("--workspace", type=Path, default=_WORKSPACE)

    explain = verbs.add_parser("explain", help="the long form of a diagnostic code")
    explain.add_argument("target", nargs="?")

    return root


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate. **The one place a combination of flags is judged.**

    `fill` takes a hand answer or a model, and argparse cannot express *these three are
    required unless that flag is set*. Doing it here rather than in the dispatcher keeps the
    rule beside the arguments it is about, and keeps `cli/__init__` free of decisions.
    """
    root = parser()
    args = root.parse_args(argv)

    if args.command == "fill":
        if args.model is not None:
            claimed = [
                name
                for name, value in (("value", args.value), ("--by", args.by), ("--why", args.why))
                if value
            ]
            if claimed:
                # `--by` on a model fill is a person putting their name to a model's answer,
                # which is the one thing the provenance design exists to keep apart.
                root.error(
                    f"--model settles a hole itself; drop {', '.join(claimed)}. "
                    "The model id is recorded as the filler."
                )
        elif not (args.field and args.value and args.by and args.why):
            root.error("a hand fill needs a field, a value, --by and --why (or use --model)")

    return args
