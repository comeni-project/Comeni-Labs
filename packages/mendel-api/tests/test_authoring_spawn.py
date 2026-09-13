"""Spawn: the same engine as Build, with the safe answers given by policy.

**Task 12's checkpoint is the first test**: Build and Spawn over the RNA-seq fixture end at one
draft and one YAML, while their histories differ — Build's steps answered by a person, Spawn's by
the author the policy relied on. The second half is the one that keeps "Spawn" from meaning "AI
wrote this": over a tier-4 model choice, authorship differs **only** at that step.
"""

import asyncio
import json
from pathlib import Path

import pytest
from comeni_ai import Client, ModelAccess
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import AiProvenance
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from comeni_core.plan.tiers import ValueSource
from fastapi.testclient import TestClient
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, Phase, ProposalState
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.routes import authoring as routes
from mendel_api.services import authoring, authoring_jobs, drafts
from mendel_resolver.goal import Goal
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def clean(monkeypatch):
    for name in ("COMENI_AI_MODEL", "MENDEL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
    yield


def _goal() -> Goal:
    return Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))


def _resolving(mode: Mode) -> str:
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = authoring.open_session(draft_id, mode=mode, who="ana")
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=1)
    authoring.move(session_id, st.Event.GOAL_ACCEPTED, row_version=2,
                   goal=_goal().model_dump(mode="json"))
    return session_id


def _draft(session_id: str) -> tuple[DraftGraph, DraftProvenance, int, str]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        return (
            DraftGraph.model_validate(draft.graph),
            DraftProvenance.model_validate(draft.provenance or {}),
            draft.revision,
            row.draft_id,
        )


def _build_by_hand(session_id: str) -> None:
    proposal = authoring.start_building(session_id)
    while proposal is not None:
        revision = _draft(session_id)[2]
        proposal = authoring.settle_step(
            proposal, ProposalState.ACCEPTED, expected_revision=revision, by="ana"
        ).next_proposal


def _shape(graph: DraftGraph):
    return (
        sorted((n.id, n.contract_id) for n in graph.nodes),
        sorted((e.from_node, e.from_port, e.to_node, e.to_port) for e in graph.edges),
    )


def _rewrite_step(session_id: str, node: str, **why) -> None:
    """Make one step of the stored blueprint a tier-4 choice — the shipped registry has no tie."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        blueprint = json.loads(json.dumps(row.blueprint))
        for step in blueprint["pipeline"]["steps"]:
            if step["id"] == node:
                step["why"].update(why)
        if why.get("source") == "model":
            contract = next(s for s in blueprint["pipeline"]["steps"] if s["id"] == node)["module"]
            blueprint["pipeline"]["decisions"].append({
                "kind": "producer", "key": "producer:alignment.bam",
                "subject": "producer:alignment.bam", "reason": "splice-aware",
                "resolved_by": "claude-opus-5", "tier": 4,
                "chosen": contract["contract_id"], "candidates": [contract["contract_id"]],
            })
        row.blueprint = blueprint


# ── the checkpoint ────────────────────────────────────────────────────────────────────────


def test_build_and_spawn_converge_on_one_draft_and_one_yaml(clean):
    """**Task 12's checkpoint.** Same goal, same registry, two policies — one pipeline."""
    build = _resolving(Mode.BUILD)
    _build_by_hand(build)
    spawn = _resolving(Mode.SPAWN)
    authoring.start_building(spawn)
    stop = authoring.spawn_forward(spawn)

    assert stop.node is None, stop.reason
    assert authoring.current_phase(spawn) is Phase.COMPLETE

    b_graph, b_prov, _, b_draft = _draft(build)
    s_graph, s_prov, _, s_draft = _draft(spawn)
    assert _shape(b_graph) == _shape(s_graph)

    ai = AiProvenance(available=[], used=[])
    assert drafts.preview(b_draft, ai=ai)[1] == drafts.preview(s_draft, ai=ai)[1]

    # The histories differ: a person answered Build; Spawn recorded the author it relied on.
    b_by = {d["by"] for d in authoring.read(build)["history"]}
    s_by = {d["by"] for d in authoring.read(spawn)["history"]}
    assert b_by == {"ana"}
    assert s_by == {"resolver"}


def test_spawn_calls_a_step_the_resolver_settled_the_resolvers(clean):
    """*Spawn is not permission to label the whole graph AI-authored.*"""
    spawn = _resolving(Mode.SPAWN)
    authoring.start_building(spawn)
    authoring.spawn_forward(spawn)
    _, provenance, _, _ = _draft(spawn)

    assert provenance.nodes, "nothing was stamped, so this asserted nothing"
    assert {entry.selection.source for entry in provenance.nodes} == {ValueSource.RESOLVER}


# ── where it stops, and who wrote what ────────────────────────────────────────────────────


