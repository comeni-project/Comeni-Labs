"""Public behavior of the shared diagnostic registry."""

from comeni_core.diagnostics import REGISTRY, explain


def test_explain_returns_the_declared_long_form():
    spec = REGISTRY["MD0001"]
    explanation = explain("MD0001")

    assert explanation.startswith(f"MD0001: {spec.says}\n\n")
    assert spec.explanation.rstrip() in explanation


def test_explain_ends_with_what_to_write():
    """`fix:` is required on every code and was printed by neither CLI (#67)."""
    spec = REGISTRY["MD0104"]
    explanation = explain("MD0104")

    head, _, fix = explanation.partition("\n\nFix:\n")
    assert fix and spec.explanation.rstrip() in head
    assert fix.splitlines()[0] == "  " + spec.fix.strip().splitlines()[0]


def test_explain_lists_known_codes_for_an_unknown_code():
    explanation = explain("MD9999")

    assert explanation.startswith("MD9999 is not a diagnostic this version emits.")
    assert "MD0001" in explanation
