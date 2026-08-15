"""The code registry is data, and a code that is not declared cannot be emitted.

Invariant 7's shape applied to diagnostics: a closed vocabulary. `EXPLANATIONS` was a Python
dict beside a hand-maintained table in `docs/reference/`, and the two could disagree with
nothing to notice — a code in one and not the other, or a `says` that drifted from the long form
it summarises.

The old guard for that would have been a test asserting every emittable code has an explanation.
A test can only find codes on paths it executes. Validating at construction makes the bad state
unrepresentable instead, which is strictly stronger and is why no such test exists here.
"""

import pathlib

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
        Diagnostic(code="MD9999", where="x", summary="s", detail="d", fix="f")


def test_a_declared_code_still_constructs():
    """Regression guard for over-correction: the eight real codes must still work."""
    from mendel_compiler.conformance import Diagnostic

    d = Diagnostic(code="MD0104", where="nf-core/star/align@1.11.0",
                   summary="s", detail="d", fix="f")
    assert d.code == "MD0104"


def test_the_generated_table_is_current():
    """`make check` runs this, and so does the nightly workflow against `main`.

    A generated artifact that drifts from its source is a lie with a timestamp — the same
    reason `tools/generate_types.py --check` exists. No Action commits the regenerated file:
    a bypass on a protected branch exists forever and for everything, and a self-healing
    `main` means nobody ever sees the drift. A failing check teaches; a silent fix does not.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "tools/generate_diagnostics_doc.py", "--check"],
        cwd=pathlib.Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

# --- `coded()`: the one place a code becomes text ---


def test_coded_prefixes_the_message_with_the_code():
    from comeni_core.diagnostics import coded

    assert coded("MD0001", "a thing went wrong") == "MD0001: a thing went wrong"


def test_coded_refuses_an_undeclared_code():
    """The whole point: a string literal cannot be wrong about this any more."""
    from comeni_core.diagnostics import UnknownDiagnosticError, coded

    with pytest.raises(UnknownDiagnosticError) as caught:
        coded("MD9999", "a thing went wrong")
    assert "MD9999" in str(caught.value)


def test_coded_refuses_a_near_miss():
    """`MD00001` is the realistic typo — one digit too many, and it reads right."""
    from comeni_core.diagnostics import UnknownDiagnosticError, coded

    with pytest.raises(UnknownDiagnosticError):
        coded("MD00001", "a thing went wrong")


def test_coded_leaves_the_message_alone():
    """No wrapping, no rstrip, no reflow.

    A message that changes shape is a message whose tests start asserting the formatter rather
    than the text — and several of these messages are multi-line with deliberate indentation.
    """
    from comeni_core.diagnostics import coded

    message = "line one\n  line two, indented\n"
    assert coded("MD0001", message) == f"MD0001: {message}"