def test_spawn_stops_on_a_tier_four_choice_no_model_made(clean):
    """A missing model, a refusal, no candidate the model could take — all arrive as a tier-4 step
    the flag settled, and Spawn leaves it for the card Build would have shown."""
    spawn = _resolving(Mode.SPAWN)
    authoring.start_building(spawn)
    _rewrite_step(spawn, "star_align", tier=4, source="resolver")

    stop = authoring.spawn_forward(spawn)
    view = authoring.read(spawn)

    assert stop.node == "star_align"
    assert view["phase"] == "building"
    assert view["pending_proposal"]["payload"]["node"] == "star_align"


def test_author_differs_only_at_the_step_a_model_chose(clean):
    """The tier-4 half of the checkpoint: the model authored its choice and nothing else."""
    spawn = _resolving(Mode.SPAWN)
    authoring.start_building(spawn)
    _rewrite_step(spawn, "star_align", tier=4, source="model")

    stop = authoring.spawn_forward(spawn)
    _, provenance, _, _ = _draft(spawn)
    authors = {entry.node: entry.selection for entry in provenance.nodes}

    assert stop.node is None, stop.reason
    assert authors["star_align"].source is ValueSource.MODEL
    assert authors["star_align"].by == "claude-opus-5"
    assert {n for n, s in authors.items() if s.source is not ValueSource.RESOLVER} == {"star_align"}


def test_a_moved_registry_stops_spawn_rather_than_applying_across_it(clean, monkeypatch):
    from mendel_api.services import blueprint as bp

    spawn = _resolving(Mode.SPAWN)
    authoring.start_building(spawn)
    monkeypatch.setattr(bp, "registry_digest", lambda roots: "sha256:" + "0" * 64)

    stop = authoring.spawn_forward(spawn)
    assert stop.reason == "MI0206"
    assert _draft(spawn)[2] == 0


def test_a_build_session_is_never_advanced_by_the_policy(clean):
    build = _resolving(Mode.BUILD)
    authoring.start_building(build)
    assert authoring.spawn_forward(build).node is None
    assert _draft(build)[2] == 0


# ── end to end through the job and the route ──────────────────────────────────────────────


GOAL_ANSWER = {
    "goal": {
        "have": [{"type_id": "fastq.reads"}, {"type_id": "annotation.gtf"},
                 {"type_id": "genome.fasta"}],
        "want": ["counts.matrix"],
        "constraints": {"required_states": {"counts.matrix": ["gene_level"]}},
        "profile": {"measurements": [
            {"measurement": "read_length", "value": 150, "source": "goal"},
            {"measurement": "strandedness", "value": "reverse", "source": "goal"},
        ]},
    },
    "have": "reads, a genome and its annotation", "do": "count reads per gene",
    "get": "a gene-level counts matrix", "questions": [],
}


class Answers:
    def __init__(self, body: str) -> None:
        self.body = body
        self.sent: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.sent.append(prompt)
        return self.body


def _spawn_turn(monkeypatch, answer: dict) -> tuple[str, Answers]:
    transport = Answers(json.dumps(answer))
    monkeypatch.setattr(authoring_jobs, "_client",
                        lambda: Client(ModelAccess(model="fake/test"), transport=transport))

    async def queued(*args):
        return True

    monkeypatch.setattr(authoring_jobs, "enqueue_turn", queued)
    client = TestClient(create_app())
    started = client.post(
        "/api/pipeline/authoring", json={"prompt": "gene counts", "mode": "spawn"}
    )
    session_id = started.json()["session"]["id"]
    seq = started.json()["session"]["turns"][-1]["seq"]
    asyncio.run(authoring_jobs.answer_authoring_turn({}, session_id, seq))
    return session_id, transport


def test_a_spawn_session_with_no_open_question_completes_from_one_turn(clean, monkeypatch):
    session_id, transport = _spawn_turn(monkeypatch, GOAL_ANSWER)
    view = authoring.read(session_id)

    assert view["phase"] == "complete"
    assert len(transport.sent) == 1, "a model call for a step the resolver settled"
    goal = next(d for d in view["history"] if d["kind"] == "goal")
    assert goal["by"] == "model"


def test_a_spawn_goal_with_an_open_question_pauses_for_a_person(clean, monkeypatch):
    """§1.2: Spawn pauses only on material ambiguity — the grouping question above all."""
    asking = {**GOAL_ANSWER, "questions": [{
        "asks": "how do the files group?", "why_open": "it changes the pipeline",
        "choices": ["paired", "independent"], "exhaustive": False,
    }]}
    session_id, _ = _spawn_turn(monkeypatch, asking)
    assert authoring.read(session_id)["phase"] == "goal_review"


def test_available_ai_points_follow_the_installation_not_the_mode(monkeypatch):
    """What `pipeline.yml` says was *available* must not depend on the mode, or two modes over one
    goal emit two artifacts. It was mode-dependent for three tasks."""
    monkeypatch.setenv("COMENI_AI_MODEL", "fake/test")
    none = DraftProvenance()
    assert routes._ai_for(Mode.BUILD, none).available == routes._ai_for(Mode.SPAWN, none).available
