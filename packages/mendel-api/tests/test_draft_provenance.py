"""What an edit does to who settled what.

**The failure this file exists to catch is silent and it inverts the product claim.** A pipeline
a model spawned, edited by a person in one place, must not come out of `keep` as a pipeline a
person drew. If it does, `pipeline.yml` says a human decided things no human ever saw — and the
artifact's whole job is that you can say why each part of it is there.

So every test below edits **one** thing and asserts that exactly one thing changed author.
"""

import secrets
from datetime import UTC, datetime

import pytest
from comeni_core.artifact.pipeline import AiPoint, AiProvenance
from comeni_core.plan.draft import (
    ChannelSettled,
    DraftChannel,
    DraftGraph,
    DraftNode,
    DraftParam,
    DraftProvenance,
    NodeSettled,
    ParamSettled,
    Settled,
)
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import drafts
from sqlalchemy import text

STAR = "nf-core/star/align@1.11.0"
HISAT = "nf-core/hisat2/align@2.2.1"
COUNTS = "nf-core/subread/featurecounts@2.0.6"

MODEL = "claude-opus-5"


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


def _graph(contract: str = STAR, mqs: int | None = 10, scope: str | None = None) -> DraftGraph:
    return DraftGraph(
        nodes=[
            DraftNode(id="align", contract_id=contract),
            DraftNode(
                id="counts",
                contract_id=COUNTS,
                params=(
                    [DraftParam(name="min_mqs", value=mqs, why="low-MAPQ reads are noise")]
                    if mqs is not None
                    else []
                ),
            ),
        ],
        channels=(
            [DraftChannel(scope=scope, why="one annotation per sample", ports=("counts.gtf",))]
            if scope
            else []
        ),
    )


def _spawned() -> DraftProvenance:
    """What a Spawn session leaves behind: the model chose the aligner and answered the setting,
    and the resolver settled that the counting step belongs at all."""
    return DraftProvenance(
        nodes=[
            NodeSettled(
                node="align",
                selection=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="STAR for a splice-aware count matrix",
                    by=MODEL,
                ),
                presence=Settled(
                    source=ValueSource.RESOLVER,
                    tier=Tier.STRUCTURAL,
                    reason="counts require an alignment",
                ),
            ),
            NodeSettled(
                node="counts",
                selection=Settled(
                    source=ValueSource.RESOLVER,
                    tier=Tier.STRUCTURAL,
                    reason="the only contract producing counts.matrix",
                ),
                presence=Settled(
                    source=ValueSource.RESOLVER,
                    tier=Tier.STRUCTURAL,
                    reason="the goal wants counts.matrix",
                ),
            ),
        ],
        params=[
            ParamSettled(
                key="counts.min_mqs",
                settled=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="10 is nf-core's default here",
                    by=MODEL,
                ),
            )
        ],
    )


@pytest.fixture
def spawned_draft() -> str:
    """A draft with a full sidecar, as a Spawn session would leave it."""
    with session_scope() as session:
        session.execute(
            text(
                "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
                "pipeline_authoring_session, pipeline_draft"
            )
        )
    draft_id = secrets.token_hex(16)
    with session_scope() as session:
        session.add(
            PipelineDraft(
                id=draft_id,
                who="tester",
                name="spawned",
                graph=_graph().model_dump(mode="json"),
                updated_at=datetime.now(UTC),
                goal=None,
                provenance=_spawned().model_dump(mode="json"),
                revision=0,
            )
        )
    return draft_id


def _ai_was_wired() -> AiProvenance:
    """What a Spawn session's caller states about its own configuration.

    Stated rather than derived, and `test_a_spawned_draft_kept_without_declaring_a_model_is_
    refused` is the other half: without this, `MD0225` refuses the artifact outright.
    """
    return AiProvenance(available=[AiPoint.TIER_4], used=[AiPoint.TIER_4])


def _sidecar(draft_id: str) -> DraftProvenance:
    with session_scope() as session:
        return DraftProvenance.model_validate(session.get(PipelineDraft, draft_id).provenance)


# ── the five edits ────────────────────────────────────────────────────────────────────────


