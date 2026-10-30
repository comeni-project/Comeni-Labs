"""Forging's rules: the AI proposes, a person decides, nothing is overwritten (spec §2)."""

import pytest
from comeni_flow.diagram import to_mermaid
from comeni_flow.interpret import Refused
from mendel_forge.forging.model import Actor, Adaptation, Command, Move, Piece, Status
from mendel_forge.forging.protocol import FORGING
from mendel_forge.forging.rules import apply, next_piece, ready_to_assemble

AI, PERSON = Actor.AI, Actor.PERSON


def _do(state, move, actor, item, **kw):
    return apply(state, Command(move=move, actor=actor, item=item, **kw))


def _answered() -> Adaptation:
    state = _do(Adaptation(), Move.ANSWER, PERSON, "questions:role", value="assembly_qc",
                by="rafael")
    return state


def _contract_approved() -> Adaptation:
    state = _do(_answered(), Move.WRITE, PERSON, "contract:process", value={}, by="rafael")
    state = _do(state, Move.DRAFT, AI, "contract:port:consensus", value={"name": "consensus"})
    return _do(state, Move.APPROVE, PERSON, "contract:port:consensus", expected=1, by="rafael")


def test_the_ai_cannot_approve():
    state = _do(_answered(), Move.DRAFT, AI, "contract:port:consensus", value={})
    with pytest.raises(Refused, match="MF0505"):
        _do(state, Move.APPROVE, AI, "contract:port:consensus", expected=1)


def test_the_ai_can_propose_a_removal_and_only_approval_removes():
    state = _do(_contract_approved(), Move.PROPOSE_REMOVAL, AI, "contract:port:consensus",
                because="not a real input")
    assert state.items["contract:port:consensus"].status is Status.PROPOSED
    state = _do(state, Move.APPROVE, PERSON, "contract:port:consensus", expected=3)
    assert state.items["contract:port:consensus"].status is Status.REMOVED


def test_a_person_written_item_counts_without_a_second_approval():
    state = _do(_answered(), Move.WRITE, PERSON, "contract:port:consensus", value={}, by="r")
    assert state.items["contract:port:consensus"].status is Status.APPROVED


def test_reject_blocks_the_piece_until_changed_or_revised_and_approved():
    state = _do(_answered(), Move.WRITE, PERSON, "contract:process", value={})
    state = _do(state, Move.DRAFT, AI, "contract:port:consensus", value={})
    state = _do(state, Move.REJECT, PERSON, "contract:port:consensus", expected=1)
    assert state.items["contract:port:consensus"].status is Status.REJECTED
    assert next_piece(state) is Piece.CONTRACT
    state = _do(state, Move.REVISE, AI, "contract:port:consensus", value={"name": "x"})
    state = _do(state, Move.APPROVE, PERSON, "contract:port:consensus", expected=3)
    assert next_piece(state) is Piece.PARAMETERS


def test_a_stale_command_is_refused():
    state = _do(_answered(), Move.DRAFT, AI, "contract:port:consensus", value={})
    state = _do(state, Move.REVISE, AI, "contract:port:consensus", value={"n": 2})
    with pytest.raises(Refused, match="MF0506"):
        _do(state, Move.APPROVE, PERSON, "contract:port:consensus", expected=1)


def test_changing_an_approved_port_reopens_parameters_and_keeps_values():
    state = _do(_contract_approved(), Move.DRAFT, AI, "parameters:param:min_contig",
                value={"default": 500})
    state = _do(state, Move.APPROVE, PERSON, "parameters:param:min_contig", expected=1)
    state = _do(state, Move.CHANGE, PERSON, "contract:port:consensus", value={"name": "c"},
                expected=2)
    param = state.items["parameters:param:min_contig"]
    assert param.status is Status.REOPENED
    assert param.value == {"default": 500}


def test_pieces_go_in_order():
    assert next_piece(Adaptation()) is Piece.QUESTIONS
    assert next_piece(_answered()) is Piece.CONTRACT
    with pytest.raises(Refused, match="MF0506"):
        _do(_answered(), Move.DRAFT, AI, "rules:rule:x", value={})


