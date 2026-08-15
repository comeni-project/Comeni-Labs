"""`emitted_by` names the package that raises the code, derived from the source.

The field's docstring said *"Which subsystem raises it"* and was false for roughly a third of
the registry: `EmittedBy` had no `core`, so every code raised inside `comeni-core` claimed
`compiler` or `resolver` instead. Six of the nine codes added on 2026-08-16 were wrong that way,
and they were written wrong **because the vocabulary offered no truthful option** — which is a
vocabulary teaching its users to lie to it.

**Absent and mismatched are reported separately.** Some codes have no f-string raise site:
`MD0100` is not a failure condition at all, and others are carried on a `Diagnostic` object
rather than interpolated into a message. A check that called those *wrong* would be switched off
within a week, so the two are different tests with different failure messages.
"""

import pathlib
import re

from comeni_core.diagnostics import REGISTRY

ROOT = pathlib.Path(__file__).parent.parent
PACKAGE_OF = {
    "core": "comeni-core",
    "resolver": "mendel-resolver",
    "compiler": "mendel-compiler",
    "forge": "mendel-forge",
    "api": "mendel-api",
}

UNLOCATABLE: tuple[str, ...] = ("MD0202",)
"""Codes with no locatable emission, pinned rather than counted.

A number going quietly up is how a list like this stops meaning anything. Adding a code this
cannot see should be a line somebody writes on purpose.

**`MD0202` is the only one, and it is the only code with `refuses: false`.** It is printed as a
*report* line — `f"  MD0202  {line}"`, aligned with two spaces — rather than raised with a
colon, because it tells a reader which values were carried forward rather than refusing
anything. Widening the pattern to catch it would mean matching a code followed by whitespace,
which every docstring mentioning one would also match.
"""


def _sources() -> list[tuple[str, str]]:
    """Every package source file, as `(package, text)`. Read once; this runs per code."""
    return [
        (path.relative_to(ROOT / "packages").parts[0], path.read_text())
        for path in sorted((ROOT / "packages").rglob("src/**/*.py"))
    ]


SOURCES = _sources()


def _raising_packages(code: str) -> set[str]:
    """Packages whose source emits this code, by either of the two forms that exist.

    **`MD0104:` — the code followed by a colon.** That is how every message-style refusal is
    written, whether the code leads the string (`f"MD0002: {where} …"`) or sits inside it
    (`"mendel: MD0223: a value was edited …"`). A docstring *mentioning* a code writes it in
    backticks without the colon, so the colon is what separates emission from reference — and
    that is checked, not assumed: `test_a_mention_is_not_an_emission` holds it.

    **`code="MD0100"` — the keyword form.** Conformance builds a `Diagnostic` object rather
    than interpolating a string, and a pattern that only knew the first form put all nine
    conformance codes in `UNLOCATABLE`, where they would have sat unexamined.
    """
    patterns = (re.compile(rf"{code}:"), re.compile(rf"""code=["']{code}["']"""))
    return {
        package
        for package, text in SOURCES
        if any(pattern.search(text) for pattern in patterns)
    }


def test_every_locatable_code_is_owned_by_the_package_that_raises_it():
    wrong = []
    for code, spec in sorted(REGISTRY.items()):
        raising = _raising_packages(code)
        if not raising:
            continue  # absent, not mismatched — see the module docstring
        expected = PACKAGE_OF[spec.emitted_by.value]
        if expected not in raising:
            wrong.append(
                f"{code}: emitted_by={spec.emitted_by.value} ({expected}), "
                f"raised in {', '.join(sorted(raising))}"
            )
    assert wrong == [], (
        "these name a package that does not raise them:\n    " + "\n    ".join(wrong)
    )


def test_the_unlocatable_codes_are_a_known_list():
    absent = tuple(sorted(code for code in REGISTRY if not _raising_packages(code)))
    assert absent == UNLOCATABLE, (
        "the set of codes with no locatable raise site moved:\n"
        f"    new:  {sorted(set(absent) - set(UNLOCATABLE))}\n"
        f"    gone: {sorted(set(UNLOCATABLE) - set(absent))}"
    )


def test_a_mention_is_not_an_emission():
    """The colon is what separates the two, and this is the assumption that rests on it.

    `materialise.py` says *"which is exactly what `MD0223` is for"* in a docstring and does not
    emit it; `artifact_verbs.py` writes `"mendel: MD0223: a value was edited"` and does. If a
    docstring ever gains a colon after a code, this fails and the pattern needs rethinking
    rather than the label.
    """
    assert "comeni-core" not in _raising_packages("MD0223"), (
        "a docstring mention is being read as an emission"
    )
    assert "mendel-compiler" in _raising_packages("MD0223")


def test_the_scan_reached_the_sources():
    """A scan that reaches nothing reports nothing and passes."""
    assert len(SOURCES) > 30, f"only {len(SOURCES)} source files found; the scan is not scanning"