def test_a_pure_position_move_changes_no_provenance(spawned_draft):
    """**Structural, not incidental.** `DraftGraph` carries no coordinates — layout is
    `dag-core`'s, computed from the graph — so moving a node produces a byte-identical graph and
    there is nothing for the diff to find. This test is what notices if a coordinate is ever
    added to the draft, because then a drag would start re-authoring the pipeline."""
    before = _sidecar(spawned_draft)
    drafts.update(spawned_draft, _graph())
    assert _sidecar(spawned_draft) == before


def test_replacing_a_step_reauthors_that_step_and_nothing_else(spawned_draft):
    """Swapping STAR for HISAT2 is the person's choice of *which contract*. It is not a decision
    about the counting step, and it is not a decision about the setting."""
    drafts.update(spawned_draft, _graph(contract=HISAT))
    after = _sidecar(spawned_draft)

    assert after.node("align").selection.source == ValueSource.HUMAN
    assert after.node("counts").selection.source == ValueSource.RESOLVER
    assert after.param("counts.min_mqs").source == ValueSource.MODEL
    assert after.param("counts.min_mqs").by == MODEL


def test_replacing_a_step_keeps_the_reason_it_exists(spawned_draft):
    """The per-decision granularity §1.8 asks for. *Which contract fills this step* changed;
    *whether this step exists at all* did not, and the resolver's structural reasoning for it
    must survive somebody swapping an aligner."""
    drafts.update(spawned_draft, _graph(contract=HISAT))
    presence = _sidecar(spawned_draft).node("align").presence
    assert presence.source == ValueSource.RESOLVER
    assert presence.reason == "counts require an alignment"


def test_editing_one_setting_reauthors_only_that_setting(spawned_draft):
    """**Task 4's checkpoint.** Editing one setting in a spawned draft changes the author of that
    setting only; untouched steps stay attributed to whoever actually chose them."""
    drafts.update(spawned_draft, _graph(mqs=30))
    after = _sidecar(spawned_draft)

    assert after.param("counts.min_mqs").source == ValueSource.HUMAN
    assert after.node("align").selection.source == ValueSource.MODEL
    assert after.node("align").selection.by == MODEL
    assert after.node("counts").selection.source == ValueSource.RESOLVER


def test_clearing_a_setting_drops_its_entry(spawned_draft):
    """A setting nobody sets has no author. Keeping the entry would leave the artifact citing a
    model's reason for a value that is now whatever the ladder decides."""
    drafts.update(spawned_draft, _graph(mqs=None))
    assert _sidecar(spawned_draft).param("counts.min_mqs") is None


def test_deleting_a_step_drops_its_entry(spawned_draft):
    """`retaining`'s half, through the real path: an entry whose subject is gone is dropped
    rather than left to attach itself to a future step with the same id."""
    drafts.update(
        spawned_draft,
        DraftGraph(nodes=[DraftNode(id="counts", contract_id=COUNTS)]),
    )
    after = _sidecar(spawned_draft)
    assert after.node("align") is None
    assert after.node("counts") is not None


def test_a_channel_scope_edit_is_the_persons(spawned_draft):
    """Splitting a channel is a judgement about the experiment — per-sample annotation over a
    shared one is a different analysis. Whoever makes it owns it."""
    drafts.update(spawned_draft, _graph(scope="sample"))
    settled = _sidecar(spawned_draft).channel(("counts.gtf",))
    assert settled is not None
    assert settled.source == ValueSource.HUMAN


def test_an_unchanged_channel_keeps_its_author(spawned_draft):
    """The other direction, and the one a naive diff gets wrong: re-posting the same channel must
    not re-author it."""
    with session_scope() as session:
        row = session.get(PipelineDraft, spawned_draft)
        row.graph = _graph(scope="sample").model_dump(mode="json")
        row.provenance = _spawned().model_copy(
            update={
                "channels": [
                    ChannelSettled(
                        ports=("counts.gtf",),
                        settled=Settled(
                            source=ValueSource.MODEL,
                            tier=Tier.AMBIGUOUS,
                            reason="the samplesheet names one annotation per sample",
                            by=MODEL,
                        ),
                    )
                ]
            }
        ).model_dump(mode="json")

    drafts.update(spawned_draft, _graph(scope="sample"))
    settled = _sidecar(spawned_draft).channel(("counts.gtf",))
    assert settled.source == ValueSource.MODEL
    assert settled.by == MODEL


