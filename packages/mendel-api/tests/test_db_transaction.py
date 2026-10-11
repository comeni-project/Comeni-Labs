"""One transaction per action (spec §11.2): every scope beneath it joins it."""

import secrets
from datetime import UTC, datetime

import pytest
from mendel_api import db
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft


def _draft(draft_id: str) -> PipelineDraft:
    return PipelineDraft(id=draft_id, who="tester", name="t", graph={"nodes": [], "edges": []},
                         updated_at=datetime.now(UTC), provenance={}, revision=0)


def _seen_elsewhere(draft_id: str) -> bool:
    """Whether another connection sees the row: what a job on the worker would read."""
    other = db.SessionLocal()
    try:
        return other.get(PipelineDraft, draft_id) is not None
    finally:
        other.close()


@pytest.fixture
def ids():
    made: list[str] = []
    yield made
    with session_scope() as s:
        for i in made:
            if (row := s.get(PipelineDraft, i)) is not None:
                s.delete(row)


def test_outside_a_transaction_each_scope_commits_on_its_own(ids):
    ids.append(i := secrets.token_hex(8))
    with session_scope() as s:
        s.add(_draft(i))
    assert _seen_elsewhere(i)
    assert not db.in_transaction()


def test_inside_a_transaction_nothing_is_seen_until_it_commits(ids):
    ids.append(i := secrets.token_hex(8))
    with db.transaction():
        assert db.in_transaction()
        with session_scope() as s:
            s.add(_draft(i))
        assert not _seen_elsewhere(i)
    assert _seen_elsewhere(i)


def test_an_exception_out_of_the_transaction_rolls_back_every_scope(ids):
    ids.append(i := secrets.token_hex(8))
    with pytest.raises(RuntimeError), db.transaction():
        with session_scope() as s:
            s.add(_draft(i))
        raise RuntimeError("broke after the write")
    assert not _seen_elsewhere(i)


def test_an_exception_caught_inside_rolls_back_only_its_own_scope(ids):
    """Review Focus 1: a `Refused` swallowed inside a command undoes only what its scope wrote."""
    ids.extend([kept := secrets.token_hex(8), undone := secrets.token_hex(8)])
    with db.transaction():
        with session_scope() as s:
            s.add(_draft(kept))
        with pytest.raises(ValueError), session_scope() as s:
            s.add(_draft(undone))
            s.flush()
            raise ValueError("refused")
    assert _seen_elsewhere(kept)
    assert not _seen_elsewhere(undone)


def test_a_transaction_does_not_open_inside_another():
    with db.transaction(), pytest.raises(RuntimeError, match="already open"), db.transaction():
        pass
