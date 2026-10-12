"""Frozen legacy conversion never guesses chooser roles or overwrites manual graphs."""

import json

import pytest
from test_authoring_samples import clean as clean


def _snapshot(**changes):
    from mendel_api.migration_data.decisions_v1 import Snapshot

    goal = {
        "have": [{"type_id": "fastq.reads"}],
        "want": ["counts.matrix"],
        "profile": {"read_length": 150},
    }
    values = dict(
        draft_id="draft",
        session_id="session",
        phase="complete",
        at="wrap",
        session_goal=json.dumps(goal),
        draft_goal=json.dumps(goal),
        facts=json.dumps(
            [
                {
                    "kind": "measurement",
                    "subject": "read_length",
                    "value": 50,
                    "source": "person_said",
                }
            ]
        ),
        graph='{"nodes": [], "edges": []}',
        provenance="{}",
        blueprint="{}",
        reviewed="[]",
        policy=None,
        decision_revision=0,
    )
    values.update(changes)
    return Snapshot(**values)


def test_confirmed_goal_is_active_and_conflicting_old_facts_are_only_observations():
    from mendel_api.migration_data.decisions_v1 import convert

    plan = convert(_snapshot())
    assert plan.disposition == "confirmed"
    active = next(s for s in plan.selections if s.family == "fact")
    assert json.loads(active.fields)["value"] == 150
    assert active.actor_kind == "unknown" and active.legacy
    assert any(json.loads(e.fields)["value"] == 50 for e in plan.observations)


def test_ambiguous_goal_preserves_manual_work_and_retires_only_the_session():
    from mendel_api.migration_data.decisions_v1 import convert

    plan = convert(_snapshot(draft_goal='{"want": ["qc.report"]}'))
    assert plan.disposition == "ambiguous_manual"
    assert plan.retired and plan.reason == "ambiguous"
    assert not plan.selections


def test_gathering_facts_are_selected_but_model_suggestions_are_not():
    from mendel_api.migration_data.decisions_v1 import convert

    plan = convert(
        _snapshot(
            phase="gathering",
            at="reply",
            draft_goal=None,
            session_goal=json.dumps(
                {"want": ["counts.matrix"], "stated": [{"subject": "paired", "value": True}]}
            ),
        )
    )
    assert plan.disposition == "gathering" and not plan.retired
    assert json.loads(plan.extraction)["want"] == ["counts.matrix"]
    assert not any(s.family == "want" for s in plan.selections)
    assert len([s for s in plan.selections if s.family == "fact"]) == 1


def test_an_obsolete_continuation_is_archived_instead_of_inventing_a_new_node():
    from mendel_api.migration_data.decisions_v1 import convert

    plan = convert(_snapshot(at="choose-old-mode"))
    assert plan.disposition == "obsolete_protocol" and plan.reason == "obsolete_protocol"
    assert plan.retired


def test_named_channels_and_measured_evidence_keep_their_original_meaning():
    from mendel_api.migration_data.decisions_v1 import convert

    goal = json.dumps(
        {
            "have": [
                {"type_id": "genome.annotation.gtf", "name": "reference"},
                {"type_id": "genome.annotation.gtf", "name": "sample"},
            ],
            "want": ["counts.matrix"],
            "profile": {
                "measurements": [
                    {
                        "measurement": "read_length",
                        "value": 150,
                        "source": "measured",
                        "pieces": ["fastq@1.0.0"],
                        "evidence": {"records": 12},
                    }
                ]
            },
        }
    )
    plan = convert(_snapshot(session_goal=goal, draft_goal=goal))
    inputs = [json.loads(s.fields) for s in plan.selections if s.family == "input"]
    assert [i["name"] for i in inputs] == ["reference", "sample"]
    fact = next(json.loads(s.fields) for s in plan.selections if s.family == "fact")
    assert fact["origin"] == "measured" and fact["pieces"] == ["fastq@1.0.0"]


def test_current_row_sessions_are_not_reinterpreted_as_legacy():
    from mendel_api.migration_data.decisions_v1 import convert

    plan = convert(_snapshot(decision_revision=2))
    assert plan.disposition == "already_rows" and not plan.selections


def test_a_manual_completed_graph_remains_manual_even_when_its_goal_is_recoverable():
    from mendel_api.migration_data.decisions_v1 import convert

    blueprint = json.dumps(
        {
            "pipeline": {
                "steps": [
                    {
                        "id": "align",
                        "module": {"contract_id": "nf-core/star/align@2.7.11a"},
                        "settings": [],
                        "inputs": [],
                    }
                ]
            }
        }
    )
    plan = convert(_snapshot(blueprint=blueprint, reviewed='[{"node": "align"}]'))
    assert plan.disposition == "manual_confirmed" and not plan.retired
    assert plan.selections


