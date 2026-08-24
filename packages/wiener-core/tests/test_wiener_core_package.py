"""The package exists and is what it says it is.

Thin on purpose: at Task 1 `wiener_core` holds a docstring and nothing else, and a test that
pretended otherwise would be asserting types that arrive in Task 2.

**A second test was written here and deleted the same hour.** It asserted that the name in
`pyproject.toml` appears in `test_purity.py`'s `CLOSED_PACKAGES` — meant to catch the package
being renamed out from under its guard entry. It cannot fail: renaming it makes `uv` refuse the
workspace outright (*"references a workspace in `tool.uv.sources` … but is not a workspace
member"*) before pytest starts, and renaming the *directory* is what
`test_every_package_is_classified` already catches. Trying to watch it fail is what showed it
was inert, which is A14's method finding one of its own.
"""


def test_the_package_imports():
    import wiener_core

    assert wiener_core.__doc__ and "Pure" in wiener_core.__doc__