# ── creation, and the drafts that predate all of this ─────────────────────────────────────


def test_a_hand_drawn_draft_starts_with_no_sidecar():
    """Empty is the truthful default: nobody has recorded anything about a graph somebody is
    still drawing, and `ir_of` treats that as today's behaviour byte for byte."""
    with session_scope() as session:
        session.execute(
            text(
                "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
                "pipeline_authoring_session, pipeline_draft"
            )
        )
    draft_id = drafts.create(_graph(), "by hand", "tester")
    with session_scope() as session:
        assert session.get(PipelineDraft, draft_id).provenance in ({}, None)


def test_an_old_draft_with_no_sidecar_still_updates(spawned_draft):
    """Every draft written before this column existed has `provenance = {}`, and editing one must
    not raise. The stamping still happens — a change is still the person's — it simply has
    nothing to retain."""
    with session_scope() as session:
        session.get(PipelineDraft, spawned_draft).provenance = {}

    drafts.update(spawned_draft, _graph(contract=HISAT))
    after = _sidecar(spawned_draft)
    assert after.node("align").selection.source == ValueSource.HUMAN
    assert after.node("counts") is None, "nothing was retained, because nothing was recorded"


# ── the confirmed goal ────────────────────────────────────────────────────────────────────


def test_a_stored_goal_reaches_the_artifact_instead_of_one_derived_from_the_canvas(
    spawned_draft, monkeypatch, tmp_path
):
    """§1.9, through `keep` rather than through the helper that reads the column.

    A conversational draft was built from what the researcher **asked for**; `goal_of` derives a
    goal from whichever nodes happen to be on the canvas right now. The two differ exactly when
    it matters: somebody who said *I want counts and a QC report* and has drawn only the counting
    half would, without this, have the QC half silently dropped from the goal the artifact
    records — and `upgrade` would then re-resolve against the narrower one.
    """
    import yaml
    from comeni_core.goal.asked import Goal

    asked = Goal(want=["counts.matrix", "qc.report"])
    with session_scope() as session:
        session.get(PipelineDraft, spawned_draft).goal = asked.model_dump(mode="json")

    # **`_load` is not stubbed here.** These read the real row, because the columns under test
    # are exactly the ones the seam reads — stubbing it would test the stub.
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    written = drafts.keep(spawned_draft, ai=_ai_was_wired())

    recorded = yaml.safe_load(written.read_text())["goal"]
    assert set(recorded["want"]) == {"counts.matrix", "qc.report"}, (
        "the canvas replaced what the researcher asked for"
    )


def test_a_draft_with_no_stored_goal_still_derives_one(spawned_draft, monkeypatch, tmp_path):
    """Every manual draft, and every draft that predates the column. `None` means *derive it*,
    which is what `keep` has always done — and the derived goal wants what the terminal nodes
    produce, so it is narrower on purpose."""
    import yaml

    # **`_load` is not stubbed here.** These read the real row, because the columns under test
    # are exactly the ones the seam reads — stubbing it would test the stub.
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    written = drafts.keep(spawned_draft, ai=_ai_was_wired())

    recorded = yaml.safe_load(written.read_text())["goal"]
    assert "qc.report" not in recorded["want"], "a goal nobody stored was invented"
    assert recorded["want"], "the derived goal is empty"


def test_a_spawned_draft_kept_without_declaring_a_model_is_refused(
    spawned_draft, monkeypatch, tmp_path
):
    """**MD0225, and it is the check working rather than an obstacle.**

    The sidecar says a model answered `counts.min_mqs`. An artifact that recorded that while also
    recording `ai.available: []` would contain two statements one of which is false — and A130's
    whole point is that `available` is the one field a reader cannot get any other way.

    So the caller has to say a model was there. Deriving it from the sidecar would be the adapter
    marking its own homework.
    """
    # **`_load` is not stubbed here.** These read the real row, because the columns under test
    # are exactly the ones the seam reads — stubbing it would test the stub.
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)

    with pytest.raises(Exception) as raised:
        drafts.keep(spawned_draft)
    assert "MD0225" in str(raised.value)
