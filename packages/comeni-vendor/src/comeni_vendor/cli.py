"""Transport over `ops.py`. It holds no logic — same split as `mendel_forge.cli`."""

import argparse
import sys
from pathlib import Path

from comeni_core.diagnostics import coded

from comeni_vendor.ops import VendorError, add, check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="comeni-vendor",
        description=(
            "Put a tool's source into a registry layer, and check it still matches its pin. "
            "Not part of the build path — a build reads a layer that is already on disk."
        ),
    )
    verbs = parser.add_subparsers(dest="verb", required=True)

    fetch = verbs.add_parser("add", help="fetch a module into a layer at a pinned commit")
    fetch.add_argument("ref", help="<source>:<ident> — nf-core:star/align")
    fetch.add_argument("--sha", required=True, help="the commit to vendor at. Never a branch")
    fetch.add_argument("--registry", required=True, type=Path, help="the layer to write into")
    fetch.add_argument("--licence", default="MIT", help="SPDX identifier, e.g. MIT")
    fetch.add_argument("--repo", help="clone URL, for a source this tool does not know")
    fetch.add_argument("--path", help="where under --repo the module sits")
    fetch.add_argument(
        "--exclude",
        action="append",
        help="a path under the module not to copy. Repeatable. Defaults to `tests`",
    )

    verify = verbs.add_parser("check", help="does every module/ still hold what it declares")
    verify.add_argument("--registry", required=True, type=Path)
    verify.add_argument(
        "--upstream",
        action="store_true",
        help="re-fetch at the pin and compare. Needs the network; the default check does not",
    )

    args = parser.parse_args(argv)
    try:
        if args.verb == "add":
            return _add(args)
        return _check(args)
    except VendorError as error:
        print(f"comeni-vendor: {error}", file=sys.stderr)
        return 1


def _add(args: argparse.Namespace) -> int:
    where = add(
        args.ref,
        sha=args.sha,
        registry=args.registry,
        licence=args.licence,
        repo=args.repo,
        path=args.path,
        excluded=args.exclude,
    )
    print(f"vendored {args.ref} at {args.sha[:12]} into {where}")
    return 0


def _check(args: argparse.Namespace) -> int:
    found = check(args.registry, upstream=args.upstream)
    if not found:
        print(f"comeni-vendor: {args.registry} declares no modules", file=sys.stderr)
        return 1
    for one in found:
        detail = f" — {one.detail}" if one.detail else ""
        print(f"{one.verdict:>8}  {one.module_id}{detail}")
    # **`unpinned` is not a failure.** A laboratory's own process has no upstream to compare
    # against, and the run said so on its own line rather than counting it as a pass.
    wrong = [one for one in found if one.verdict in ("edited", "moved")]
    if wrong:
        print(
            coded(
                "MV0002",
                f"{len(wrong)} of {len(found)} modules no longer match what they declare.",
            ),
            file=sys.stderr,
        )
        return 1
    return 0
