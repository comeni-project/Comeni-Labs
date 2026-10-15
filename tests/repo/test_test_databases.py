"""Test collection uses isolated databases independently of development configuration."""

import os

from sqlalchemy.engine import make_url
from support.databases import MENDEL_TEST_URL, WIENER_TEST_URL, configure


def test_application_database_urls_are_replaced_with_test_defaults():
    environ = {
        "MENDEL_DATABASE_URL": "postgresql://developer/important",
        "WIENER_DATABASE_URL": "postgresql://developer/important",
    }
    configure(environ)
    assert environ["MENDEL_DATABASE_URL"] == MENDEL_TEST_URL
    assert environ["WIENER_DATABASE_URL"] == WIENER_TEST_URL
    assert environ["WIENER_TEST_DATABASE_URL"] == WIENER_TEST_URL


def test_explicit_test_databases_are_used_by_both_applications():
    environ = {
        "MENDEL_TEST_DATABASE_URL": "postgresql://isolated/mendel_test",
        "WIENER_TEST_DATABASE_URL": "postgresql://isolated/wiener_test",
    }
    configure(environ)
    assert environ["MENDEL_DATABASE_URL"] == environ["MENDEL_TEST_DATABASE_URL"]
    assert environ["WIENER_DATABASE_URL"] == environ["WIENER_TEST_DATABASE_URL"]


def test_selecting_test_databases_does_not_enable_required_database_mode():
    environ = {}
    configure(environ)
    assert "COMENI_REQUIRE_DB" not in environ


def test_collection_configures_the_application_before_its_engine_is_imported():
    from mendel_api.db import engine

    selected = os.environ.get("MENDEL_TEST_DATABASE_URL", MENDEL_TEST_URL)
    assert engine.url == make_url(selected)
