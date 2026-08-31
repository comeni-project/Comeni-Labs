"""The command line, as a parser. One function, so `main` reads as dispatch rather than setup.

Split out for issue #41: fifty lines of `add_argument` were the first thing anybody opening
`cli.py` met, before any verb.

Every `help=` string moved verbatim, and several carry an argument rather than a description —
`--dry-run` explains why there is no separate `verify` verb, and `--force` names the target
directory as *another pipeline's evidence*. Those are the reason each flag is shaped as it is,
and losing one to a rewrite would lose the reason.
"""

import argparse
from pathlib import Path

from mendel_compiler.gates import Gate


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mendel")
    parser.add_argument(
        "command",
        choices=[
            "build",
            "profile",
            "publish",
            "upgrade",
            "emit",
            "explain",
            "docs",
            "conformance",
        ],
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help=(
            "a diagnostic code for `explain`, or a pipeline.yml for `emit`, `upgrade` "
            "and `publish`"
        ),
    )
    parser.add_argument("--goal", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "`upgrade` only: report what would move and write nothing. This is `verify` — "
            "a separate verb comparing digests would answer a strictly weaker question, "
            "and two answers to 'is this still what it says it is' is how they disagree."
        ),
    )
    parser.add_argument(
        "--have",
        action="append",
        default=None,
        help="a type id the laboratory holds; repeat. `profile` only.",
    )
    # Not `required=True`: `mendel explain MD0104` writes nothing and loads nothing, so
    # demanding an output directory for it would be argparse describing the wrong verb.
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--gate", type=Gate, default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "`upgrade` only: write into a --out directory that already holds a *different* "
            "pipeline.yml, replacing it. Refused without this, because that directory is "
            "another pipeline's evidence."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "`docs` only: write nothing and exit 1 if any page disagrees with the data. "
            "A check that repaired what it measured could never fail twice."
        ),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        action="append",
        default=None,
        help=(
            "a registry layer — a directory of files that each carry a `declares:` line; "
            "repeat to stack overlays, later layers win"
        ),
    )
    return parser