def test_sql_conversion_is_idempotent_and_keeps_graph_name_and_old_observations(clean):
    from datetime import UTC, datetime
    from secrets import token_hex

    from mendel_api.db import engine, session_scope
    from mendel_api.migration_data.decisions_v1 import apply, convert
    from mendel_api.models import PipelineAuthoringSession, PipelineDraft
    from mendel_api.services import decisions, session
    from mendel_api.services.decision_migration import inventory
    from sqlalchemy import text

    snapshot = _snapshot(draft_id=token_hex(16), session_id=token_hex(16))
    with session_scope() as db:
        db.add(
            PipelineDraft(
                id=snapshot.draft_id,
                name="Preserved",
                who="old",
                graph=json.loads(snapshot.graph),
                provenance={"nodes": []},
                updated_at=datetime.now(UTC),
                revision=4,
            )
        )
        db.flush()
        db.add(
            PipelineAuthoringSession(
                id=snapshot.session_id,
                draft_id=snapshot.draft_id,
                phase="complete",
                at="wrap",
                who="old",
                row_version=3,
                blueprint={},
                registry_digest="",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    with engine.begin() as connection:
        before = connection.execute(
            text("SELECT count(*) FROM pipeline_fact_revision")
        ).scalar_one()
        report = inventory(connection)
        assert report == []  # a new draft has no legacy snapshot to inventory
        assert (
            connection.execute(text("SELECT count(*) FROM pipeline_fact_revision")).scalar_one()
            == before
        )
        loaded = snapshot
        converted = convert(loaded)
        assert apply(connection, loaded, converted, at=datetime.now(UTC))
        assert not apply(connection, loaded, converted, at=datetime.now(UTC))
    current = session.read(snapshot.session_id)
    assert current["name"] == "Preserved" and current["graph"] == json.loads(snapshot.graph)
    assert current["revision"] == 4 and current["pending_proposal"]["kind"] == "goal"
    assert next(f.value for f in decisions.read(snapshot.draft_id).facts) == 150
    history = decisions.history(snapshot.draft_id, "read_length")
    assert any(h["value"] == 50 and not h["selected"] for h in history)
    assert all(h.get("actor_kind", "unknown") == "unknown" for h in history)


def test_populated_previous_head_upgrades_and_converts_without_changing_saved_bytes(monkeypatch):
    import os
    import subprocess
    import sys
    from datetime import UTC, datetime
    from pathlib import Path
    from secrets import token_hex

    from mendel_api import db
    from mendel_api.services import decisions, session
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    name = "mendel_migration_test_" + token_hex(6)
    admin = create_engine(db.engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    clone_url = db.engine.url.set(database=name)
    clone = create_engine(clone_url)
    package = Path(__file__).resolve().parents[1]
    try:
        env = dict(os.environ, MENDEL_DATABASE_URL=clone_url.render_as_string(hide_password=False))

        def upgrade(target):
            done = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", target],
                cwd=package,
                env=env,
                capture_output=True,
                text=True,
            )
            assert done.returncode == 0, done.stderr

        upgrade("f8b4d2c6a913")
        goal = _snapshot().draft_goal
        with clone.begin() as connection:
            connection.execute(
                text("""INSERT INTO pipeline_draft
                (id,who,name,graph,goal,provenance,updated_at,revision,kept_graph,kept_digest)
                VALUES ('legacy-draft','old','Saved label',CAST(:graph AS JSON),CAST(:goal AS JSON),
                        CAST(:provenance AS JSON),:at,4,:kept_graph,:kept_digest)"""),
                dict(
                    graph=_snapshot().graph,
                    goal=goal,
                    provenance='{"nodes":[]}',
                    at=datetime.now(UTC),
                    kept_graph="sha256:" + "a" * 64,
                    kept_digest="sha256:" + "b" * 64,
                ),
            )
            connection.execute(
                text("""INSERT INTO pipeline_authoring_session
                (id,draft_id,phase,at,goal,facts,blueprint,registry_digest,reviewed,
                 row_version,who,created_at,updated_at)
                VALUES ('legacy-session','legacy-draft','complete','wrap',CAST(:goal AS JSON),
                        CAST(:facts AS JSON),'{}','', '[]',3,'old',:at,:at)"""),
                dict(goal=goal, facts=_snapshot().facts, at=datetime.now(UTC)),
            )
            before = connection.execute(
                text("""SELECT name,graph::text,provenance::text,
                kept_graph,kept_digest,revision FROM pipeline_draft""")
            ).one()
        upgrade("head")
        with clone.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT disposition FROM pipeline_decision_migration")
                ).scalar_one()
                == "confirmed"
            )
            after = connection.execute(
                text("""SELECT name,graph::text,provenance::text,
                kept_graph,kept_digest,revision FROM pipeline_draft""")
            ).one()
        assert after == before
        monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=clone, expire_on_commit=False))
        view = session.read("legacy-session")
        assert view["goal"]["profile"]["measurements"][0]["value"] == 150
        assert view["pending_proposal"]["kind"] == "goal"
        assert decisions.history("legacy-draft", "read_length")
    finally:
        clone.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_retired_sessions_are_readable_but_all_commands_refuse_mutation(clean):
    import pytest
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineAuthoringSession
    from mendel_api.services import session
    from mendel_authoring import commands as c
    from test_authoring_samples import _gathering

    sid = _gathering(["counts.matrix"])
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        row.retired, row.retirement_reason = True, "ambiguous"
    assert session.read(sid)["retired"]
    with pytest.raises(ValueError, match="MI0217.*archived"):
        session.perform(c.Say(sid, "try changing this"))


