"""Stage ④ through the facade, against the real registry and a real database (spec §14).

**The blueprint decides, the walk reviews.** The pure flow is
`packages/mendel-authoring/tests/test_stage_four.py`; this file is the work each node does with
rows: a card's alternatives as whole pipelines, a change into the goal, the draft projected from
the blueprint (no orphan, the fact kept), the pacing and Dev forks, the refusals, the wrap-up."""

import pytest
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.services import session as facade
from mendel_api_tests.database import reachable
from mendel_api_tests.step_review import (
    _amend,
    _built,
    _continue,
    _draft,
    _goal,
    _hisat2,
    _ids,
    _no_orphan,
    _pending,
    _pending_node,
    _unbuildable_at,
    _walk_to_node,
    _walk_to_wrap,
)
from mendel_api_tests.step_review import (
    clean as clean,
)
from mendel_authoring import commands
from mendel_authoring.protocol import PROTOCOL
from support.example import example_mapping

pytestmark = pytest.mark.skipif(not reachable(), reason="no database — run `make test-db`")


# ── a card's choices ───────────────────────────────────────────────────────────────────────
def test_without_a_read_length_the_aligner_stops_with_its_tools_and_the_fact(clean):
    session_id = _built(_goal(read_length=False))
    card = _walk_to_node(session_id, "star_align")
    options = card["payload"]["options"]
    assert card["payload"]["block"]["tier"] == 4
    assert "fact_read_length" in options
    assert any(o.startswith("alt_") for o in options)
    assert "adds hisat2_build" in _hisat2(card)["note"]


def test_telling_a_short_read_length_rebuilds_with_hisat2_and_no_star(clean):
    """Issue 253: the fact changes the tool, and the draft follows the new blueprint."""
    session_id = _built(_goal(read_length=False))
    _walk_to_node(session_id, "star_align")
    _amend(session_id, "fact_read_length", 50)
    assert not _ids(session_id) & {"star_genomegenerate", "star_align"}
    _no_orphan(session_id)
    _walk_to_wrap(session_id)
    final = _ids(session_id)
    assert {"hisat2_build", "hisat2_align"} <= final
    assert not final & {"star_genomegenerate", "star_align"}
    _no_orphan(session_id)


def test_swapping_star_for_hisat2_on_the_card_brings_its_index(clean):
    """Issue 257, Review Focus 1: the swap drags HISAT2's index in and STAR's out; the index it
    added is the walk's next stop."""
    session_id = _built(_goal())
    card = _walk_to_node(session_id, "star_align")
    _amend(session_id, _hisat2(card)["id"])
    assert _pending_node(session_id) == "hisat2_build"
    assert "hisat2_align" in _ids(session_id)
    _walk_to_wrap(session_id)
    assert not _ids(session_id) & {"star_genomegenerate", "star_align"}
    _no_orphan(session_id)


def test_the_kept_draft_carries_the_fact_it_was_built_on(clean):
    """Issue 254."""
    session_id = _built(_goal(read_length=False))
    _walk_to_node(session_id, "star_align")
    _amend(session_id, "fact_read_length", 150)
    draft = _draft(session_id)
    assert any(
        m["measurement"] == "read_length"
        for m in facade.read(session_id)["goal"]["profile"]["measurements"]
    )
    assert any(m["measurement"] == "read_length" for m in draft.graph["profile"]["measurements"])


def test_the_wrap_up_credits_the_person_for_a_swap(clean):
    """Issue 256."""
    session_id = _built(_goal())
    _amend(session_id, _hisat2(_walk_to_node(session_id, "star_align"))["id"])
    assert "by human" in _walk_to_wrap(session_id)


def test_a_value_its_measurement_refuses_is_refused(clean):
    session_id = _built(_goal(read_length=False))
    _walk_to_node(session_id, "star_align")
    with pytest.raises(ValueError, match="MI0208"):
        _amend(session_id, "fact_read_length", "long")


# ── refusals ───────────────────────────────────────────────────────────────────────────────
def test_a_card_answered_twice_is_refused_the_second_time(clean):
    """Review Focus 4: a double click, or a second tab."""
    session_id = _built(_goal())
    card = _walk_to_node(session_id, "star_align")
    _amend(session_id, _hisat2(card)["id"], proposal_id=card["id"])
    with pytest.raises(ValueError, match="MI0203"):
        _amend(session_id, _hisat2(card)["id"], proposal_id=card["id"])
    with pytest.raises(ValueError, match="MI0203"):
        facade.perform(commands.SettleStep(card["id"], facade.read(session_id)["revision"], "a"))


