"""The draft is a projection of the blueprint, and one rule says where the walk stops
(§14.3, §14.4 of the consultant build).

The two blueprints are the rnaseq example resolved by the shell and recorded: STAR's, and
HISAT2's after a person pinned it at the aligner's site — the swap of issue 253.
"""

import json
from pathlib import Path

import pytest
from comeni_core.goal.profile import DataProfile
from mendel_authoring.blueprint import Blueprint
from mendel_authoring.draft import Reviewed, drafted, kept, next_step
from mendel_authoring.gaps import Gap, GapKind
from mendel_authoring.needs import Need, NeedKind
from mendel_authoring.pacing import Pacing, Policy, Stop, stops
from mendel_authoring.plan import PlannedStep

FIXTURES = Path(__file__).parent / "fixtures"


def _recorded(name: str) -> Blueprint:
    return Blueprint.model_validate(json.loads((FIXTURES / f"blueprint-{name}.json").read_text()))


STAR, HISAT2 = _recorded("star"), _recorded("hisat2")


def _ids(graph) -> set[str]:
    return {node.id for node in graph.nodes}


def test_the_draft_holds_only_reviewed_steps_with_edges_between_them():
    reviewed = [Reviewed(node=n, by="engine") for n in STAR.order[:3]]
    graph, provenance = drafted(STAR, reviewed, DataProfile())
    assert _ids(graph) == set(STAR.order[:3])
    assert graph.edges, "the index feeds the aligner"
    assert all(e.from_node in _ids(graph) and e.to_node in _ids(graph) for e in graph.edges)
    assert {entry.node for entry in provenance.nodes} == _ids(graph)


def test_the_draft_carries_the_goals_profile():
    profile = STAR.pipeline.goal.profile
    graph, _ = drafted(STAR, [], profile)
    assert graph.profile == profile and not graph.nodes


@pytest.mark.parametrize("cut", range(len(STAR.order) + 1))
def test_no_orphan_after_a_swap_whatever_was_reviewed(cut):
    """Review Focus 1, as a property: whatever was reviewed under STAR, the draft projected from
    HISAT2's blueprint holds only HISAT2's steps and only edges between them."""
    reviewed = [Reviewed(node=n, by="person") for n in STAR.order[:cut]]
    graph, _ = drafted(HISAT2, reviewed, DataProfile())
    ids = _ids(graph)
    assert ids <= set(HISAT2.order)
    assert all(e.from_node in ids and e.to_node in ids for e in graph.edges)


def test_after_a_swap_the_index_it_added_comes_next():
    before = [Reviewed(node=n, by="person") for n in ("star_genomegenerate", "trimgalore")]
    reviewed = kept(HISAT2, before) + [Reviewed(node="hisat2_align", by="person")]
    assert next_step(HISAT2, reviewed) == "hisat2_build"


def test_the_walk_ends_when_every_step_is_reviewed():
    assert next_step(STAR, [Reviewed(node=n, by="engine") for n in STAR.order]) is None


def test_a_swapped_step_keeps_the_persons_reason():
    """The pinned aligner is the blueprint's own step, tier 4 by person: its provenance keeps
    the pin's reason (*you chose … over …*), not a generic sentence."""
    _, provenance = drafted(HISAT2, [Reviewed(node="hisat2_align", by="ana")], DataProfile())
    settled = provenance.nodes[0].selection
    assert settled.by == "ana" and settled.reason.startswith("you chose")


_GAP = Gap(kind=GapKind.NO_DESCRIPTION, subject="lab/x", fix="registry/tools/lab/x/tool.yml")


def _planned(*, tier4: bool, gaps: bool) -> PlannedStep:
    return PlannedStep(
        node="x",
        contract="lab/x@1",
        brief=_brief(),
        need=Need(kind=NeedKind.CHOICE if tier4 else NeedKind.NOTHING),
        gaps=[_GAP] if gaps else [],
    )


def _brief():
    from mendel_authoring.brief import Brief

    return Brief(does=None, why=[], makes=[], check=[])


@pytest.mark.parametrize(
    ("tier4", "gaps", "pacing", "show", "expected"),
    [
        (True, False, "stop_where_needed", False, Stop.TIER_FOUR),
        (False, True, "stop_where_needed", True, Stop.GAP),
        (False, True, "stop_where_needed", False, None),
        (False, False, "together", False, Stop.TOGETHER),
        (False, False, "stop_where_needed", False, None),
        (True, True, "together", True, Stop.TIER_FOUR),
    ],
)
def test_where_the_walk_stops(tier4, gaps, pacing, show, expected):
    """The need first (3b's Review Focus 1), then a gap if Dev mode shows gaps, then *together*."""
    policy = Policy(pacing=Pacing(pacing), show_gaps=show)
    assert stops(_planned(tier4=tier4, gaps=gaps), policy) == expected
