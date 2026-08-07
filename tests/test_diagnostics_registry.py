"""The code registry is data, and a code that is not declared cannot be emitted.

Invariant 7's shape applied to diagnostics: a closed vocabulary. `EXPLANATIONS` was a Python
dict beside a hand-maintained table in `docs/reference/cli.md`, and the two could disagree with
nothing to notice — a code in one and not the other, or a `says` that drifted from the long form
it summarises.

The old guard for that would have been a test asserting every emittable code has an explanation.
A test can only find codes on paths it executes. Validating at construction makes the bad state
unrepresentable instead, which is strictly stronger and is why no such test exists here.
"""

import pytest

from comeni_core import diagnostics

CONFORMANCE = ("MD0100", "MD0101", "MD0102", "MD0103", "MD0104", "MD0105", "MD0106", "MD0107")


def test_every_existing_conformance_code_is_declared():
    for code in CONFORMANCE:
        assert code in diagnostics.REGISTRY, code


def test_a_spec_carries_a_fix_and_an_explanation():
    spec = diagnostics.spec_for("MD0104")
    assert spec.fix, "a diagnostic without a fix is half a diagnostic"
    assert spec.explanation


def test_an_undeclared_code_is_refused():
    with pytest.raises(diagnostics.UnknownDiagnosticError):
        diagnostics.spec_for("MD9999")


def test_says_is_one_line():
    """It is rendered into a markdown table row; a newline breaks the table silently rather
    than loudly. Root C's `Line`/`Text` split, in a new place."""
    for code, spec in diagnostics.REGISTRY.items():
        assert "\n" not in spec.says, code


def test_the_registry_is_read_one_way():
    """Root G: `yaml.safe_load` keeps the **last** of two duplicate keys, silently. A
    `diagnostics.yml` declaring `MD0104` twice would load one and lose one, and the loss is
    exactly the sort a reviewer reading the file cannot see. This registry goes through the
    strict loader like every other declared file in the pure packages.
    """
    import inspect

    from comeni_core import yaml_strict

    source = inspect.getsource(diagnostics)
    assert "yaml_strict" in source, "the registry must not call yaml.safe_load directly"
    assert hasattr(yaml_strict, "load")


def test_a_diagnostic_cannot_carry_an_undeclared_code():
    """The bad state is unrepresentable, not merely tested for.

    `Diagnostic.where` is still `contract_id` at this point in Plan 1.10 — Task 11 renames it,
    and this call site changes with it.
    """
    from mendel_compiler.conformance import Diagnostic

    with pytest.raises(ValueError, match="MD9999"):
        Diagnostic(code="MD9999", contract_id="x", summary="s", detail="d", fix="f")


def test_a_declared_code_still_constructs():
    """Regression guard for over-correction: the eight real codes must still work."""
    from mendel_compiler.conformance import Diagnostic

    d = Diagnostic(code="MD0104", contract_id="nf-core/star/align@1.11.0",
                   summary="s", detail="d", fix="f")
    assert d.code == "MD0104"
