"""The authoring protocol, asked of the types rather than of a running session.

**Nothing here touches a database or a model.** Task 3 persists these and Task 6 fills them in;
what this file holds is the shape both of those have to agree on — which block kinds exist, what
a proposal may be, and what a model is allowed to reply.

The rule the file exists to keep: **the protocol expresses a state rather than inferring it from
an absent field.** A `None` that means "not yet" and a `None` that means "no" are the same value,
and a reader six months later cannot tell which was meant.
"""

import pytest
from mendel_api.authoring import types as t
from pydantic import ValidationError

# ── modes and phases ──────────────────────────────────────────────────────────────────────


def test_the_two_modes_are_closed():
    """Build and Spawn are policies over one engine (§1.2), so they are two members of one
    enum and not two code paths. A third mode is a design change, and it fails here first."""
    assert {m.value for m in t.Mode} == {"build", "spawn"}


def test_every_phase_in_the_state_diagram_exists():
    """§2's diagram, as a vocabulary. It is asserted literally because a phase nobody named is
    a phase the reducer will infer from absent fields."""
    assert {p.value for p in t.Phase} == {
        "understanding",
        "goal_review",
        "resolving",
        "building",
        "complete",
        "failed",
    }


def test_a_proposal_state_says_stale_out_loud():
    """`stale` is the one that matters. A proposal made against an older revision is not
    `rejected` — nobody rejected it — and it is not `pending`, because applying it would write
    over somebody's newer work. §2 requires the state to exist rather than be deduced."""
    assert {s.value for s in t.ProposalState} == {"pending", "accepted", "rejected", "stale"}


def test_a_turn_can_be_pending_without_being_failed():
    """A user turn appears immediately and its assistant turn is pending until the model
    answers. Two booleans would make `pending and failed` representable; an enum does not."""
    assert {s.value for s in t.TurnState} == {"pending", "answered", "failed"}


# ── blocks ────────────────────────────────────────────────────────────────────────────────


def test_every_block_kind_in_the_spec_has_a_type():
    """§2 lists eight blocks. The frontend renders them with an exhaustive switch, so a kind
    with no type here is a kind the browser cannot be made to handle."""
    assert {k.value for k in t.BlockKind} == {
        "narrative",
        "goal_summary",
        "question",
        "step_proposal",
        "setting_request",
        "change_set",
        "receipt",
        "notice",
    }


def test_every_block_kind_is_reachable_through_the_union():
    """The discriminated union must cover the enum. A kind declared and left out of the union
    typechecks fine and fails at the first response that carries it."""
    covered = {block.model_fields["kind"].default for block in t.BLOCK_TYPES}
    assert covered == set(t.BlockKind)


def test_a_block_is_parsed_by_its_discriminator():
    parsed = t.parse_block({"kind": "narrative", "id": "b1", "text": "Two steps left."})
    assert isinstance(parsed, t.Narrative)
    assert parsed.kind is t.BlockKind.NARRATIVE


def test_an_unknown_block_kind_is_refused_rather_than_guessed():
    with pytest.raises(ValidationError):
        t.parse_block({"kind": "diagram", "id": "b1", "text": "..."})


def test_every_block_carries_a_stable_id():
    """§2: every interactive block has a stable id, and the browser posts ids rather than
    copied objects. A block without one cannot be referred to in the next turn."""
    assert len(t.BLOCK_TYPES) == len(t.BlockKind), "the walk is not walking"
    for block in t.BLOCK_TYPES:
        assert "id" in block.model_fields, f"{block.__name__} has no id"


def test_every_option_carries_a_stable_id():
    option = t.Option(id="opt_star", label="STAR")
    assert option.id == "opt_star"
    with pytest.raises(ValidationError):
        t.Option(label="STAR")


# ── the shapes are closed ─────────────────────────────────────────────────────────────────


def test_a_block_refuses_a_field_nobody_declared():
    """`extra="forbid"`, for the reason `EgressPayload` has it: a field that can be added at
    runtime is a field no review ever saw."""
    with pytest.raises(ValidationError):
        t.Narrative(id="b1", text="fine", context={"path": "/data/PT-4471023"})


