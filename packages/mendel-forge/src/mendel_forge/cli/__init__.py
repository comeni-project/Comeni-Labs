"""The command line: argv in, a rendered result out. **No logic.**

Every verb is three steps — build the request model, call the one `ops` function, render
the result — and the HTTP app does the same three with a different first and last. That
is what makes `forge draft --json` and `POST /drafts` the same payload rather than two
payloads that happen to agree today.

**A refusal exits 1; a usage error exits 2.** `mendel` returns 2 for both, and the
difference here is deliberate: a coded refusal is something `forge explain` can talk
about, and a flag you did not type is not. The exit code is the first thing a script
branches on, so the two should not look alike.
"""

import datetime
import re
import sys

from mendel_compiler import conformance

from mendel_forge import ops
from mendel_forge.cli import parse, render
from mendel_forge.workspace import Workspace

_CODE = re.compile(r"\bMF\d{4}\b")
"""`MF` only. A forge refusal is explained by `forge explain`; pointing a reader at
`mendel explain` for a code `mendel` never raises would send them to the wrong verb."""


def _with_pointer(message: str) -> str:
    found = _CODE.search(message)
    return f"{message}\n  run: forge explain {found.group()}" if found else message


def main(argv: list[str] | None = None) -> int:
    """Entry point. Wraps `_run` so a user mistake is a message, not a traceback."""
    try:
        return _run(argv)
    except (OSError, KeyError, ValueError) as exc:
        print(_with_pointer(f"forge: {exc}"), file=sys.stderr)
        return 1


def _emit(args, result, text: str) -> int:
    print(result.model_dump_json(indent=2) if args.json else text)
    return 0


def _run(argv: list[str] | None = None) -> int:
    parser = parse.parser()
    args = parser.parse_args(argv)

    if args.command == "explain":
        if not args.target:
            parser.error("explain needs a code, e.g. `forge explain MF0004`")
        print(conformance.explain(args.target))
        return 0

    if args.command == "sources":
        return _emit(args, ops.sources_(), render.sources(ops.sources_()))

    if args.command == "discover":
        result = ops.discover(
            ops.DiscoverRequest(source_root=args.source_root, source=args.source)
        )
        return _emit(args, result, render.discover(result))

    if args.command == "draft":
        result = ops.draft(
            ops.DraftRequest(
                ref=args.ref,
                name=args.name,
                version=args.version,
                registry_root=args.registry,
                source_root=args.source_root,
                workspace_root=args.workspace,
            )
        )
        return _emit(args, result, render.draft(result))

    if args.command == "list":
        names = Workspace(root=args.workspace).names()
        print(names if args.json else render.listing(names))
        return 0

    if args.command == "show":
        result = ops.show(
            ops.ShowRequest(
                name=args.name,
                registry_root=args.registry,
                source_root=args.source_root,
                workspace_root=args.workspace,
            )
        )
        return _emit(args, result, render.show(result))

    if args.command == "fill":
        value = [part.strip() for part in args.value.split(",")] if args.list else args.value
        result = ops.fill(
            ops.FillRequest(
                name=args.name,
                field=args.field,
                value=value,
                by=args.by,
                why=args.why,
                workspace_root=args.workspace,
            )
        )
        return _emit(args, result, render.fill(result))

    if args.command == "verify":
        result = ops.verify_(
            ops.VerifyRequest(
                name=args.name,
                registry_root=args.registry,
                source_root=args.source_root,
                workspace_root=args.workspace,
            )
        )
        print(result.model_dump_json(indent=2) if args.json else render.verify(result))
        return 1 if result.refused else 0

    if args.command == "check":
        result = ops.check(
            ops.CheckRequest(registry_root=args.registry, source_root=args.source_root)
        )
        print(result.model_dump_json(indent=2) if args.json else render.check(result))
        return 1 if result.drift else 0

    if args.command == "update":
        result = ops.update(
            ops.UpdateRequest(
                contract_id=args.contract_id,
                name=args.name,
                registry_root=args.registry,
                source_root=args.source_root,
                workspace_root=args.workspace,
            )
        )
        return _emit(args, result, render.draft(result))

    result = ops.land(
        ops.LandRequest(
            name=args.name,
            registry=args.registry,
            branch=args.branch or f"forge/{args.name}",
            approved_by=args.by,
            approved_at=args.on or datetime.date.today().isoformat(),
            workspace_root=args.workspace,
        )
    )
    return _emit(args, result, render.land(result))
