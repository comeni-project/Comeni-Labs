"""What a model may say back, and what is refused before anything reads it.

The claims here are about the *response*, not about the prompt that produced it, so nothing in
this file needs a model or a dossier — the same reason `test_ai_context.py` needs neither.
"""

import pytest
from mendel_forge.ai import schemas
from mendel_forge.ai.schemas import (
    Analysis,
    Answer,
    ChatAnswer,
    Citation,
    ClaimKind,
    ModuleProposal,
    Proposal,
    Unresolved,
    admit,
    admit_answer,
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
        # **`Citation.file` is a filename in a response, and it is listed rather than
        # exempted.** It is a display anchor: the candidate file a claim points at, so the UI
        # can scroll to it. What makes it safe is not its name but that `ChatAnswer` never
        # reaches `render.py` — a chat answer is shown to a curator and writes nothing — while
        # every path that *is* written comes from `bundle.joined(adaptation_id, ...)`.
        #
        # It was added on 2026-09-05 and this table did not fail, because the loop below walks
        # the names in this dict rather than every model in the module. That is the hole in
        # this guard, and `test_the_table_covers_every_model_in_the_module` closes it.
        "Citation": {"kind", "evidence_id", "file", "line"},
        "ChatAnswer": {"answer", "citations", "unanswered"},
    }
    for name, fields in declared.items():
        model = getattr(schemas, name)
        assert set(model.model_fields) == fields, (
            f"{name} gained or lost a field. If it is a path, a filename, a directory or a URL, "
            "the response has been given a say in where its output lands, which §5.6 forbids."
        )
    assert declared, "an empty table would make this loop assert nothing"


def test_the_table_covers_every_model_in_the_module():
    """**The hole in the test above, closed.** It walks the names in its own table, so a model
    added to `schemas.py` and not to the table is a model nothing inspects — silently, with a
    green run to say so.

    That is not hypothetical: `Citation` and `ChatAnswer` arrived with door 5 on 2026-09-05,
    `Citation` carries a `file` field, and the path allowlist passed without ever looking at it.
    The same shape as invariant 14's own guard taking its roots from `vars(egress)` rather than
    from `DOORS`, which walked three doors out of four while reporting green.
    """
    from pydantic import BaseModel

    defined = {
        name
        for name, obj in vars(schemas).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj is not BaseModel
        # `__module__`, not mere presence in the namespace: `ScaffoldHole` is imported here as
        # an *input* to `admit()` and is not a response shape. Filtering by name would need a
        # second allowlist, which is the thing this test exists to avoid.
        and obj.__module__ == schemas.__name__
    }
    assert defined, "no models were found, so this asserted nothing"
    uncovered = defined - {
        "Answer",
        "Unresolved",
        "Analysis",
        "ModuleProposal",
        "Proposal",
        "Citation",
        "ChatAnswer",
    }
    assert uncovered == set(), (
        f"these response models are in schemas.py and in no allowlist: {sorted(uncovered)}. "
        "Add them to the table above after checking that no field of theirs is ever used as a "
        "destination path."
    )


def test_a_module_proposal_reports_which_open_sections_it_filled():
    """`render.py` puts sections back where `modulegen`'s markers are, and a section left
    blank must stay a marked hole rather than becoming an empty block — an empty `script:` is a
    process that runs nothing and reports success."""
    proposal = ModuleProposal(script="clustalw2 -INFILE=in.fa", input_block="  path(reads)")
    assert proposal.filled() == ("input_block", "script")
    assert ModuleProposal(script="   ").filled() == ()


# ── the review chat's envelope (§5.8) ──────────────────────────────────────────────────


def test_a_citation_must_point_at_something():
    """A citation naming neither an evidence id nor a file renders as a clickable anchor
    pointing nowhere, which is worse than an uncited sentence — it looks checked."""
    with pytest.raises(ValueError, match="must name an evidence id or a candidate file"):
        Citation(kind=ClaimKind.SOURCE_FACT)
    assert Citation(kind=ClaimKind.SOURCE_FACT, evidence_id="E001")
    assert Citation(kind=ClaimKind.PROPOSAL, file="contract.yml", line=12)


def test_a_claim_says_which_of_the_four_kinds_it_is():
    """§5.8. A model proposal presented as a source fact is the failure a review exists to
    catch, and a reviewer skimming prose cannot see which one they are reading — so it is a
    closed vocabulary on the citation rather than a sentence in the prompt."""
    assert {kind.value for kind in ClaimKind} == {
        "source_fact",
        "derivation",
        "proposal",
        "reviewer_decision",
    }


def test_a_chat_answer_cannot_cite_evidence_outside_its_record():
    """`MF0401` on the chat path. The same claim `admit()` makes about a proposal, and a
    separate function because a chat answer has no holes — sharing one would mean a caller
    passing `holes=[]` to switch half the checks off without saying so."""
    answer = ChatAnswer(
        answer="it is a BAM",
        citations=(Citation(kind=ClaimKind.SOURCE_FACT, evidence_id="E404"),),
    )
    with pytest.raises(ValueError, match="MF0401"):
        admit_answer(answer, evidence_ids={"E001"})
    assert admit_answer(answer, evidence_ids={"E404"})


def test_a_file_citation_needs_no_evidence_id():
    """§5.8 permits two anchors — an evidence id *or* a candidate file line — and a claim about
    what the candidate itself says has no upstream excerpt behind it."""
    answer = ChatAnswer(
        answer="line 12 declares it",
        citations=(Citation(kind=ClaimKind.DERIVATION, file="contract.yml", line=12),),
    )
    assert admit_answer(answer, evidence_ids=set())


def test_an_answer_can_report_what_the_record_could_not_settle():
    """*The evidence here does not say* is a complete answer and the one a curator can act on.
    A shape with nowhere to put it invites a plausible sentence instead."""
    answer = ChatAnswer(answer="I cannot tell", unanswered=("the tool's man page",))
    assert answer.unanswered == ("the tool's man page",)