def test_an_option_the_card_never_offered_is_refused(clean):
    session_id = _built(_goal())
    _walk_to_node(session_id, "star_align")
    with pytest.raises(ValueError, match="MI0205"):
        _amend(session_id, "alt_99")


def test_a_replayed_pacing_answer_is_refused(clean, monkeypatch):
    """Issue 259."""
    monkeypatch.delenv("COMENI_BUILD_PACING", raising=False)
    session_id = _built(_goal())
    question = _pending(session_id)
    assert question["kind"] == "pacing"
    facade.perform(commands.ChoosePacing(question["id"], "together", "ana"))
    with pytest.raises(ValueError, match="MI0203"):
        facade.perform(commands.ChoosePacing(question["id"], "together", "ana"))


# ── pacing and Dev mode ─────────────────────────────────────────────────────────────────────
def test_together_rests_at_every_step(clean):
    session_id = _built(_goal())
    first = _pending(session_id)
    assert first["kind"] == "step"
    _continue(session_id)
    assert _pending(session_id)["id"] != first["id"] and _pending(session_id)["kind"] == "step"


def test_stop_where_needed_with_a_read_length_reaches_the_wrap_up(clean, monkeypatch):
    """Review Focus 5's shell half: every quiet step placed in one entry of `step`."""
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    session_id = _built(_goal())
    view = facade.read(session_id)
    assert view["phase"] == Phase.COMPLETE.value and view["pending_proposal"] is None
    assert "You'll get: counts.matrix" in _walk_to_wrap(session_id)
    assert _ids(session_id) >= {"star_align", "subread_featurecounts"}
    _no_orphan(session_id)


def test_stop_where_needed_offers_its_first_card_against_the_quiet_steps(clean, monkeypatch):
    """Issue 263: the card was offered before the quiet steps were projected, so it held the
    draft's old revision (Continue answered `MI0202`) and wired only to the old graph."""
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    session_id = _built(_goal(read_length=False))
    card = _pending(session_id)
    assert card is not None and card["payload"]["node"] == "star_align"
    present = _ids(session_id)
    wired = {e["from_node"] for e in card["payload"]["edges"]}
    assert wired and wired <= present
    assert "star_align" not in present
    _continue(session_id)
    assert "star_align" in _ids(session_id), "Continue was refused: the card was stale"


def test_ask_puts_the_pacing_question_and_the_answer_walks_on(clean, monkeypatch):
    monkeypatch.delenv("COMENI_BUILD_PACING", raising=False)
    session_id = _built(_goal())
    question = _pending(session_id)
    assert question["kind"] == "pacing"
    facade.perform(commands.ChoosePacing(question["id"], "stop_where_needed", "ana"))
    assert facade.read(session_id)["phase"] == Phase.COMPLETE.value


def test_an_env_pinned_pacing_wins_over_the_stored_one(monkeypatch, settings_in_memory):
    """The snapshot is the settings resolver's, never the raw stored row."""
    settings_in_memory.rows["building.pacing"] = "ask"
    monkeypatch.setenv("COMENI_BUILD_PACING", "together")
    assert facade.snapshot(PROTOCOL).settings["building.pacing"] == "together"
    monkeypatch.delenv("COMENI_BUILD_PACING")
    assert facade.snapshot(PROTOCOL).settings["building.pacing"] == "ask"


def test_dev_mode_on_stops_on_a_gap_and_names_the_file(clean, monkeypatch):
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    monkeypatch.setenv("COMENI_DEV_MODE", "true")
    session_id = _built(_goal())
    card = _pending(session_id)
    assert card is not None and card["kind"] == "step"
    assert card["payload"]["block"]["stop"] == "gap"
    gaps = card["payload"]["block"]["gaps"]
    assert gaps and all(g["fix"].startswith("registry/tools/") for g in gaps)


def test_dev_mode_off_routes_around_every_gap(clean, monkeypatch):
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    monkeypatch.setenv("COMENI_DEV_MODE", "false")
    session_id = _built(_goal())
    assert facade.read(session_id)["phase"] == Phase.COMPLETE.value


