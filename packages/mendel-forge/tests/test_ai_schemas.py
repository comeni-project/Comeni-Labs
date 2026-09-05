"""What a model may say back, and what is refused before anything reads it.

The claims here are about the *response*, not about the prompt that produced it, so nothing in
this file needs a model or a dossier — the same reason `test_ai_context.py` needs neither.
"""

import pytest
from mendel_forge.ai import schemas
from mendel_forge.ai.schemas import (
    Analysis,
    Answer,
    ModuleProposal,
    Proposal,
    Unresolved,
    admit,
    owed,
)
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole


def _hole(hole_id: str, **overrides) -> ScaffoldHole:
    base = {
        "id": hole_id,
        "pointer": "/consumes/0/type_id",
        "kind": HoleKind.TYPE,
        "question": "the semantic type of the input the module calls reads",
        "why_open": "nf-core declares an output as type: file with a filename pattern",
        "legal_values": ("fastq.reads", "alignment.bam"),
    }
    return ScaffoldHole(**{**base, **overrides})


def _proposal(*answers: Answer, unresolved: tuple[Unresolved, ...] = ()) -> Proposal:
    return Proposal(analysis=Analysis(answers=answers, unresolved=unresolved))


def test_a_well_formed_response_about_the_right_holes_is_admitted():
    """The positive case first, so the refusals below are known to be refusing something the
    gate would otherwise let through."""
    proposal = _proposal(
        Answer(hole_id="consumes.reads.type_id", value="fastq.reads", evidence_ids=("E001",))
    )
    assert admit(proposal, holes=[_hole("consumes.reads.type_id")], evidence_ids={"E001"})


def test_an_answer_to_a_hole_that_was_never_opened_is_refused():
    """`MF0402`. A response free to name its own fields is producing a document rather than
    answering questions, and there is then nothing that says which parts of the result came
    from arithmetic over declared data and which came from a model."""
    proposal = _proposal(Answer(hole_id="produces.invented.type_id", value="fastq.reads"))
    with pytest.raises(ValueError, match="MF0402"):
        admit(proposal, holes=[_hole("consumes.reads.type_id")], evidence_ids=set())


def test_the_whole_response_is_refused_rather_than_the_stray_answer_dropped():
    """A model that invented one hole id was not answering the question it was asked, and the
    answers that happen to match real ids are not more trustworthy for being well-formed."""
    proposal = _proposal(
        Answer(hole_id="consumes.reads.type_id", value="fastq.reads"),
        Answer(hole_id="not.a.hole", value="fastq.reads"),
    )
    with pytest.raises(ValueError, match="MF0402"):
        admit(proposal, holes=[_hole("consumes.reads.type_id")], evidence_ids=set())


def test_a_citation_of_evidence_not_in_the_dossier_is_refused():
    """`MF0401`, and it is the check that keeps the audit trail worth following. A fabricated
    `E014` is worse than no citation: a reviewer follows it, finds real text, and reads it as
    support for a claim it does not make."""
    proposal = _proposal(
        Answer(hole_id="consumes.reads.type_id", value="fastq.reads", evidence_ids=("E014",))
    )
    with pytest.raises(ValueError, match="MF0401"):
        admit(proposal, holes=[_hole("consumes.reads.type_id")], evidence_ids={"E001", "E002"})


def test_the_refusal_says_what_evidence_was_actually_given():
    """Otherwise the reader cannot tell an invented id from an adapter that collected nothing,
    and those have opposite fixes."""
    proposal = _proposal(
        Answer(hole_id="consumes.reads.type_id", value="fastq.reads", evidence_ids=("E014",))
    )
    with pytest.raises(ValueError, match="no evidence at all"):
        admit(proposal, holes=[_hole("consumes.reads.type_id")], evidence_ids=set())


def test_a_module_proposal_may_not_cite_evidence_either():
    """The module path is where a model is trusted with the most, so it is the last place the
    citation check should be relaxed."""
    proposal = Proposal(
        analysis=Analysis(),
        module=ModuleProposal(script="clustalw2 -INFILE=x", evidence_ids=("E099",)),
    )
    with pytest.raises(ValueError, match="MF0401"):
        admit(proposal, holes=[], evidence_ids={"E001"})


def test_an_answer_outside_an_exhaustive_candidate_set_is_refused():
    """`MF0403` — invariant 3's closed-choice constraint reaching the forge. A model resolving
    a tier-4 ambiguity cannot produce a value outside the candidate set; a model answering a
    scaffold hole must not either, or the forge is the hole in a guarantee the rest of the
    system keeps."""
    proposal = _proposal(Answer(hole_id="consumes.reads.type_id", value="fastq.invented"))
    with pytest.raises(ValueError, match="MF0403"):
        admit(proposal, holes=[_hole("consumes.reads.type_id")], evidence_ids=set())


