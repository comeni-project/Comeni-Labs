"""A `DataProfile` is built in exactly one place, and that place validates it.

Validation needs the measurement registry, which the model cannot hold, so it cannot live
in `__init__`. That makes an unvalidated profile constructible — and an unvalidated profile
with a nonsense measurement flows straight into routing.

**This scan is belt and braces, and saying so is load-bearing.** A2's fix re-checks every
measurement inside `resolve()`, so any profile that reaches resolution is validated
*regardless of how it was constructed*; that is the enforcement. This file raises the cost
of the mistake and makes it visible in review — which is a real job, and a different one.
Treating a spelling-matcher as the guarantee is exactly how A18 was written: `if name ==
"DataProfile"`, no alias resolution, one construction form, and
`from … import DataProfile as _DP; _DP.model_construct(...)` walked straight past it.
"""

import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_purity import (  # noqa: E402  — the one alias resolver and one package list
    BANLIST_PACKAGES,
    CLOSED_PACKAGES,
    _imported_names,
)

ALLOWED = {
    # the one validated constructor
    "packages/comeni-core/src/comeni_core/declared/measurement.py",
    # the model's own module, where the class is defined
    "packages/comeni-core/src/comeni_core/goal/profile.py",
}

BYPASSES = ("model_construct", "model_validate", "model_validate_json")
"""Pydantic's other constructors. `model_construct` skips validation entirely, and the two
`model_validate` forms build one from data a stranger may have written — a bundle, a goal
file. A18: the scan knew about `DataProfile(...)` and nothing else.

**`model_copy` was added for A62 and then removed, and the removal is the finding.** It does
build an instance without re-validating — `model_copy(update=…)` can arrive at a value that
could not be constructed — but it is an *instance* method, so it can never appear as
`<ClassAlias>.model_copy`, which is the only shape this scan matches. Adding it produced an
entry that cannot fire: unreachable, and therefore reading to the next person as a case
somebody had covered. Same call as Plan 1.15 Task 9's `_sole_premise` clause.

The real usage is `pipeline.model_copy(update={"gate": gate})` on an instance
(`pipeline_file.py`), and catching that needs to know the variable's type — which an AST scan
does not. **Recorded as residue on issue #26 rather than papered over**: `Pipeline` is frozen
and `model_copy` returns a new instance, so the mutation A66 is about is a different route,
and on a payload the copy still goes through `model_dump()`."""


_GUARDED = (*CLOSED_PACKAGES, *BANLIST_PACKAGES)
"""The packages this file scans, taken from `test_purity.py` rather than written out again.

A67, issue #31: both files globbed a hand-written package list, and a name that matches no
directory yields nothing while the assertion runs over an empty list — the reviewer mistyped
both keys and got `1 passed` in 0.04s. `test_purity.py::test_every_package_is_classified`
now refuses a package that is not in one of its three lists, and sharing the lists is what
makes that one check cover both files instead of two checks that can disagree.
"""


def _aliases_of(tree: ast.AST, name: str = "DataProfile") -> set[str]:
    """Every local name that resolves to `name` in this file.

    `import ... as` is the whole of A18: the guard compared a spelling, so renaming the
    import at the point of use was enough to disappear from it. **A62 is that the fix stopped
    at imports** — an assignment (`_P = Pipeline`) and a subclass (`class _P(Pipeline)`) each
    denote the class without one, and the reviewer built a `Pipeline` with `model_construct`
    through the first of those while the guard reported green.

    Iterated to a fixpoint rather than resolved in one pass, because `_A = Pipeline` followed
    by `_B = _A` is two hops and a guard that stops after one has a two-line bypass. The loop
    terminates because the alias set only grows and is bounded by the names in the file.
    """
    names = {name}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == name:
                    names.add(alias.asname or alias.name)
    while True:
        before = len(names)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Name)
                and node.value.id in names
            ):
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            elif isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id in names for base in node.bases
            ):
                names.add(node.name)
        if len(names) == before:
            return names


