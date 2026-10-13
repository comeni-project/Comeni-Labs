"""Each question says what it is about and why it is asked (Part I.1 §4)."""

import pytest
from mendel_api.authoring.envelopes import GapOffer
from mendel_api.services import explain, gaps, registry


@pytest.fixture
def scene():
    stack = registry.stack()
    found = gaps.gaps(["counts.matrix"], [], stack)
    return stack, found, {g.subject: g for g in found}


def _explained(scene, subject, *, measured=None, read=frozenset(), ai=False, found=None):
    stack, all_found, by = scene
    return explain.explanation(by[subject], found if found is not None else all_found, stack,
                               measured=measured or {}, read=set(read), characterisable=ai)


def test_an_input_says_what_it_is_and_which_steps_read_it(scene):
    got = _explained(scene, "annotation.gtf")
    assert got.name == "gene annotation (GTF)"
    assert got.what.startswith("A table of where each gene")
    assert got.reads == "steps" and got.needed
    assert all(r.text for r in got.needed)
    assert len({r.text for r in got.needed}) == len(got.needed)


def test_a_measurement_says_which_rule_it_decides(scene):
    got = _explained(scene, "read_length")
    assert got.name == "Sequenced read length"
    assert got.reads == "rule"
    assert got.needed[0].text == "read length determines which aligner is appropriate"
    assert got.needed[0].detail.startswith("Dobin et al. 2013")


def test_a_sample_settles_only_what_is_still_open(scene):
    """Review Focus 3."""
    measured = {"read_length": {"fastq.reads"}, "paired": {"fastq.reads"},
                "quality_encoding": {"fastq.reads"}}
    got = _explained(scene, "fastq.reads", measured=measured, read={"fastq.reads"})
    assert got.read_by == "inspector"
    assert got.settles == ["whether the library was sequenced paired-end",
                           "sequenced read length"]
    stack, found, by = scene
    without = [g for g in found if g.subject not in ("read_length", "paired")]
    none_left = _explained(scene, "fastq.reads", measured=measured, read={"fastq.reads"},
                           found=without)
    assert none_left.settles == [] and none_left.read_by == "inspector"


def test_a_type_no_inspector_reads_is_read_by_the_ai_when_it_may(scene):
    assert _explained(scene, "annotation.gtf", ai=True).read_by == "ai"
    assert _explained(scene, "annotation.gtf", ai=False).read_by is None


def test_a_type_with_nothing_declared_falls_back_to_its_id(scene):
    """Review Focus 2: a lab's type with no name or explanation."""
    stack, found, by = scene
    bare = stack.vocabulary.model_copy(update={"names": {}, "explains": {}})
    stack = stack.model_copy(update={"vocabulary": bare})
    got = explain.explanation(by["annotation.gtf"], found, stack, measured={}, read=set(),
                              characterisable=False)
    assert got.name == "annotation.gtf" and got.what is None and got.needed


def test_an_offer_stored_before_explanations_still_reads():
    """Review Focus 1: a payload with no `explain` key."""
    block = {"kind": "question", "id": "gap-1", "asks": "x?", "why_open": "y",
             "options": [{"id": "have_it", "label": "I have it"}]}
    offer = GapOffer.model_validate({
        "offer": "gap", "subject": "genome.fasta", "kind": "input", "why": "y",
        "options": {"have_it": "I have it"}, "block": block,
        "context": {"draft_revision": 0, "decision_revision": 0, "session_version": 1,
                    "registry": ""}})
    assert offer.explain is None