def test_an_open_vocabulary_accepts_a_value_it_did_not_list():
    """`exhaustive=False` genuinely means *we listed what we found*. Refusing here would make
    the forge unable to propose the new vocabulary it exists to propose — invariant 7 says new
    states arrive through the approval queue, not that they can never be suggested."""
    proposal = _proposal(Answer(hole_id="consumes.reads.type_id", value="fastq.novel"))
    hole = _hole("consumes.reads.type_id", exhaustive=False)
    assert admit(proposal, holes=[hole], evidence_ids=set())


def test_a_hole_with_no_closed_vocabulary_accepts_anything():
    """A process name has no candidate set to be outside of. Checking membership against an
    empty tuple would refuse every answer to every Nextflow hole."""
    proposal = _proposal(Answer(hole_id="nf_process", value="CLUSTALW_ALIGN"))
    hole = _hole("nf_process", kind=HoleKind.NEXTFLOW, legal_values=())
    assert admit(proposal, holes=[hole], evidence_ids=set())


def test_a_hole_cannot_be_answered_and_reported_unresolved_at_once():
    """A reviewer would see a settled value and a request for more evidence about the same
    field, with nothing to say which is current."""
    with pytest.raises(ValueError, match="both answered and reported unresolved"):
        Analysis(
            answers=(Answer(hole_id="a", value="fastq.reads"),),
            unresolved=(Unresolved(hole_id="a", needed_evidence="the tool's man page"),),
        )


def test_an_unresolved_item_must_say_what_would_close_it():
    """§5.5. The difference between this and a hole that was skipped is that one tells a
    curator where to look and the other tells them only that they have work."""
    with pytest.raises(ValueError):
        Unresolved(hole_id="a", needed_evidence="")


def test_a_confidence_score_cannot_be_returned_at_all():
    """§5.5's last line: *confidence never turns missing evidence into a fact*. A score invites
    exactly that trade — a reviewer reads 0.9 and stops reading the evidence — so the shape has
    no room for one and `extra="forbid"` makes offering one an error rather than a field that
    is silently dropped."""
    with pytest.raises(ValueError):
        Answer(hole_id="a", value="fastq.reads", confidence=0.9)


def test_a_forgotten_required_hole_is_owed_rather_than_refused():
    """A model that answered six of nine holes has not declined the other three, it has
    forgotten them — and §5.7's repair prompt is where that is said, not `admit`."""
    holes = [
        _hole("a"),
        _hole("b"),
        _hole("c", required=False),
    ]
    proposal = _proposal(Answer(hole_id="a", value="fastq.reads"))
    assert owed(proposal, holes) == ("b",)


def test_a_hole_left_explicitly_unresolved_is_not_owed():
    """Declining with `needed_evidence` is the answer the shared invariant block asks for when
    evidence runs out. Counting it as a failure to respond would make the honest move look
    identical to the negligent one, and a repair pass would then push against it."""
    proposal = _proposal(
        unresolved=(Unresolved(hole_id="b", needed_evidence="the tool's man page"),)
    )
    assert owed(proposal, [_hole("b")]) == ()


def test_no_response_field_can_be_used_as_a_destination_path():
    """§5.6: a response never chooses a destination. Held literally, the way the egress guard
    holds its payload allowlist, because this is the same class of boundary — the check is that
    somebody must edit a test that says *these are all the fields a response has* before a new
    one can carry a path.

    The path a candidate is written to comes from `bundle.joined(adaptation_id, Area.CANDIDATE,
    ...)`, which is derived from the adaptation id and a fixed name and reads nothing here.
    """
    declared = {
        "Answer": {"hole_id", "value", "evidence_ids", "reason"},
        "Unresolved": {"hole_id", "needed_evidence"},
        "Analysis": {"answers", "unresolved"},
        "ModuleProposal": {
            "input_block",
            "output_block",
            "script",
            "versions_command",
            "evidence_ids",
        },
        "Proposal": {"analysis", "module"},
    }
    for name, fields in declared.items():
        model = getattr(schemas, name)
        assert set(model.model_fields) == fields, (
            f"{name} gained or lost a field. If it is a path, a filename, a directory or a URL, "
            "the response has been given a say in where its output lands, which §5.6 forbids."
        )
    assert declared, "an empty table would make this loop assert nothing"


def test_a_module_proposal_reports_which_open_sections_it_filled():
    """`render.py` puts sections back where `modulegen`'s markers are, and a section left
    blank must stay a marked hole rather than becoming an empty block — an empty `script:` is a
    process that runs nothing and reports success."""
    proposal = ModuleProposal(script="clustalw2 -INFILE=in.fa", input_block="  path(reads)")
    assert proposal.filled() == ("input_block", "script")
    assert ModuleProposal(script="   ").filled() == ()
