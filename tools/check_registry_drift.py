"""Has a registry fix landed in one repository and not the other?

`registry/` here and github.com/comeni-project/comeni-registry hold the same layer today,
and are *meant* to diverge: the published registry grows into a real one, while this repo
keeps enough hand-written data for its tests. So "they must be identical" would fight the
design.

What must never happen is a file existing in both and saying different things. That is a
contract fix applied once and forgotten, and nothing else would notice it — the two repos
have no shared CI, no shared history after the extraction, and each is green on its own.

Files present in only one side are reported and do not fail: that is the growth the split
exists to allow.

    uv run python tools/check_registry_drift.py ../comeni-registry

Runs nightly rather than per pull request: it needs the network, and the fast lane is
deliberately offline.
"""

import hashlib
import pathlib
import sys

# Only the four declared kinds. A README or a licence differing between the two is
# expected — they are different repositories with different audiences — and failing on
# those would train everyone to ignore this check.
KINDS = ("contracts", "measurements", "rules", "vocabularies")


def _files(layer: pathlib.Path) -> dict[str, str]:
    """Every declared file under the layer, by relative path, with its content hash."""
    found: dict[str, str] = {}
    for kind in KINDS:
        root = layer / kind
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.yml")):
            found[path.relative_to(layer).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: check_registry_drift.py <path to a comeni-registry checkout>",
            file=sys.stderr,
        )
        return 2

    here = pathlib.Path(__file__).parent.parent / "registry"
    there = pathlib.Path(argv[1])
    if not (there / "registry.yml").exists():
        print(f"{there} does not look like a registry layer: no registry.yml", file=sys.stderr)
        return 2

    ours, theirs = _files(here), _files(there)

    diverged = sorted(name for name in ours.keys() & theirs.keys() if ours[name] != theirs[name])
    only_here = sorted(ours.keys() - theirs.keys())
    only_there = sorted(theirs.keys() - ours.keys())

    for name in only_here:
        print(f"  only in Comeni-Labs      {name}")
    for name in only_there:
        print(f"  only in comeni-registry  {name}")

    if not diverged:
        print(
            f"no drift: {len(ours.keys() & theirs.keys())} shared files agree "
            f"({len(only_here)} only here, {len(only_there)} only there)"
        )
        return 0

    print("\nthese files exist in both repositories and disagree:", file=sys.stderr)
    for name in diverged:
        print(f"  DRIFT  {name}", file=sys.stderr)
    print(
        f"\n{len(diverged)} file(s) drifted. A fix has landed in one repository and not the\n"
        f"other. Decide which is right, copy it across, and say so in the commit — the two\n"
        f"repositories have no shared history, so nothing else will tell you.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
