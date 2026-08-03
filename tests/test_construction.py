"""A `DataProfile` is built in exactly one place, and that place validates it.

Validation needs the measurement registry, which the model cannot hold, so it cannot live
in `__init__`. That makes an unvalidated profile constructible — and an unvalidated profile
with a nonsense measurement flows straight into routing. This is the third guard of its
kind, after `test_purity.py` and `test_egress.py`, and it exists for the same reason: the
alternative is a convention nobody notices breaking.
"""

import ast
import pathlib

ALLOWED = {
    # the one validated constructor
    "packages/comeni-core/src/comeni_core/measurement.py",
    # the model's own module, where the class is defined
    "packages/comeni-core/src/comeni_core/profile.py",
}


def test_data_profile_is_constructed_in_one_place():
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for package in ("comeni-core", "mendel-resolver", "mendel-compiler"):
        for py in sorted((root / "packages" / package / "src").rglob("*.py")):
            if str(py.relative_to(root)) in ALLOWED:
                continue
            for node in ast.walk(ast.parse(py.read_text())):
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    if name == "DataProfile":
                        offenders.append(f"{py.relative_to(root)}:{node.lineno}")
    assert offenders == [], (
        "build a profile through MeasurementRegistry.profile(), which validates it; "
        "these construct one directly: " + ", ".join(offenders)
    )
