"""Frozen Part I.0 carry of a stored extraction into rows, version c6a2e8d4f159.

What a session's `extraction` stood for, written as the rows that replace it: each wanted type a
want revision by the model, unquoted; the model's suggested states and stated candidates pending
suggestions. Used by that migration and by the legacy conversion's writer once the column is
gone. Plain SQL against the schema as it stands; never today's models."""

import json
from datetime import UTC, datetime
from secrets import token_hex

import sqlalchemy as sa

VERSION = "c6a2e8d4f159"


def _suggest(conn, session_id: str, change: dict, at) -> None:
    conn.execute(sa.text(
        "INSERT INTO pipeline_authoring_suggestion "
        "(id, session_id, change, heard, state, created_at, shape_version) "
        "VALUES (:id, :sid, CAST(:change AS JSONB), false, 'pending', :at, 1)"),
        {"id": token_hex(16), "sid": session_id, "change": json.dumps(change), "at": at})


def _want(conn, draft_id: str, type_id: str, at) -> None:
    present = conn.execute(sa.text(
        "SELECT r.present FROM pipeline_want w JOIN pipeline_want_revision r "
        "ON r.id = w.current_id WHERE w.draft_id = :d AND w.subject_key = :k"),
        {"d": draft_id, "k": type_id}).scalar()
    if present:
        return
    seq = conn.execute(sa.text(
        "UPDATE pipeline_draft SET decision_sequence = decision_sequence + 1 "
        "WHERE id = :d RETURNING decision_sequence"), {"d": draft_id}).scalar_one()
    subject, revision_id = token_hex(16), token_hex(16)
    existing = conn.execute(sa.text(
        "SELECT id FROM pipeline_want WHERE draft_id = :d AND subject_key = :k"),
        {"d": draft_id, "k": type_id}).scalar()
    if existing is None:
        conn.execute(sa.text(
            "INSERT INTO pipeline_want (id, draft_id, subject_key, position, current_id) "
            "VALUES (:id, :d, :k, 0, :current)"),
            {"id": subject, "d": draft_id, "k": type_id, "current": revision_id})
    else:
        subject = existing
    conn.execute(sa.text(
        "INSERT INTO pipeline_want_revision (id, draft_id, subject_id, seq, actor_kind, who, "
        "legacy, action, at, type_id, states, present, shape_version) "
        "VALUES (:id, :d, :s, :seq, 'model', 'model', false, 'select', :at, :t, "
        "CAST('[]' AS JSONB), true, 1)"),
        {"id": revision_id, "d": draft_id, "s": subject, "seq": seq, "at": at, "t": type_id})
    conn.execute(sa.text("UPDATE pipeline_want SET current_id = :r WHERE id = :s"),
                 {"r": revision_id, "s": subject})


def carry(conn, session_id: str, draft_id: str, extraction, at=None) -> None:
    at = at or datetime.now(UTC)
    extraction = extraction if isinstance(extraction, dict) else json.loads(extraction)
    for type_id in extraction.get("want") or []:
        _want(conn, draft_id, type_id, at)
    for required in (extraction.get("suggested") or {}).get("required_states") or []:
        _suggest(conn, session_id, {"kind": "require", "subject": required["type_id"],
                                    "states": sorted(required.get("states") or []),
                                    "actor": "model"}, at)
    for stated in extraction.get("stated") or []:
        value = True if stated.get("kind") == "input" else stated.get("value")
        _suggest(conn, session_id, {"kind": stated["kind"], "subject": stated["subject"],
                                    "value": value, "actor": "model"}, at)