def test_the_cutover_removes_duplicate_live_goal_columns():
    from mendel_api.db import engine
    from sqlalchemy import inspect

    schema = inspect(engine)
    assert "goal" not in {c["name"] for c in schema.get_columns("pipeline_draft")}
    assert not (
        {"goal", "facts", "reviewed", "policy"}
        & {c["name"] for c in schema.get_columns("pipeline_authoring_session")}
    )


def test_frozen_conversion_retains_the_independent_required_state_order():
    from comeni_core.declared.measurement import MeasurementRegistry
    from comeni_core.goal.asked import Goal
    from mendel_api.migration_data.decisions_v1 import convert
    from mendel_authoring.decisions import Decisions, WantDecision
    from support.paths import REGISTRY

    goal = Goal(
        want=["counts.matrix", "alignment.bam"],
        constraints={
            "required_states": [
                {"type_id": "alignment.bam", "states": ["coordinate_sorted"]},
                {"type_id": "counts.matrix", "states": ["gene_level"]},
            ]
        },
    )
    encoded = goal.model_dump_json()
    converted = convert(_snapshot(session_goal=encoded, draft_goal=encoded, facts="[]"))
    assert converted.disposition == "confirmed"
    selected = Decisions(
        wants=[
            WantDecision.model_validate_json(s.fields)
            for s in converted.selections
            if s.family == "want"
        ]
    )
    assert selected.goal(MeasurementRegistry.load(REGISTRY)).model_dump(mode="json") == (
        goal.model_dump(mode="json")
    )


@pytest.mark.parametrize("decision", ["accepted", "rejected"])
def test_empty_legacy_gathering_can_answer_its_recovered_goal_card(clean, monkeypatch, decision):
    from datetime import UTC, datetime
    from secrets import token_hex

    from mendel_api.db import engine, session_scope
    from mendel_api.migration_data.decisions_v1 import apply, convert
    from mendel_api.models import PipelineAuthoringSession, PipelineDraft
    from mendel_api.services import session
    from mendel_authoring import commands as c

    monkeypatch.setattr(session, "_enqueue", lambda job: True)
    snapshot = _snapshot(
        draft_id=token_hex(16), session_id=token_hex(16), phase="gathering", at="reply",
        draft_goal=None, session_goal=json.dumps({"want": ["counts.matrix"]}), facts="[]",
    )
    converted = convert(snapshot)
    assert converted.disposition == "gathering" and not converted.selections
    with session_scope() as db:
        db.add(PipelineDraft(
            id=snapshot.draft_id, name="Before the first answer", who="old",
            graph=json.loads(snapshot.graph), provenance={"nodes": []},
            updated_at=datetime.now(UTC), revision=4,
        ))
        db.flush()
        db.add(PipelineAuthoringSession(
            id=snapshot.session_id, draft_id=snapshot.draft_id, phase="gathering", at="reply",
            who="old", row_version=3, blueprint={}, registry_digest="",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
    with engine.begin() as connection:
        assert apply(connection, snapshot, converted, at=datetime.now(UTC))
    # Reload the actual persisted offer, then answer it through the real dispatcher.
    current = session.read(snapshot.session_id)
    assert current["phase"] == "goal_review"
    proposal = current["pending_proposal"]
    session.perform(c.DecideGoal(proposal["id"], decision, current["revision"], "ana"))
    changed = session.read(snapshot.session_id)
    assert changed["phase"] != "goal_review"
