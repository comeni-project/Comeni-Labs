"""A model's reply is a list of changes, each heard (quoting the person) or suggested
(Part I.0 spec §5.3, §7)."""

import pytest
from mendel_api.authoring.types import ChatReply, Understanding
from mendel_api.services import registry, replies

TURNS = [
    (
        1,
        "Gene counts from my paired-end Illumina reads, 150 bp, and differential "
        "expression between treated and control",
    )
]


@pytest.fixture
def stack():
    return registry.stack()


def _issued(stack, reply):
    return replies.issue(
        replies.admit(reply, stack),
        turns=TURNS,
        stack=stack,
        invocation_id="inv-1",
        first_reading=isinstance(reply, Understanding),
    )


def test_a_quoted_fact_is_heard_with_its_turn(stack):
    got = _issued(
        stack,
        Understanding(
            wants=[{"type": "counts.matrix", "quote": "Gene counts"}],
            facts=[
                {"subject": "paired", "value": True, "quote": "paired-end"},
                {"subject": "read_length", "value": 150, "quote": "150 bp"},
            ],
        ),
    )
    heard = {(c.kind, c.subject): c for c in got.heard}
    assert heard[("measurement", "paired")].heard == "paired-end"
    assert heard[("measurement", "paired")].heard_seq == 1
    assert heard[("measurement", "read_length")].value == 150
    assert heard[("want", "counts.matrix")].heard == "Gene counts"
    assert all(c.actor == "model" and c.invocation_id == "inv-1" for c in got.heard)
    assert got.suggested == []


def test_an_unquoted_fact_is_suggested(stack):
    got = _issued(
        stack,
        Understanding(
            wants=[{"type": "counts.matrix", "quote": "Gene counts"}],
            facts=[{"subject": "strandedness", "value": "reverse"}],
        ),
    )
    assert [(c.kind, c.subject) for c in got.suggested] == [("measurement", "strandedness")]


def test_an_unquoted_want_is_still_issued(stack):
    """Gathering needs the want; the goal card's *That's right* confirms it."""
    got = _issued(stack, Understanding(wants=[{"type": "counts.matrix"}]))
    assert [(c.kind, c.subject, c.heard) for c in got.heard] == [("want", "counts.matrix", None)]


def test_not_offered_is_heard_or_dropped_never_suggested(stack):
    got = _issued(
        stack,
        Understanding(
            wants=[{"type": "counts.matrix", "quote": "Gene counts"}],
            not_offered=[{"quote": "differential expression"}, {"quote": "variant calling"}],
        ),
    )
    assert [(c.kind, c.subject) for c in got.heard if c.kind == "asked"] == [
        ("asked", "differential expression")
    ]
    assert got.dropped == ["variant calling"]
    assert not [c for c in got.suggested if c.kind == "asked"]


def test_one_subject_said_two_ways_is_suggested_both_ways(stack):
    """Review Focus 3."""
    got = _issued(
        stack,
        ChatReply(
            facts=[
                {"subject": "paired", "value": True, "quote": "paired-end"},
                {"subject": "paired", "value": False, "quote": "Illumina reads"},
            ]
        ),
    )
    assert not [c for c in got.heard if c.subject == "paired"]
    assert sorted(c.value for c in got.suggested if c.subject == "paired") == [False, True]


def test_an_input_said_is_held(stack):
    got = _issued(
        stack,
        Understanding(
            wants=[{"type": "counts.matrix"}],
            inputs=[{"type": "fastq.reads", "quote": "Illumina reads"}],
        ),
    )
    held = next(c for c in got.heard if c.kind == "input")
    assert held.value is True and held.subject == "fastq.reads"


def test_a_retract_takes_the_kind_its_subject_implies(stack):
    got = _issued(
        stack,
        ChatReply(
            retract=[{"subject": "read_length", "quote": "150 bp"}, {"subject": "genome.fasta"}]
        ),
    )
    assert {(c.kind, c.subject, c.retract) for c in got.heard} == {
        ("measurement", "read_length", True)
    }
    assert {(c.kind, c.subject, c.retract) for c in got.suggested} == {
        ("input", "genome.fasta", True)
    }


