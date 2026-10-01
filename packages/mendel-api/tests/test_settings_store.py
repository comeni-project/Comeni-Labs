"""The settings store against the real database (spec §8)."""

import threading

import pytest
from mendel_api.db import session_scope
from sqlalchemy import text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — see this plan's Global Constraints"
)


def test_a_value_is_read_back(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    store.put("building.pacing", "together", by="someone")
    assert store.values() == {"building.pacing": "together"}
    assert store.who("building.pacing") == "someone"


def test_a_second_put_replaces_the_first(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    store.put("building.pacing", "together", by="a")
    store.put("building.pacing", "ask", by="b")
    assert store.values() == {"building.pacing": "ask"}
    assert store.who("building.pacing") == "b"


def test_structured_values_survive(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    value = [{"name": "Local Ollama", "endpoint": "http://ollama:11434"}]
    store.put("models.connections", value, by="a")
    assert store.values()["models.connections"] == value


def test_two_saves_to_different_keys_both_land(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    threads = [
        threading.Thread(target=store.put, args=(f"building.k{i}", i, "a")) for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.values() == {f"building.k{i}": i for i in range(8)}