def _constructions(
    tree: ast.AST,
    aliases: set[str],
    modules: set[str],
    permitted: frozenset[str] = frozenset(),
) -> list[int]:
    """Every line that builds a `DataProfile`, by any spelling this scan can see.

    `permitted` exempts named *spellings*, never a whole file. `pipeline_file.load` needs
    `Pipeline.model_validate` — reading one back off disk is not materialising one, and the
    round trip is what the design rests on — but a bare `Pipeline(...)` in that same module
    must stay an offence. Exempting the file would have granted both, which is how a
    sole-constructor rule quietly becomes a suggestion.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # `DataProfile(...)`, or `_DP(...)` after an aliased import.
        if isinstance(func, ast.Name) and func.id in aliases:
            found.append(node.lineno)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            # `DataProfile.model_construct(...)` or `_DP.model_validate_json(...)` — a
            # bypass on a name that resolves to the model.
            bypass = (
                func.value.id in aliases
                and func.attr in BYPASSES
                and func.attr not in permitted
            )
            # `profile.DataProfile(...)` — the model reached through its module.
            through_module = func.attr in aliases and func.value.id in modules
            if bypass or through_module:
                found.append(node.lineno)
    return found


def test_data_profile_is_constructed_in_one_place():
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for package in _GUARDED:
        for py in sorted((root / "packages" / package / "src").rglob("*.py")):
            if str(py.relative_to(root)) in ALLOWED:
                continue
            tree = ast.parse(py.read_text())
            aliases = _aliases_of(tree)
            modules = _imported_names(tree)
            for line in _constructions(tree, aliases, modules):
                offenders.append(f"{py.relative_to(root)}:{line}")
    assert offenders == [], (
        "build a profile through MeasurementRegistry.profile(), which validates it; "
        "these construct one directly: " + ", ".join(offenders)
    )


PIPELINE_ALLOWED = {
    # the module the class is defined in
    "packages/comeni-core/src/comeni_core/artifact/pipeline.py",
    # **and the body of the one validated constructor.** `Pipeline.of` delegates to
    # `materialise.of`, so the `Pipeline(...)` call moved out of the class's own file when
    # issue #41 split it — the guard caught that within the hour, which is the guard working
    # rather than an argument for exempting the file loosely.
    #
    # Exempting the *file* rather than a spelling, deliberately and unlike `PIPELINE_READERS`
    # below: this is not a reader that happens to need one constructor, it **is** the
    # materialisation. `Pipeline.of` remains the only entry point and
    # `test_the_only_caller_of_materialise_of_is_pipeline_of` is what keeps that true.
    "packages/comeni-core/src/comeni_core/artifact/materialise.py",
}

PIPELINE_READERS = {
    # `pipeline_file.load` parses a `pipeline.yml` back into a `Pipeline`, and reading one
    # off disk is not materialising one — the file it reads was written by `Pipeline.of`.
    # Note what is exempted: the **spelling**, not the file. `Pipeline(...)` here is still an
    # offence, and `model_construct` — which skips validation entirely, so `MD0207`,
    # `MD0211`, `MD0212` and `MD0215` would never fire — still is too.
    "packages/mendel-compiler/src/mendel_compiler/pipeline_file.py": frozenset(
        {"model_validate"}
    ),
}


def test_pipeline_is_constructed_in_one_place():
    """`Pipeline.of()` or nowhere, for the reason `MeasurementRegistry.profile()` exists.

    A `Pipeline` assembled by hand is one with the contract-derived fields left empty — no
    `process`, no `call`, no frozen `ext.args` — and it would emit a `main.nf` calling a
    process with no name. Materialisation is the whole value of the type; a constructor that
    skips it is the type not doing its job.

    The scan walks `packages/*/src` and nothing else, so tests may still hand-build a
    pathological one. That matters: `test_a11_the_emitter_never_compares_two_resolved_values`
    deliberately constructs a node with duplicate params to prove the emitter survives it, and
    a sole-constructor rule covering `tests/` would have made that test unwritable.
    """
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for package in _GUARDED:
        for py in sorted((root / "packages" / package / "src").rglob("*.py")):
            if str(py.relative_to(root)) in PIPELINE_ALLOWED:
                continue
            tree = ast.parse(py.read_text())
            aliases = _aliases_of(tree, "Pipeline")
            modules = _imported_names(tree)
            permitted = PIPELINE_READERS.get(str(py.relative_to(root)), frozenset())
            for line in _constructions(tree, aliases, modules, permitted):
                offenders.append(f"{py.relative_to(root)}:{line}")
    assert offenders == [], (
        "build one through Pipeline.of(), which materialises it; these construct one "
        "directly: " + ", ".join(offenders)
    )


def test_an_assignment_alias_is_resolved(tmp_path):
    """A62, issue #26. `_aliases_of` collected names from `ast.ImportFrom` only, so an
    assignment denoted the class without an import-as and disappeared from the scan.

    Reviewer's probe was `_P = Pipeline` followed by `_P.model_construct(version=1)` in
    `pipeline_file.py`, with the guard green — a `Pipeline` built with no validation at all,
    which is the one thing `Pipeline.of` exists to prevent.
    """
    tree = ast.parse("from comeni_core.artifact.pipeline import Pipeline\n_P = Pipeline\n")
    assert "_P" in _aliases_of(tree, "Pipeline")


def test_a_subclass_is_resolved(tmp_path):
    """The other spelling. A subclass is the class for construction purposes, and
    `class _P(Pipeline)` binds a name the import-only resolver never saw."""
    tree = ast.parse(
        "from comeni_core.artifact.pipeline import Pipeline\n"
        "class _P(Pipeline):\n    pass\n"
    )
    assert "_P" in _aliases_of(tree, "Pipeline")


def test_an_alias_chain_is_resolved(tmp_path):
    """`_A = Pipeline` then `_B = _A`. One pass over the tree resolves the first and not the
    second, and a guard that stops after one hop is a guard with a two-line bypass."""
    tree = ast.parse(
        "from comeni_core.artifact.pipeline import Pipeline\n_A = Pipeline\n_B = _A\n_C = _B\n"
    )
    assert {"_A", "_B", "_C"} <= _aliases_of(tree, "Pipeline")


def test_an_unrelated_assignment_is_not_an_alias():
    """The negative. A guard that treats every assignment as an alias refuses code that
    never touched the class, and a refusal nobody can argue with is worse than a gap."""
    tree = ast.parse("from comeni_core.artifact.pipeline import Pipeline\n_other = SomethingElse\n")
    assert _aliases_of(tree, "Pipeline") == {"Pipeline"}


def test_model_copy_is_not_in_bypasses_and_the_reason_is_written_down():
    """A62's residue, pinned so it cannot be re-added without reading why it was removed.

    `model_copy` is an instance method, so `<ClassAlias>.model_copy` — the only shape this
    scan matches — is not valid Python. An entry for it is unreachable, and an unreachable
    entry reads to the next person as a case somebody covered.
    """
    assert "model_copy" not in BYPASSES


def test_the_only_caller_of_materialise_of_is_pipeline_of():
    """`materialise.py` is exempt as a *file*, so something has to hold its entry point.

    Issue #41 split `Pipeline.of`'s body into `materialise.of`, which means the `Pipeline(...)`
    call now lives outside the class's own module and the file is exempted wholesale. That is
    the right exemption — it is the materialisation, not a reader that needs one constructor —
    but it moves the question rather than answering it: what stops a second caller reaching
    `materialise.of` and skipping `Pipeline.of` entirely?

    This does. `Pipeline.of` is what `tests/test_construction.py`'s other guard names and what
    `docs/reference/pipeline-schema.md` tells a reader to use; a second door to the same room
    is a door nobody documented.
    """
    root = pathlib.Path(__file__).parent.parent
    callers = []
    for package in _GUARDED:
        for py in sorted((root / "packages" / package / "src").rglob("*.py")):
            if py.name in ("materialise.py", "pipeline.py"):
                continue
            imported = {
                alias.name
                for node in ast.walk(ast.parse(py.read_text()))
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            } | {
                alias.name
                for node in ast.walk(ast.parse(py.read_text()))
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            # The *import*, not the word. A first version searched the file text and named
            # three files that merely mention materialisation in a docstring — a guard whose
            # output is mostly prose is a guard people stop reading.
            if any(name.endswith("materialise") for name in imported):
                callers.append(str(py.relative_to(root)))
    assert callers == [], (
        "these reach `materialise` directly, bypassing `Pipeline.of` — the only entry point "
        "the guard above names and the only one the documentation describes:\n  "
        + "\n  ".join(callers)
    )
