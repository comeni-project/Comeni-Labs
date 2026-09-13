"""The preview a person watches grow, and the artifact they keep — one serializer, one set of bytes.

Task 13's server half. **Preview is pure**: it writes nothing, keeps nothing, and makes no gate
available. **Preview and Keep agree byte for byte**, because both materialise the same draft with
the same goal, the same sidecar and the same `ai` block, and both call `pipeline_file.dump`. And an
authored draft carrying a model's choice **can be kept**, which it could not before the keep route
stated the draft's AI points.
"""

import json
from pathlib import Path

import pytest
from comeni_core import yaml_strict
from comeni_core.plan.draft import DraftGraph
from fastapi.testclient import TestClient
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, ProposalState
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import authoring, drafts
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
def clean(monkeypatch, tmp_path):
    for name in ("COMENI_AI_MODEL", "MENDEL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path / "kept")
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
    yield tmp_path / "kept"


def _complete(mode: Mode = Mode.BUILD) -> tuple[str, str]:
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = authoring.open_session(draft_id, mode=mode, who="ana")
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=1)
    goal = Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))
    authoring.move(
        session_id, st.Event.GOAL_ACCEPTED, row_version=2, goal=goal.model_dump(mode="json")
    )
    proposal = authoring.start_building(session_id)
    if mode is Mode.SPAWN:
        return session_id, draft_id
    while proposal is not None:
        revision = authoring.read(session_id)["revision"]
        proposal = authoring.settle_step(
            proposal, ProposalState.ACCEPTED, expected_revision=revision, by="ana"
        ).next_proposal
    return session_id, draft_id


def test_a_preview_writes_nothing_and_keeps_nothing(clean):
    session_id, draft_id = _complete()
    client = TestClient(create_app())

    shown = client.get(f"/api/pipeline/authoring/{session_id}/preview").json()

    assert shown["state"] == "ready" and shown["text"].startswith("#")
    assert drafts.artifact_path(draft_id) is None
    assert not clean.exists(), "previewing created an output directory"
    assert client.get(f"/api/pipeline/drafts/{draft_id}/artifact").status_code == 404


def test_the_kept_file_is_byte_for_byte_the_preview(clean):
    """**The checkpoint's server half.** No second implementation serialized either of them."""
    session_id, draft_id = _complete()
    client = TestClient(create_app())

    shown = client.get(f"/api/pipeline/authoring/{session_id}/preview").json()["text"]
    kept = client.post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert kept.status_code == 200, kept.text

    assert drafts.artifact_path(draft_id).read_text() == shown
    reloaded = client.get(f"/api/pipeline/drafts/{draft_id}/artifact").json()["text"]
    assert reloaded == shown


def test_keeping_an_authored_draft_makes_no_second_draft(clean):
    session_id, draft_id = _complete()
    client = TestClient(create_app())
    before = client.get("/api/pipeline/drafts").json()["total"]
    client.post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert client.get("/api/pipeline/drafts").json()["total"] == before


def test_an_empty_draft_previews_as_empty_and_not_as_yaml(clean):
    draft_id = drafts.create(DraftGraph(), "empty", "ana")
    session_id = authoring.open_session(draft_id, mode=Mode.BUILD, who="ana")
    shown = TestClient(create_app()).get(f"/api/pipeline/authoring/{session_id}/preview").json()
    assert shown == {"revision": 0, "state": "empty", "text": "", "findings": []}


def test_an_illegal_partial_graph_previews_its_findings_and_not_fake_yaml(clean):
    session_id, draft_id = _complete()
    graph = authoring.read(session_id)["graph"]
    graph["edges"].append({"from_node": "samtools_sort", "from_port": "bam",
                           "to_node": "star_genomegenerate", "to_port": "fasta"})
    authoring.record_edit(session_id, DraftGraph.model_validate(graph), by="ana")

    shown = TestClient(create_app()).get(f"/api/pipeline/authoring/{session_id}/preview").json()
    assert shown["state"] == "illegal"
    assert shown["text"] == ""
    assert shown["findings"] and shown["findings"][0].startswith("MD05")


def test_a_kept_spawn_draft_says_a_model_was_available_and_used(clean, monkeypatch):
    """The keep route states an authored draft's AI points, as its preview does.

    **What this does not claim, recorded because the first version of this test claimed it:**
    that `MD0225` would refuse the same draft kept without them. It does not — `MD0225` checks
    model-sourced *settings*, and a model's choice of *which contract fills a step* is not one. So
    a draft kept through the unguarded path records `available: []` beside a model's decision, and
    nothing refuses the contradiction. The route closes it for the product; the check is a gap.
    """
    import yaml

    monkeypatch.setenv("COMENI_AI_MODEL", "fake/test")
    session_id, draft_id = _complete(Mode.SPAWN)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        blueprint = json.loads(json.dumps(row.blueprint))
        step = next(s for s in blueprint["pipeline"]["steps"] if s["id"] == "star_align")
        step["why"].update(tier=4, source="model")
        blueprint["pipeline"]["decisions"].append({
            "kind": "producer",
            "key": "producer:alignment.bam",
            "subject": "producer:alignment.bam",
            "reason": "splice-aware", "resolved_by": "claude-opus-5", "tier": 4,
            "chosen": step["module"]["contract_id"], "candidates": [step["module"]["contract_id"]],
        })
        row.blueprint = blueprint
    authoring.spawn_forward(session_id)

    kept = TestClient(create_app()).post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert kept.status_code == 200, kept.text
    artifact = yaml.safe_load(drafts.artifact_path(draft_id).read_text())
    assert artifact["ai"] == {"available": ["prompt", "tier-4"], "used": ["prompt", "tier-4"]}

    unguarded = yaml.safe_load(drafts.keep(draft_id).read_text())
    assert unguarded["ai"]["available"] == [], "the gap this docstring records has closed"