@pytest.mark.parametrize(
    "reply",
    [
        Understanding(wants=[{"type": "made.up"}]),
        ChatReply(facts=[{"subject": "read_length", "value": -3}]),
        ChatReply(facts=[{"subject": "read_length", "value": "fifty"}]),
        ChatReply(pins=[{"type": "alignment.bam", "tool": "nf-core/nothing@1.0.0"}]),
        ChatReply(requires=[{"type": "counts.matrix", "states": ["no_such_state"]}]),
        # A derived profiling type is no builder's to name (#346). A `requires` of one names a
        # state it does not have; a want or an input of one met no check at all.
        Understanding(wants=[{"type": "measurement.read_length"}]),
        ChatReply(inputs=[{"type": "measurement.read_length"}]),
    ],
)
def test_an_undeclared_id_is_refused_at_admission(stack, reply):
    with pytest.raises(ValueError, match="MI0204"):
        replies.admit(reply, stack)


def test_a_number_written_as_text_is_read_by_its_declared_kind(stack):
    """Issue 323, from the walk: `"50"` for an integer measurement refused the whole reply.
    It is read as the declaration says, and heard when the quote holds the number."""
    got = _issued(
        stack,
        ChatReply(facts=[{"subject": "read_length", "value": "150", "quote": "150 bp"},
                         {"subject": "paired", "value": "true", "quote": "paired-end"}]),
    )
    heard = {c.subject: c.value for c in got.heard}
    assert heard == {"read_length": 150, "paired": True}
    assert type(heard["read_length"]) is int


def test_a_quote_is_checked_against_what_the_person_typed_in_this_session():
    from comeni_core.plan.draft import DraftGraph
    from mendel_api.services import drafts
    from mendel_api.services import session as facade
    from mendel_api.stages import describe
    from mendel_api_tests.database import reachable
    from mendel_authoring import commands

    if not reachable():
        pytest.skip("no database")
    draft = drafts.create(DraftGraph(), "t", "ana")
    sid = facade.perform(commands.OpenSession(draft, "ana")).result
    answer = describe.record_said(sid, "paired-end reads, 150 bp")
    # `record_said` returns the pending answer's seq; the person's own turn is just before it.
    assert replies.person_turns(sid) == [(answer - 1, "paired-end reads, 150 bp")]


def test_an_unquoted_retraction_of_a_want_is_only_suggested(stack):
    """Review C1: the want exception covers the first reading's wants, never a retraction."""
    got = replies.issue(
        replies.admit(ChatReply(retract=[{"subject": "counts.matrix"}]), stack),
        turns=TURNS,
        stack=stack,
        invocation_id="i",
        wanted=frozenset({"counts.matrix"}),
    )
    assert not got.heard
    assert [(c.kind, c.retract) for c in got.suggested] == [("want", True)]


def test_a_want_said_two_ways_is_not_heard(stack):
    got = replies.issue(
        replies.admit(
            ChatReply(
                wants=[{"type": "counts.matrix", "quote": "Gene counts"}],
                retract=[{"subject": "counts.matrix", "quote": "Gene counts"}],
            ),
            stack,
        ),
        turns=TURNS,
        stack=stack,
        invocation_id="i",
        wanted=frozenset({"counts.matrix"}),
    )
    assert not [c for c in got.heard if c.kind == "want"]


def test_in_chat_an_unquoted_new_want_is_only_suggested(stack):
    got = replies.issue(
        replies.admit(ChatReply(wants=[{"type": "qc.report"}]), stack),
        turns=TURNS,
        stack=stack,
        invocation_id="i",
    )
    assert not got.heard and [c.subject for c in got.suggested] == ["qc.report"]


def test_a_number_is_heard_only_when_the_quote_holds_it(stack):
    """Review M2 (re-graded Important): a quote proves words were typed; for a number it must
    be the number's words, or "the" would make any value heard."""
    got = _issued(
        stack,
        ChatReply(
            facts=[
                {"subject": "read_length", "value": 150, "quote": "paired-end"},
                {"subject": "read_length", "value": 150, "quote": "150 bp"},
            ]
        ),
    )
    assert [(c.subject, c.heard) for c in got.heard] == [("read_length", "150 bp")]
    assert [(c.subject, c.heard) for c in got.suggested] == [("read_length", None)]


def test_a_not_offered_phrase_too_long_to_keep_is_dropped_not_a_crash(stack):
    """Review I2: a quote longer than a change's subject crashed the turn job."""
    long = "differential expression between treated and control " * 6
    got = replies.issue(
        replies.admit(ChatReply(not_offered=[{"quote": long.strip()}]), stack),
        turns=[(1, long)],
        stack=stack,
        invocation_id="i",
    )
    assert got.heard == [] and got.dropped == [long.strip()]
