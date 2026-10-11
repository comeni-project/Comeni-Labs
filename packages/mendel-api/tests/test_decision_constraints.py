"""Current pointers cannot borrow another draft's answer or ungranted evidence."""

from datetime import UTC, datetime
from secrets import token_hex

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import engine
from mendel_api.services import drafts
from mendel_postgres import reachable
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")


def test_current_decisions_have_separate_typed_relations():
    names = set(inspect(engine).get_table_names())
    for family in ("input", "want", "fact", "producer", "parameter", "review"):
        assert f"pipeline_{family}" in names
        assert f"pipeline_{family}_revision" in names


def _subject(conn, draft_id, subject_id, current_id, key="read_length"):
    conn.execute(text("INSERT INTO pipeline_fact (id, draft_id, subject_key, current_id) "
                      "VALUES (:id, :draft, :key, :current)"),
                 {"id": subject_id, "draft": draft_id, "key": key, "current": current_id})


def _revision(conn, draft_id, subject_id, revision_id, observation_id=None):
    conn.execute(text("INSERT INTO pipeline_fact_revision "
                      "(id, draft_id, subject_id, observation_id, at) "
                      "VALUES (:id, :draft, :subject, :observation, :at)"),
                 {"id": revision_id, "draft": draft_id, "subject": subject_id,
                  "observation": observation_id, "at": datetime.now(UTC)})


def test_initial_pointer_can_be_inserted_before_its_revision():
    draft = drafts.create(DraftGraph(), "constraint", "ana")
    subject, revision = token_hex(16), token_hex(16)
    with engine.begin() as conn:
        _subject(conn, draft, subject, revision)
        _revision(conn, draft, subject, revision)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT current_id FROM pipeline_fact WHERE id=:id"),
                           {"id": subject}) == revision


def test_a_dangling_current_pointer_is_refused_at_commit():
    draft = drafts.create(DraftGraph(), "constraint", "ana")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _subject(conn, draft, token_hex(16), token_hex(16))


def test_a_current_pointer_cannot_name_another_drafts_revision():
    first = drafts.create(DraftGraph(), "first", "ana")
    second = drafts.create(DraftGraph(), "second", "ana")
    subject, revision = token_hex(16), token_hex(16)
    with engine.begin() as conn:
        _subject(conn, first, subject, revision)
        _revision(conn, first, subject, revision)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _subject(conn, second, token_hex(16), revision)


def test_duplicate_subjects_are_refused_even_with_distinct_revision_ids():
    draft = drafts.create(DraftGraph(), "constraint", "ana")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        for _ in range(2):
            subject, revision = token_hex(16), token_hex(16)
            _subject(conn, draft, subject, revision)
            _revision(conn, draft, subject, revision)


def test_selecting_ungranted_evidence_is_refused():
    draft = drafts.create(DraftGraph(), "constraint", "ana")
    subject, revision = token_hex(16), token_hex(16)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _subject(conn, draft, subject, revision)
        _revision(conn, draft, subject, revision, token_hex(16))


@pytest.mark.parametrize("actor", ["made_up", "unknown"])
def test_live_revision_cannot_have_unknown_or_undeclared_actor(actor):
    draft = drafts.create(DraftGraph(), "constraint", "ana")
    subject, revision = token_hex(16), token_hex(16)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _subject(conn, draft, subject, revision)
        _revision(conn, draft, subject, revision)
        conn.execute(text("UPDATE pipeline_fact_revision SET actor_kind=:actor WHERE id=:id"),
                     {"actor": actor, "id": revision})