def test_prose_is_bounded():
    """An unbounded string in a protocol is an unbounded string in a prompt. The Forge already
    bounds `why`; this bounds narrative for the same reason."""
    with pytest.raises(ValidationError):
        t.Narrative(id="b1", text="x" * (t.PROSE_LIMIT + 1))
    assert t.Narrative(id="b1", text="x" * t.PROSE_LIMIT).text


def test_the_conversation_tail_is_bounded_and_follows_the_forge():
    """§2 says follow the Forge precedent unless evaluation shows otherwise. It has not yet, so
    the number is the same one and this test is where a change to it gets argued."""
    assert 0 < t.CHAT_TAIL <= 12


# ── what a model may reply ────────────────────────────────────────────────────────────────


def test_goal_understanding_and_follow_up_intent_are_separate_shapes():
    """§Task 2: the first call turns prose into a `Goal`; a later one turns prose into an
    intent about a pipeline that already exists. One shape doing both is a shape where half the
    fields are always null, which is the local model's worst case."""
    assert t.GoalUnderstanding is not t.AuthoringIntent
    assert set(t.GoalUnderstanding.model_fields) != set(t.AuthoringIntent.model_fields)


def test_an_intent_carries_exactly_one_thing():
    """Mutually exclusive by validation, not by convention. A reply naming both a chosen option
    and a goal revision is a reply nobody can act on, and the ambiguity must not reach the
    service layer to be resolved by field order."""
    assert t.AuthoringIntent(chose="opt_star").chose == "opt_star"
    assert t.AuthoringIntent(revise="use hisat2 instead").revise

    with pytest.raises(ValidationError):
        t.AuthoringIntent(chose="opt_star", revise="use hisat2 instead")
    with pytest.raises(ValidationError):
        t.AuthoringIntent()


def test_an_intent_cannot_answer_with_a_value_outside_the_offered_set():
    """The product claim, at the type level: a model addressed by id **cannot** produce a value
    outside the candidate set. `chose` is an `OptionId`, so it is an identifier — prose, a path
    and a contract body are all refused before anything looks at whether it was offered."""
    with pytest.raises(ValidationError):
        t.AuthoringIntent(chose="../../etc/passwd")
    with pytest.raises(ValidationError):
        t.AuthoringIntent(chose="whatever the tool needs")


def test_a_reply_cannot_author_yaml_or_a_graph():
    """§1.3 — the model never authors YAML, graph JSON, UI markup or compatibility. There is
    nowhere in either reply shape to put one, and this is the test that notices a field being
    added because it was convenient."""
    for shape in (t.GoalUnderstanding, t.AuthoringIntent):
        assert shape.model_fields, f"{shape.__name__} has no fields to check"
        for name, field in shape.model_fields.items():
            assert "dict" not in str(field.annotation).lower(), f"{shape.__name__}.{name}"
            assert "Any" not in str(field.annotation), f"{shape.__name__}.{name}"


# ── the request that carries a phase transition ───────────────────────────────────────────


def test_a_mutating_request_carries_the_revision_it_was_made_against():
    """§2: every mutating request carries `expected_revision`, and a stale acceptance returns a
    coded conflict rather than writing. A request that cannot say what it saw cannot be checked
    for staleness at all, so the field is required rather than defaulted."""
    accept = t.AcceptProposal(proposal_id="p1", expected_revision=4)
    assert accept.expected_revision == 4
    with pytest.raises(ValidationError):
        t.AcceptProposal(proposal_id="p1")


def test_a_person_speaking_is_not_a_mutating_request():
    """Saying something is not applying something. A `Say` carries no revision because it
    proposes no change — conflating the two is how a chat message acquires the power to
    overwrite a draft."""
    assert "expected_revision" not in t.Say.model_fields


# ── the six intents builder.chat.v1 can return ────────────────────────────────────────────
#
# Task 2 shipped three — chose, revise, explain — because those were the three §1.3 spelled out
# as sentences. Task 5's prompt has to name the whole closed set, and the other three are what a
# person actually does in the middle of a build: name a value for an open setting, say *go on*,
# or ask for something this conversation cannot do. Adding them here rather than letting the
# prompt describe a seventh, untyped "other" is the point — an intent with no field is an intent
# the service layer has to parse out of prose.