def test_a_truthful_fact_change_stays_when_building_is_blocked_and_can_be_corrected_again(
    clean, monkeypatch
):
    """Part F: an impossible speculative swap is refused; a truthful fact stays selected."""
    from mendel_api_tests.corrections import _correct

    session_id = _built(_goal(read_length=False))
    card = _walk_to_node(session_id, "star_align")
    _unbuildable_at(monkeypatch, 50)
    _amend(session_id, "fact_read_length", 50)
    view = facade.read(session_id)
    assert view["phase"] in (Phase.GATHERING.value, Phase.GOAL_REVIEW.value)
    assert view["pending_proposal"]["id"] != card["id"]
    assert any(
        m["measurement"] == "read_length" and m["value"] == 50
        for m in view["goal"]["profile"]["measurements"]
    )
    assert not _draft(session_id).projection_current
    _correct(session_id, "read_length", 150)
    assert facade.read(session_id)["phase"] == Phase.BUILDING.value
    assert any(
        m["measurement"] == "read_length" and m["value"] == 150
        for m in facade.read(session_id)["goal"]["profile"]["measurements"]
    )


def test_a_moved_registry_that_cannot_build_the_goal_is_refused_by_name(clean, monkeypatch):
    """Final review I2: re-resolving after the registry moved can find the goal unbuildable;
    that is said (MI0207), not a server error."""
    from mendel_api.services import blueprint as bp
    from mendel_resolver.router import UnroutableError

    session_id = _built(_goal())
    card = _pending(session_id)
    monkeypatch.setattr(bp, "registry_digest", lambda roots: "sha256:" + "0" * 64)

    def unbuildable(goal, **kw):
        raise UnroutableError("gone", missing=("genome.fasta", frozenset()))

    monkeypatch.setattr(bp, "resolve", unbuildable)
    with pytest.raises(ValueError, match="MI0207"):
        facade.perform(commands.SettleStep(card["id"], facade.read(session_id)["revision"], "ana"))


def test_two_answers_at_once_to_one_card_one_is_refused(clean):
    """Final review I3: a double click that really overlaps. The first answer holds the card;
    the second waits for it, then reads it answered and is refused (MI0203)."""
    import threading
    import time

    from mendel_api.models import PipelineAuthoringProposal

    session_id = _built(_goal())
    card = _walk_to_node(session_id, "star_align")
    locked = threading.Event()

    def first_answer():
        with session_scope() as db:
            proposal = db.get(PipelineAuthoringProposal, card["id"], with_for_update=True)
            locked.set()
            time.sleep(1.0)
            proposal.state = "accepted"

    holder = threading.Thread(target=first_answer)
    holder.start()
    locked.wait(5)
    try:
        with pytest.raises(ValueError, match="MI0203"):
            _amend(session_id, _hisat2(card)["id"], proposal_id=card["id"])
    finally:
        holder.join()


# ── a fact a tool reads (#338) ─────────────────────────────────────────────────────────────
def _goal_without_strandedness():
    from mendel_resolver.goal import Goal

    data = example_mapping()
    data["profile"].pop("strandedness")
    data["profile"]["read_length"] = 50  # HISAT2: two steps read strandedness
    return Goal.model_validate(data)


def _strandedness(session_id: str):
    from mendel_api.services import decisions

    draft = facade.read(session_id)["draft_id"]
    return next((f.value for f in decisions.read(draft).facts if f.subject == "strandedness"),
                None)


def test_an_unknown_fact_stops_the_first_tool_that_reads_it_and_one_answer_settles_both(clean):
    """#338, Review Focus 3: HISAT2 align and featureCounts both read strandedness off the
    label. The walk asks at the first; the answer is the fact, so the second does not ask."""
    session_id = _built(_goal_without_strandedness())
    card = _walk_to_node(session_id, "hisat2_align")
    assert "fact_strandedness" in card["payload"]["options"]
    _amend(session_id, "fact_strandedness", "reverse")
    assert _strandedness(session_id) == "reverse"
    asked_again = []
    for _ in range(50):
        pending = _pending(session_id)
        if pending is None:
            break
        if "fact_strandedness" in pending["payload"]["options"]:
            asked_again.append(_pending_node(session_id))
        _continue(session_id)
    assert asked_again == []
    assert "subread_featurecounts" in _ids(session_id)


def test_the_card_for_an_unknown_fact_offers_its_values_says_why_and_is_tier_four(clean):
    """#341, from the walk: the card said tier 2, explained itself as *the rule that picks this
    tool reads it*, and asked for strandedness as free text."""
    session_id = _built(_goal_without_strandedness())
    block = _walk_to_node(session_id, "hisat2_align")["payload"]["block"]
    assert block["tier"] == 4
    assert block["need"]["fact_values"]["strandedness"] == ["forward", "reverse", "unstranded"]
    assert "reads strandedness" in block["need"]["fact_reasons"]["strandedness"]
