"""Integrity checks for the package-level compatibility surface."""

import comeni_core


def test_every_public_export_exists_and_is_listed_once():
    assert len(comeni_core.__all__) == len(set(comeni_core.__all__))
    assert all(hasattr(comeni_core, name) for name in comeni_core.__all__)


def test_the_package_exposes_a_version():
    assert comeni_core.__version__
