"""A code is declared in one place, emitted through one function, and both are checked.

`comeni_core/diagnostics.yml` declares every code; `coded()` is the only way one becomes text
(with `Diagnostic(code=)` for conformance, which builds an object rather than a message). That
gives two directions, and both were unguarded until 2026-08-16:

- **emitted but not declared** — a typo, or a `raise` outliving its registry entry. `coded()`
  refuses it, but only when the error fires. This scan runs whether or not anything fails.
- **declared but never emitted** — a code that exists in the document and in `mendel explain`
  and cannot happen. The operator's decision: a code nothing raises is a promise in a document
  that no code keeps.

**`emitted_by` names the package that raises**, and that is derived here rather than trusted:
`EmittedBy` had no `core` until this week, so twenty-three entries claimed a package that does
not raise them — a vocabulary that could not express the truth taught its users to lie to it.

**`UNLOCATABLE` is gone.** It existed because three emission shapes had to be matched by
pattern and one — `MD0202`, a report line without a colon — could not be. With a single shape
there is nothing to exempt.
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
    "ai": "mendel-ai",
    "api": "mendel-api",
}

EMISSION = re.compile(r"""(?:coded\(\s*|code=)["']([A-Z]{2}\d{4})["']""")
"""The two shapes an emission can take, and there are only two.

`coded("MD0001", …)` builds a message; `Diagnostic(code="MD0100", …)` builds an object that
carries the code as a field and validates it there. `\\s*` because wrapping a long call puts the
code on its own line.

**`[A-Z]{2}`, not `MD`.** This read `MD\\d{4}` until the forge landed. The blindness was not
symmetric, which is why it is worth writing down: `test_every_declared_code_is_emitted`
compares the whole registry against this scan, so it fired *loudly and falsely* the moment
`MF0002` was declared — the code was emitted, the scan simply could not see it. The other
direction stayed silently green and would have let an undeclared `MF9999` through. A guard
scoped to one prefix goes blind the day a second subsystem appears, and
`test_the_scan_sees_every_declared_prefix` is what makes that loud instead.
"""

SOURCES = [
    (path.relative_to(ROOT / "packages").parts[0], path.read_text())
    for path in sorted((ROOT / "packages").rglob("src/**/*.py"))
]


def _emitted() -> dict[str, set[str]]:
    """Every code emitted anywhere, mapped to the packages that emit it."""
    found: dict[str, set[str]] = {}
    for package, text in SOURCES:
        for match in EMISSION.finditer(text):
            found.setdefault(match.group(1), set()).add(package)
    return found


def test_the_scan_reached_the_sources():
    """A scan that reaches nothing reports nothing and passes."""
    assert len(SOURCES) > 30, f"only {len(SOURCES)} source files found; the scan is not scanning"
    assert len(_emitted()) > 40, "the emission pattern matches almost nothing; it has drifted"


def test_every_emitted_code_is_declared():
    """Belt to `coded()`'s braces: that check runs on the error path, this one runs always."""
    undeclared = sorted(set(_emitted()) - set(REGISTRY))
    assert undeclared == [], (
        "emitted in source but absent from diagnostics.yml — a typo, or a raise that outlived "
        f"its entry: {undeclared}"
    )


def test_every_declared_code_is_emitted():
    """The operator's decision, 2026-08-16.

    A reserved *band* stays legal: `MD0400`–`MD0499` is a comment in `diagnostics.yml`, not an
    entry, and reserving a range costs nothing. Reserving a *code* stops being legal, because a
    code that cannot happen still appears in the generated page and still answers
    `mendel explain` — it is documentation of a refusal that does not exist.
    """
    unemitted = sorted(set(REGISTRY) - set(_emitted()))
    assert unemitted == [], (
        f"declared in diagnostics.yml but emitted nowhere: {unemitted}"
    )


def test_every_code_is_owned_by_the_package_that_emits_it():
    wrong = []
    for code, packages in sorted(_emitted().items()):
        spec = REGISTRY.get(code)
        if spec is None:
            continue  # test_every_emitted_code_is_declared reports this one
        expected = PACKAGE_OF[spec.emitted_by.value]
        if expected not in packages:
            wrong.append(
                f"{code}: emitted_by={spec.emitted_by.value} ({expected}), "
                f"emitted in {', '.join(sorted(packages))}"
            )
    assert wrong == [], (
        "these name a package that does not emit them:\n    " + "\n    ".join(wrong)
    )


def test_a_docstring_mention_is_not_an_emission():
    """`diagnostics.py`'s own docstring quotes `f"MD0001: …"` as an example of the old shape.

    An emission is a *call*, which is why the pattern anchors on `coded(` and `code=` rather
    than on the code followed by a colon. The previous version anchored on the colon and had to
    reason about which mentions carried one.
    """
    assert "comeni-core" in _emitted()["MD0001"]
    core_text = next(text for package, text in SOURCES if "def coded(" in text)
    assert 'f"MD0001: {where} is not valid YAML"' in core_text, "the example moved; update this"


def test_the_scan_sees_every_declared_prefix():
    """A prefix the pattern does not match is a whole subsystem the guard is blind to.

    `MF` codes were declared and emitted while both ownership directions were expected to
    stay green, because `EMISSION` matched `MD` alone. The prefixes are a closed set —
    `EmittedBy` names the subsystems and the header of `diagnostics.yml` names the
    letters — so the pattern is checked against the registry rather than maintained by
    hand.
    """
    declared = {code[:2] for code in REGISTRY}
    seen = {code[:2] for code in _emitted()}
    missing = sorted(declared - seen)
    assert missing == [], (
        f"codes with these prefixes are declared but the emission scan matches none of "
        f"them; widen EMISSION: {missing}"
    )