def test_all_approved_is_ready_to_assemble():
    state = _contract_approved()
    for key in ("parameters:none", "vocabulary:none", "rules:none"):
        state = _do(state, Move.WRITE, PERSON, key, value=None)
    assert not ready_to_assemble(state), "a tool needs a test"
    state = _do(state, Move.WRITE, PERSON, "tests:test:one", value=None)
    assert ready_to_assemble(state)


def test_the_forging_protocol_is_valid_and_draws():
    drawn = to_mermaid(FORGING)
    assert FORGING.refusal_code == "MF0506"
    for node in ("review", "draft", "assemble", "assembled"):
        assert node in drawn


def test_a_reforge_seeds_every_piece_as_proposals():
    """A re-forge starts from the registry's contract: proposals in any piece, never decisions."""
    state = _do(Adaptation(), Move.DRAFT, Actor.REGISTRY, "contract:input:reads", value={})
    assert state.items["contract:input:reads"].status is Status.PROPOSED
    assert next_piece(state) is Piece.QUESTIONS
    with pytest.raises(Refused, match="MF0505"):
        _do(state, Move.APPROVE, Actor.REGISTRY, "contract:input:reads", expected=1)


def test_reopen_piece_reopens_the_blamed_piece_itself():
    from mendel_forge.forging.rules import reopen_piece

    state = reopen_piece(_contract_approved(), Piece.CONTRACT)
    assert state.items["contract:port:consensus"].status is Status.REOPENED
    assert state.items["questions:role"].status is Status.APPROVED


@pytest.mark.parametrize("key", ["rules:rule:../../escaped", "contract:input:a/b",
                                 "nowhere:thing", "rules:rule:", "contract:input:x y"])
def test_a_key_outside_the_grammar_is_refused(key):
    """Review C1: a key names a file in the draft; nothing may climb out of it."""
    with pytest.raises(Refused, match="MF0506"):
        _do(_answered(), Move.WRITE, PERSON, key, value={})


def test_rejecting_a_revision_of_an_approved_item_keeps_the_approved_value():
    """Review I7: "no, keep it" restores what was decided, re-opening nothing."""
    state = _contract_approved()
    state = _do(state, Move.REVISE, AI, "contract:port:consensus", value={"name": "other"})
    state = _do(state, Move.REJECT, PERSON, "contract:port:consensus", expected=3)
    item = state.items["contract:port:consensus"]
    assert item.status is Status.APPROVED
    assert item.value == {"name": "consensus"}


def test_a_question_is_answered_not_approved():
    """Review I8: an answer is the person's; approving the AI's question records none."""
    state = _do(Adaptation(), Move.DRAFT, AI, "questions:role", value={"asks": "?"})
    with pytest.raises(Refused, match="MF0506"):
        _do(state, Move.APPROVE, PERSON, "questions:role", expected=1)


def test_changing_an_answer_reopens_what_was_built_on_it():
    state = _contract_approved()
    question = state.items["questions:role"]
    state = _do(state, Move.ANSWER, PERSON, "questions:role", expected=question.current.n,
                value={"choice": "alignment"}, by="r")
    assert state.items["contract:process"].status is Status.REOPENED


def test_a_person_acting_on_an_existing_item_names_its_revision():
    """Review I5: without `expected`, a write could overwrite someone else's decision."""
    state = _contract_approved()
    with pytest.raises(Refused, match="MF0506"):
        _do(state, Move.CHANGE, PERSON, "contract:port:consensus", value={"name": "x"})


def test_the_contract_needs_its_process_to_be_finished():
    """Review I2: a contract of ports alone cannot assemble."""
    state = _do(_answered(), Move.DRAFT, AI, "contract:port:consensus", value={})
    state = _do(state, Move.APPROVE, PERSON, "contract:port:consensus", expected=1)
    assert next_piece(state) is Piece.CONTRACT
    state = _do(state, Move.WRITE, PERSON, "contract:process", value={})
    assert next_piece(state) is Piece.PARAMETERS