def test_every_intent_the_chat_prompt_offers_has_somewhere_to_go():
    """The prompt and the shape are one closed set stated twice, and they must agree.

    A prompt naming an intent the shape cannot carry produces a reply that validates as
    something else — *continue* arriving as an empty `explain`, which reads as the model having
    answered a question nobody asked.
    """
    for field in ("chose", "revise", "explain", "setting", "proceed", "unsupported"):
        assert field in t.AuthoringIntent.model_fields, f"an intent cannot express {field}"


def test_continuing_is_still_exactly_one_thing():
    """`proceed` is a bool and joins the exclusivity check anyway. *Continue, and also revise the
    goal* is not a turn anybody can act on, and a bool that sat outside the check would be the
    one way to express it."""
    assert t.AuthoringIntent(proceed=True).proceed is True
    with pytest.raises(ValidationError):
        t.AuthoringIntent(proceed=True, revise="use hisat2 instead")


def test_an_unsupported_request_says_so_in_words():
    """The sixth intent carries prose because *no* is not an answer by itself — the person needs
    to know what would work instead, and that sentence has to live somewhere typed."""
    assert t.AuthoringIntent(unsupported="I cannot change the registry from here").unsupported


def test_a_proposed_setting_names_a_step_and_a_setting_and_never_a_path():
    """The one place a model may produce a value rather than choose an id, which is why the
    value is guarded rather than free.

    §1.3 permits a proposed setting revision *that still requires validation and explicit
    acceptance*. `HumanParamValue` is the guard `ParamOverride` already uses, and it is the
    right one here for the reason audit A3 gave: a path-shaped value is the thing neither a
    person nor a model may write into a goal.
    """
    proposal = t.SettingProposal(
        node="counts", setting="min_mqs", value=20, because="they asked for stricter mapping"
    )
    assert proposal.value == 20
    with pytest.raises(ValidationError):
        t.SettingProposal(
            node="counts",
            setting="min_mqs",
            value="/data/patients/PT-4471023/S1_R1.fastq.gz",
            because="",
        )


def test_a_proposed_setting_cannot_name_a_step_that_is_not_an_identifier():
    """`node` is a `NodeId`, so the reference is refused before anything checks whether the step
    exists. Admission checks the second half; the type is what makes the first half free."""
    with pytest.raises(ValidationError):
        t.SettingProposal(node="../etc", setting="min_mqs", value=20, because="")


def test_an_explanation_refers_to_steps_by_id():
    """Task 5: *model explanations must refer to known step ids; reject invented references*.

    The ids go in a typed list rather than being parsed back out of the prose, which is what
    makes rejecting an invented one a set difference instead of a regex over English.
    """
    intent = t.AuthoringIntent(explain="STAR is here because you asked for splice-aware counts")
    assert intent.refers_to == []
    assert t.AuthoringIntent(explain="it sorts the BAM", refers_to=["sort"]).refers_to == ["sort"]
    with pytest.raises(ValidationError):
        t.AuthoringIntent(explain="it sorts the BAM", refers_to=["../../etc/passwd"])


def test_a_goal_understanding_carries_the_questions_it_could_not_settle():
    """The grouping question has to be able to come back from the first call.

    §1.7 says *do not infer one silently*, and a first call with nowhere to put a question can
    only infer: the shape would force a `Goal` that states a sample structure nobody confirmed.
    """
    assert "questions" in t.GoalUnderstanding.model_fields
    asked = t.AskedQuestion(
        asks="how do those 24 files group?",
        why_open="the grouping changes what gets built and was not stated",
        choices=["24 independent items", "12 paired samples"],
        exhaustive=False,
    )
    assert asked.exhaustive is False


def test_a_question_the_model_raises_carries_labels_and_not_ids():
    """**The engine issues ids, always** — rule 2 of this module, applied to the one case that
    tempts otherwise.

    A question the model invents has options nobody has minted yet, and letting the model name
    them would mean the next turn's `chose` is checked against a set the model itself authored.
    The engine mints the ids when it stores the question, and *that* is what the next reply is
    held to.
    """
    assert "id" not in t.AskedQuestion.model_fields
    for name, field in t.AskedQuestion.model_fields.items():
        assert "OptionId" not in str(field.annotation), f"AskedQuestion.{name} names an id"
