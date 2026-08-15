#!/usr/bin/env python
"""One package's notes for one version, read out of the shared `CHANGELOG.md`.

The release workflow calls this to fill a GitHub Release's body. One changelog with a section
per package under each version heading, rather than a changelog per package: the repository is
one repository today, and four files describing the same commits is worse than one file with
headings. Reading *by heading* is what lets the split happen later without changing anything
here.

**Refuses rather than returning nothing.** A release cut with empty notes is worse than a
release that failed to cut: it looks finished. `MD0200`'s reasoning, applied to a shell script —
a value that reaches nothing should be refused at the point it is produced.

Deliberately not a general markdown parser. It finds `## [<version>]`, then `### <package>`
beneath it, and stops at the next heading of the same level or above. A changelog that needs
more structure than that is a changelog that has stopped being readable.
"""

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
