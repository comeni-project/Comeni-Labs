"""The tier-4 adapter: what it may answer, and what it does when it cannot.

**No database and no provider.** The adapter writes nothing and `Client` takes a transport, so
every case here is a pure function of a canned string — which is also the point of the design:
a resolver that opened a transaction per decision could not be tested this way, and could not be
replayed either.

The discriminating test is `test_a_value_that_was_not_offered_leaves_the_question_open`. Every
other case passes whether or not membership is checked, because a well-behaved model answers
from the list anyway.
"""

import json

import pytest
from comeni_ai import Client, ModelAccess
from comeni_core.plan.decision import ParamAsked, ProducerAsked, Resolution, SourceAsked
from comeni_core.plan.tiers import ValueSource
from mendel_api.authoring import resolver as r
from mendel_resolver.ports import NoCandidatesError

STAR = "nf-core/star/align@1.11.0"
HISAT2 = "nf-core/hisat2/align@2.2.1"

ACCESS = ModelAccess(model="fake/test")


class Answers:
    """A transport returning one canned body, recording what it was sent."""

    def __init__(self, body: str) -> None:
        self.body = body
        self.sent: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.sent.append(prompt)
        return self.body


def _chose(value: str, why: str = "it is splice-aware") -> Client:
    return Client(ACCESS, transport=Answers(json.dumps({"value": value, "why": why})))


def _producer(**overrides) -> ProducerAsked:
    fields = {
        "node_id": "align",
        "subject": "producer:alignment.bam",
        "what": "which contract produces the aligned BAM",
        "why_open": "two contracts produce it and nothing in the goal distinguishes them",
        "candidates": [STAR, HISAT2],
    }
    fields.update(overrides)
    return ProducerAsked(**fields)


# ── choosing ──────────────────────────────────────────────────────────────────────────────


def test_it_answers_with_one_of_the_offered_candidates(monkeypatch):
    """The ordinary case, and every field the record needs to be honest afterwards."""
    adapter = r.ModelResolver(_chose(STAR))
    answer = adapter.resolve(_producer())

    assert isinstance(answer, Resolution)
    assert answer.value == STAR
    assert answer.how is ValueSource.MODEL
    assert answer.by == "fake/test"
    assert "splice-aware" in answer.why


def test_a_value_that_was_not_offered_leaves_the_question_open():
    """**The discriminating test.** A model naming a real-looking contract nobody offered must
    not reach the pipeline, and the fallback is what keeps the build running without it.

    `choose_one` refuses the value; the question comes back settled by the flag, which is
    precisely how Build mode would have left it — tier 4, first candidate, and a reason saying
    nobody judged it.
    """
    adapter = r.ModelResolver(_chose("nf-core/salmon/quant@1.10.0"))
    answer = adapter.resolve(_producer())

    assert answer.value == STAR, "an unoffered value reached the pipeline"
    assert answer.how is not ValueSource.MODEL
    assert answer.by == "flag-only"
    assert "without judgement" in answer.why


def test_a_declined_answer_leaves_the_question_exactly_as_build_mode_would():
    """A provider outage or an unparseable reply is not a failed build. Spawn degrades to
    Build's behaviour for that one question rather than losing the whole pipeline."""
    adapter = r.ModelResolver(Client(ACCESS, transport=Answers("I would probably use STAR.")))
    answer = adapter.resolve(_producer())

    assert answer.by == "flag-only"
    assert answer.how is not ValueSource.MODEL


def test_a_question_with_no_candidates_refuses_exactly_as_the_flag_only_path_does():
    """Nothing in the resolver catches this today, so softening it here would make whether a
    build fails depend on which mode it ran in."""
    adapter = r.ModelResolver(_chose(STAR))
    with pytest.raises(NoCandidatesError):
        adapter.resolve(_producer(candidates=[]))


