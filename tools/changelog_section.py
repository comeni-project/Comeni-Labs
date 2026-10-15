#!/usr/bin/env python
"""Print one package's release notes from the shared changelog.

The release workflow supplies a package and version. Read the body under `### <package>`
within `## [<version>]`, stopping at the next peer or parent heading. Missing headings and
`Unreleased` return exit code 2; successful extraction prints the body to stdout. This does
not parse arbitrary Markdown or write files."""

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent


def section(changelog: pathlib.Path, package: str, version: str) -> str:
    """The body under `### <package>` inside `## [<version>]`, stripped.

    Raises `LookupError` when either heading is absent, naming which one — a caller that
    cannot tell "no such version" from "no notes for this package" will report the wrong
    thing to whoever is cutting the release.
    """
    lines = changelog.read_text().splitlines()

    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^##\s+\[{re.escape(version)}\]", line)
    ]
    if not starts:
        raise LookupError(f"{changelog} has no `## [{version}]` heading")
    start = starts[0]

    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )

    within = [
        index
        for index in range(start + 1, end)
        if re.match(rf"^###\s+{re.escape(package)}\s*$", lines[index])
    ]
    if not within:
        raise LookupError(
            f"{changelog} has no `### {package}` section under `## [{version}]`. "
            "A release with empty notes looks finished; write the section or do not tag."
        )
    body_start = within[0] + 1

    body_end = next(
        (
            index
            for index in range(body_start, end)
            if lines[index].startswith("### ") or lines[index].startswith("## ")
        ),
        end,
    )
    return "\n".join(lines[body_start:body_end]).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("package", help="e.g. comeni-core")
    parser.add_argument("version", help="e.g. 0.2.0 — never `Unreleased`")
    parser.add_argument("--changelog", type=pathlib.Path, default=ROOT / "CHANGELOG.md")
    args = parser.parse_args()

    if args.version == "Unreleased":
        # A tag is never `Unreleased`, and shipping that section would publish the notes for
        # everything that has *not* been released.
        print("`Unreleased` is not a version; a release needs a version heading.", file=sys.stderr)
        return 2
    try:
        print(section(args.changelog, args.package, args.version))
    except LookupError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
