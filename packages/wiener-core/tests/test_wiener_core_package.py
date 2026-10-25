"""Package-level import and identity smoke checks."""


def test_the_package_imports():
    import wiener_core

    assert wiener_core.__doc__ and "Pure" in wiener_core.__doc__
