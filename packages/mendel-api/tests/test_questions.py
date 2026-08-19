"""The projection both React and an agent read.

One schema, two consumers — spec §4.2. `Ambiguity` projects into the same shape in a later
slice, so nothing here may be forge-specific in its NAMES even where it is forge-only in
its source today.
"""

import pytest
from comeni_core.review import Candidate, Excerpt
from mendel_api.questions import Band, OpenQuestion, question_from_hole
from mendel_forge.scaffold import Hole
from pydantic import ValidationError


def _hole(**kw) -> Hole:
    base = {
        "subject": "consumes[0].type_id",
        "what": "what arrives on channel 0",
        "why_open": "nf-core declares it as type: file",
        "candidates": [Candidate(value="alignment.bam", note="4 contracts")],
        "evidence": [Excerpt(locator="meta.yml:input.bam", text="BAM/CRAM/SAM file")],
    }
    return Hole(**{**base, **kw})


def test_a_hole_projects_to_an_open_question():
    q = question_from_hole(_hole(), draft="samtools/index")
    assert q.subject == "consumes[0].type_id"
    assert q.what == "what arrives on channel 0"
    assert q.why_open
    assert [c.value for c in q.candidates] == ["alignment.bam"]
    assert q.evidence[0].locator == "meta.yml:input.bam"
    assert q.asked_by == ["samtools/index"]


def test_a_type_question_is_routing_not_cosmetic():
    """The bands come from the forge's own measurement: 97% on the fields that change
    which pipeline gets built, ~60% on port labels. A wrong type routes; a wrong label
    is renamed in seconds."""
    assert question_from_hole(_hole(), draft="x").band is Band.ROUTING


def test_a_port_name_question_is_cosmetic():
    q = question_from_hole(_hole(subject="consumes[0].name"), draft="x")
    assert q.band is Band.COSMETIC


def test_a_roles_question_aims_the_rules():
    q = question_from_hole(_hole(subject="roles"), draft="x")
    assert q.band is Band.ROUTING


def test_prose_has_no_candidates_and_is_never_asked_of_a_model():
    """Issue #70: priority_because is the one free-prose value reaching a registry and
    nothing can check it. A model is never asked, which is stronger than asking and
    discarding."""
    q = question_from_hole(_hole(subject="priority_because", candidates=[]), draft="x")
    assert q.band is Band.PROSE


def test_an_open_candidate_list_is_reported_as_open():
    """`closed` is inherited from Question. The forge measured that opening a closed
    field was the worst configuration tested, so whether the list binds must reach the
    client rather than being inferred."""
    assert question_from_hole(_hole(closed=False), draft="x").closed is False


def test_the_projection_forbids_extra_fields():
    with pytest.raises(ValidationError):
        OpenQuestion(subject="x", what="y", why_open="z", band=Band.ROUTING,
                     asked_by=["a"], candidates=[], evidence=[], closed=True, nonsense=1)
