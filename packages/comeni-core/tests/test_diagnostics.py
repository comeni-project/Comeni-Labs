"""Public behavior of the shared diagnostic registry."""

from comeni_core.diagnostics import REGISTRY, explain


def test_explain_returns_the_declared_long_form():
    explanation = explain("MD0001")

    assert explanation.startswith("MD0001\n\n")
    assert explanation.endswith(REGISTRY["MD0001"].explanation.rstrip())


def test_explain_lists_known_codes_for_an_unknown_code():
    explanation = explain("MD9999")

    assert explanation.startswith("MD9999 is not a diagnostic this version emits.")
    assert "MD0001" in explanation
