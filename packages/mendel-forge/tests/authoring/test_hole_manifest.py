"""Addressing a hole, and the vocabulary it is asked with.

Separate from `test_bundle.py` because these are claims about the *type* rather than about a
derivation: what makes an id usable, what makes a hint complete, and what a manifest counts as
still owed. A defect in any of them would surface in `test_bundle.py` as a confusing failure
about fastqc.
"""

import pytest
from mendel_forge.hole_manifest import (
    HINTS,
    HoleKind,
    ScaffoldHole,
    pointer_for,
    port_hole_id,
    slug,
    unresolved,
)


def _hole(**overrides) -> ScaffoldHole:
    base = {
        "id": "consumes.reads.type_id",
        "pointer": "/consumes/0/type_id",
        "kind": HoleKind.TYPE,
        "question": "the semantic type of the input the module calls reads",
        "why_open": "nf-core declares an output as type: file with a filename pattern",
        "legal_values": ("fastq.reads", "alignment.bam"),
    }
    return ScaffoldHole(**{**base, **overrides})


def test_every_kind_has_a_hint():
    """`HINTS`' docstring promises this, so it is a test rather than a sentence.

    A hole with no fragment falls back to whatever the surrounding prompt happens to say, which
    is how one question comes to be asked two different ways in two drafts — and the difference
    then reads as a model being inconsistent rather than as a prompt being missing.
    """
    assert set(HINTS) == set(HoleKind)
    assert all(HINTS[kind] for kind in HoleKind)


def test_a_hint_names_a_versioned_fragment():
    """`ports.semantic-type.v1`, not a paragraph. A hole points at a *committed* instruction and
    never carries one, so two drafts of two tools ask the same question in the same words — and
    changing that question is a diff in a file rather than a change in generated text."""
    for value in HINTS.values():
        assert value.endswith(".v1"), value
        assert " " not in value


def test_a_kind_specific_override_wins_over_the_default():
    """The port-name case: a name and a type are the same *sort* of question about the same port
    and are not the same question."""
    assert _hole().hint == HINTS[HoleKind.TYPE]
    assert _hole(prompt_hint_id="ports.name.v1").hint == "ports.name.v1"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("bam_unsorted", "bam-unsorted"),
        ("reads", "reads"),
        ("BAM", "bam"),
        ("versions.fastqc", "versions-fastqc"),
        ("  spaced  ", "spaced"),
        ("[meta]", "meta"),
    ],
)
def test_a_channel_name_becomes_a_readable_segment(text, expected):
    """Not reversible, and it does not need to be — the pointer addresses the document. This
    only has to be stable and readable."""
    assert slug(text) == expected


def test_an_id_is_built_from_the_channel_and_a_pointer_from_the_index():
    """**Two fields because they answer two questions**: which port is this, and where is it in
    today's document. Fusing them is the defect `consumes[0].type_id` was."""
    assert port_hole_id("consumes", "bam_unsorted", "type_id") == "consumes.bam-unsorted.type_id"
    assert pointer_for("consumes", 3, "type_id") == "/consumes/3/type_id"


def test_a_pointer_that_is_not_a_pointer_is_refused():
    """A JSON pointer starts with `/`. One that does not is a field name that has been put in
    the wrong slot, and it would silently address nothing."""
    with pytest.raises(ValueError, match="not a JSON pointer"):
        _hole(pointer="consumes/0/type_id")


def test_an_id_with_stray_whitespace_is_refused():
    """The id is a key: it is stored, cited in a review, and matched against an answer. One with
    a trailing space matches nothing and looks identical to one that would."""
    with pytest.raises(ValueError, match="not a usable hole id"):
        _hole(id="consumes.reads.type_id ")


def test_an_open_vocabulary_says_so_rather_than_offering_nothing():
    """`exhaustive=False` with a ranked list is a real state — *we listed what we found* — and it
    is not the same claim as an empty list. Collapsing them is how a reviewer comes to believe a
    suggestion is the only legal answer."""
    ranked = _hole(exhaustive=False, legal_values=("fastq.reads",))
    assert ranked.legal_values and not ranked.exhaustive


def test_a_nextflow_hole_may_have_no_legal_values():
    """The one exemption, and it is a real one: a process name or a script body has no closed
    vocabulary to enumerate. Every other kind offering an exhaustive list of nothing is a
    candidate set that came back empty and a flag nobody set."""
    assert ScaffoldHole(
        id="nf_process",
        pointer="/nf_process",
        kind=HoleKind.NEXTFLOW,
        question="what is the process called",
        why_open="this source ships no Nextflow module",
    )


def test_an_answered_hole_is_no_longer_owed():
    """Approval's precondition, in one place.

    Counting at the call site is how the number on the page and the number the service refuses
    on come to disagree — and the disagreement always favours the page, because the page is what
    somebody looked at.
    """
    holes = (_hole(id="a"), _hole(id="b"), _hole(id="c", required=False))
    assert unresolved(holes, frozenset()) == ("a", "b")
    assert unresolved(holes, frozenset({"a"})) == ("b",)
    assert unresolved(holes, frozenset({"a", "b"})) == ()


def test_an_optional_hole_never_blocks_even_unanswered():
    """`required` is not derived from the kind, and this is why: a missing semantic type blocks
    and a missing citation on an optional parameter does not, and both are type-ish in flavour.
    Deriving it would make a judgement look like a classification."""
    assert unresolved((_hole(id="only", required=False),), frozenset()) == ()


def test_a_hole_is_frozen():
    """A manifest is written once and read many times. A mutable hole would let a renderer
    'normalise' a legal value in place, and the stored answer would then be validated against
    something the reviewer never saw."""
    hole = _hole()
    with pytest.raises(ValueError):
        hole.id = "something-else"