def test_a_parameter_whose_only_candidate_is_null_is_never_put_to_a_model():
    """`str(None)` would offer the model the literal string `"None"` to choose, and a model
    that took it would have answered with a value that is not the candidate."""
    client = _chose("None")
    adapter = r.ModelResolver(client)
    answer = adapter.resolve(
        ParamAsked(node_id="align", subject="seq_platform", candidates=[None])
    )

    assert answer.by == "flag-only"
    assert client.last_prompt is None, "a model was asked about a question with no real options"


# ── what crosses the door ─────────────────────────────────────────────────────────────────


def test_the_projection_onto_door_two_is_total_for_all_three_kinds():
    """The same three the egress guard builds. This is door 2's first producer, and a kind that
    could not cross would be a tier-4 question a model is silently never asked."""
    for asked in (
        ParamAsked(node_id="align", subject="seq_platform", candidates=[None]),
        SourceAsked(
            node_id="sort",
            subject="source:reads",
            candidates=["align.bam", "trim.reads"],
            type_id="alignment.bam",
            required=["coordinate_sorted"],
        ),
        _producer(),
    ):
        request = r.request_for(asked)
        assert request.subject == asked.subject


def test_the_model_is_shown_the_question_its_reason_and_its_evidence():
    """Composed from the door payload rather than the ambiguity, so what a guard inspects and
    what a model reads are the same object."""
    client = _chose(STAR)
    r.ModelResolver(client).resolve(_producer())
    sent = client.last_prompt

    assert "producer:alignment.bam" in sent
    assert "two contracts produce it" in sent
    assert STAR in sent and HISAT2 in sent


def test_no_candidate_outside_the_offered_set_appears_in_the_prompt():
    """The list the model reads and the list membership is checked against are one list —
    `choose_one` appends it, and the template has no placeholder for candidates at all."""
    client = _chose(STAR)
    r.ModelResolver(client).resolve(_producer())

    assert "salmon" not in client.last_prompt


def test_a_question_with_no_evidence_says_so_rather_than_leaving_a_blank():
    """A heading with nothing under it reads as something withheld."""
    client = _chose(STAR)
    r.ModelResolver(client).resolve(_producer())

    assert "carries no evidence" in client.last_prompt


# ── what the caller can audit ─────────────────────────────────────────────────────────────


def test_every_call_is_recorded_for_the_caller_to_write_down():
    """The adapter writes no rows — it runs inside the resolver's loop, which must stay free of
    I/O — so the record has to survive in memory until the build finishes."""
    adapter = r.ModelResolver(_chose(STAR))
    adapter.resolve(_producer())

    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert call.subject == "producer:alignment.bam"
    assert call.chosen == STAR
    assert call.prompt_id == "builder.tier4.v1"
    assert call.prompt_digest and call.refusal is None


def test_a_refused_answer_is_recorded_with_its_code_and_no_choice():
    """The row worth reading afterwards. A model that keeps naming unoffered contracts is a
    finding, and it is invisible if only successes are recorded."""
    adapter = r.ModelResolver(_chose("nf-core/salmon/quant@1.10.0"))
    adapter.resolve(_producer())

    call = adapter.calls[0]
    assert call.chosen is None
    assert call.refusal and "MA0005" in call.refusal


def test_nothing_is_recorded_for_a_question_never_put_to_a_model():
    """A call that did not happen must not appear in the audit — a zero-token row would put a
    call in every aggregate that counts attempts."""
    adapter = r.ModelResolver(_chose(STAR))
    adapter.resolve(ParamAsked(node_id="align", subject="seq_platform", candidates=[None]))

    assert adapter.calls == []


def test_a_multi_line_reason_is_collapsed_rather_than_cut():
    """`Resolution.why` is a `Line` and reaches `pipeline.yml`. Truncating at the newline would
    keep the half that says what and drop the half that says why."""
    adapter = r.ModelResolver(_chose(STAR, why="it is splice-aware\nand the goal wants junctions"))
    answer = adapter.resolve(_producer())

    assert "\n" not in answer.why
    assert "junctions" in answer.why
