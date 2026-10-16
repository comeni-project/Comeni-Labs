"""A test that means one tool names it, rather than taking the first file a glob finds.

`next(layer.rglob("align/contract.yml"))` meant STAR's aligner until HISAT2's landed beside it.
From then on the filesystem's order chose: STAR on one machine, HISAT2 on CI's runner, where
the test's text replacement changed nothing and three tests failed for a reason they were not
about (issue 296). This scans the suite for that shape and refuses a pattern that matches more
than one file in the registry. A test that truly wants any one file says so on the line:
`# any one will do`.
"""

import re

from support.paths import PACKAGES, REGISTRY, ROOT

SELF = ROOT / "tests/repo/test_unambiguous_registry_globs.py"
_NEXT_RGLOB = re.compile(r"""next\(\s*[\w.()/" ]*?\.rglob\(\s*"([^"]+)"\s*\)\s*\)""")


def _sites() -> list[tuple[str, int, str]]:
    found = []
    for path in sorted([*PACKAGES.rglob("tests/**/*.py"), *(ROOT / "tests").rglob("*.py")]):
        if path == SELF:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "# any one will do" in line:
                continue
            for pattern in _NEXT_RGLOB.findall(line):
                found.append((str(path.relative_to(ROOT)), number, pattern))
    return found


def test_the_scan_finds_the_shape_it_looks_for():
    """A loop is not an assertion: the scan must be able to see a `next(…rglob(…))`."""
    assert _NEXT_RGLOB.findall('star = next(layer.rglob("align/contract.yml"))') == [
        "align/contract.yml"
    ]


def test_no_test_takes_the_first_of_several_registry_files():
    ambiguous = [
        f"{where}:{number} rglob({pattern!r}) matches {count} registry files"
        for where, number, pattern in _sites()
        if (count := len(list(REGISTRY.rglob(pattern)))) > 1
    ]
    assert ambiguous == [], (
        "these take whichever file the filesystem lists first; name the tool's path instead: "
        f"{ambiguous}"
    )
