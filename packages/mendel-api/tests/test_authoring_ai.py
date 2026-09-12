"""The builder's model calls, against a fake transport and a real database.

**No test here reaches a provider**, and the mechanism is the seam rather than a promise:
`Client` takes a transport, and every test below supplies one that returns a committed string.
`tests/guards/test_no_live_model.py` is what keeps that true by refusing the two names that
reach a network.

**A fake rather than a recorded fixture, and it is a deliberate choice.** `RecordedTransport`
keys answers on a digest of the exact prompt, which is right for the Forge, where the question
*is* the thing under test and a prompt change should invalidate the recording. Here the thing
under test is admission and audit — what happens to an answer on the way back in — and keying on
the prompt would mean every wording change in a committed template silently turned ten behaviour
tests into ten `KeyError`s. The prompt has its own tests, next door.

Task 5 names ten cases and each has a test here: paired RNA-seq counts, many independent items,
a paired-file ambiguity, a goal correction, *why STAR?*, selecting an offered alternative, an
invented option, invalid JSON, a provider failure, and no configured model.
"""

import hashlib
import json

import pytest
from comeni_ai import Client, ModelAccess, ModelUnavailableError
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation
from mendel_api.services import authoring_ai as ai
from mendel_api.services import registry
from sqlalchemy import select, text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


# **`clean_forge` in `conftest.py` is the fixture, and a rival one here was written first.**
# The shorter list — the two authoring tables plus `ai_invocation` — is refused by Postgres,
# because `forge_message` references `ai_invocation` as well: every foreign key in that block is
# `RESTRICT`, so the whole set is truncated in one statement or none of it is. That is the
# constraint doing its job, and the shared fixture's docstring already said so.


@pytest.fixture
def stack():
    return registry.stack()


ACCESS = ModelAccess(model="fake/test", base_url="http://localhost:1")
"""A model that does not exist, reached through a transport that never calls it.

`base_url` is set so `_record` writes `provider: local`, which is the lane a developer actually
runs — and asserting on it is how the column stays meaningful.
"""


class Answers:
    """A transport returning committed bodies in order, recording what it was sent.

    Implements `Transport.send` and nothing else, so `Client` takes the unmetered path and
    `last_usage` stays `None` — which is the honest shape for a fixture: a recording has no
    duration anybody measured, and `Usage`'s nullable fields exist for exactly that.
    """

    def __init__(self, *bodies: str | Exception) -> None:
        self.bodies = list(bodies)
        self.sent: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.sent.append(prompt)
        body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        if isinstance(body, Exception):
            raise body
        return body


def _client(*bodies: str | Exception) -> Client:
    return Client(ACCESS, transport=Answers(*bodies))


def _goal_answer(**overrides) -> str:
    """A well-formed `GoalUnderstanding`, so each test overrides only what it is about."""
    body = {
        "goal": {
            "have": [{"type_id": "fastq.reads", "states": []}],
            "want": ["counts.matrix"],
            "constraints": {},
            "profile": {"measurements": []},
        },
        "have": "paired RNA-seq reads",
        "do": "align them and count reads per gene",
        "get": "a gene-level counts matrix",
        "questions": [],
    }
    body.update(overrides)
    return json.dumps(body)


def _rows() -> list[AiInvocation]:
    with session_scope() as session:
        return list(session.scalars(select(AiInvocation)).all())


# ── the goal call ─────────────────────────────────────────────────────────────────────────


def test_a_paired_rnaseq_request_comes_back_as_a_typed_goal(stack, clean_forge):
    """The flagship case: prose in, a `Goal` the resolver can run on out, and a summary the
    person can check it against."""
    client = _client(
        _goal_answer(
            goal={
                "have": [{"type_id": "fastq.reads", "states": []}],
                "want": ["counts.matrix"],
                "constraints": {"required_states": {"counts.matrix": ["gene_level"]}},
                "profile": {
                    "measurements": [
                        {"measurement": "n_samples", "value": 12, "source": "goal"}
                    ]
                },
            }
        )
    )
    request = ai.compose(prompt="I have 12 paired RNA-seq samples and want gene counts")
    outcome = ai.understand(request, stack=stack, client=client)

    assert outcome.admitted, outcome.refusal
    assert [entry.type_id for entry in outcome.reply.goal.have] == ["fastq.reads"]
    assert outcome.reply.goal.want == ["counts.matrix"]
    assert outcome.reply.goal.constraints.states_for("counts.matrix") == frozenset({"gene_level"})
    assert outcome.reply.get


def test_many_independent_items_do_not_acquire_a_sample_count(stack, clean_forge):
    """§1.7: *never invent a sample count.*

    A model that supplies one produces a goal that validates and builds, and the interface draws
    `×24 samples` as though somebody had measured it. The honest answer leaves the profile empty
    and lets the canvas say `×N items`.
    """
    client = _client(
        _goal_answer(
            goal={
                "have": [{"type_id": "genome.fasta", "states": []}],
                "want": ["qc.report"],
                "constraints": {},
                "profile": {"measurements": []},
            }
        )
    )
    request = ai.compose(prompt="I have a folder of FASTA files, QC each one")
    outcome = ai.understand(request, stack=stack, client=client)

    assert outcome.admitted, outcome.refusal
    assert outcome.reply.goal.profile.measurements == []


def test_an_ambiguous_grouping_comes_back_as_a_question(stack, clean_forge):
    """The paired-file ambiguity, which is the case §1.7 says must never be settled silently.

    Twenty-four files is a count, not a structure, and the two readings build different
    pipelines — so the first call's job is to notice, not to choose.
    """
    client = _client(
        _goal_answer(
            questions=[
                {
                    "asks": "how do those 24 files group into samples?",
                    "why_open": "the grouping changes what is built and was not stated",
                    "choices": ["24 independent items", "12 paired samples"],
                    "exhaustive": False,
                }
            ]
        )
    )
    request = ai.compose(prompt="I have 24 fastq files, count genes")
    outcome = ai.understand(request, stack=stack, client=client)

    assert outcome.admitted, outcome.refusal
    assert len(outcome.reply.questions) == 1
    assert outcome.reply.questions[0].exhaustive is False


def test_a_goal_naming_a_type_the_registry_does_not_declare_is_refused(stack, clean_forge):
    """`MI0204`, and the reason it refuses rather than trims.

    `rnaseq.counts` is not a declared type. It reads perfectly, validates as a string, and
    routes to nothing — dropping it silently would leave a goal quietly missing the thing
    somebody asked for.
    """
    client = _client(
        _goal_answer(
            goal={
                "have": [{"type_id": "fastq.reads", "states": []}],
                "want": ["rnaseq.counts"],
                "constraints": {},
                "profile": {"measurements": []},
            }
        )
    )
    outcome = ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0204"
    assert "rnaseq.counts" in outcome.refusal


def test_a_goal_naming_a_state_that_type_does_not_declare_is_refused(stack, clean_forge):
    """The same code on the other axis. `fastq.reads` is real and `polished` is not one of its
    states, which is the subtler half — the type check alone would pass this."""
    client = _client(
        _goal_answer(
            goal={
                "have": [{"type_id": "fastq.reads", "states": ["polished"]}],
                "want": ["counts.matrix"],
                "constraints": {},
                "profile": {"measurements": []},
            }
        )
    )
    outcome = ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0204"
    assert "polished" in outcome.refusal


def test_a_goal_naming_a_measurement_nobody_declares_is_refused(stack, clean_forge):
    """Routed through `MeasurementRegistry.check`, which is the declared validating path — a
    second membership test written here would be the duplicate `test_construction.py` exists to
    prevent."""
    client = _client(
        _goal_answer(
            goal={
                "have": [{"type_id": "fastq.reads", "states": []}],
                "want": ["counts.matrix"],
                "constraints": {},
                "profile": {
                    "measurements": [
                        {"measurement": "sample_purity", "value": 0.9, "source": "goal"}
                    ]
                },
            }
        )
    )
    outcome = ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0204"


# ── the chat call ─────────────────────────────────────────────────────────────────────────


DRAFT = ai.compose(
    prompt="why STAR?",
    steps=[("align", "nf-core/star/align@1.11.0"), ("sort", "nf-core/samtools/sort@1.21.0")],
    options=["opt_hisat2", "opt_keep_star"],
)


def test_a_goal_correction_comes_back_as_a_revision(clean_forge):
    """Not an edit. A person saying *actually it is single-end* is re-describing the analysis,
    and that re-enters goal understanding rather than patching the graph in place."""
    client = _client(json.dumps({"revise": "the reads are single-end, not paired"}))
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert outcome.reply.revise
    assert outcome.reply.chose is None


def test_why_star_comes_back_as_an_explanation_grounded_on_a_step(clean_forge):
    """The explanation case, and `refers_to` is what makes it checkable: the step it is about is
    an id the engine issued, not a name recovered from prose."""
    client = _client(
        json.dumps(
            {
                "explain": "STAR is here because you asked for splice-aware gene counts",
                "refers_to": ["align"],
            }
        )
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert outcome.reply.refers_to == ["align"]


def test_an_explanation_citing_a_step_that_is_not_in_the_draft_is_refused(clean_forge):
    """`MI0205` on the reference axis.

    A fluent, checkable-sounding claim about a step the person cannot see is the hardest kind of
    wrong answer for them to catch, which is why this is refused rather than shown with the
    citation quietly dropped.
    """
    client = _client(
        json.dumps({"explain": "TRIMGALORE cleans the adapters first", "refers_to": ["trim"]})
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0205"
    assert "trim" in outcome.refusal


def test_selecting_an_offered_alternative_comes_back_as_that_option_id(clean_forge):
    """The ordinary case the whole boundary exists for: the answer is an id the engine minted,
    so nothing about the choice was authored by the model."""
    client = _client(json.dumps({"chose": "opt_hisat2"}))
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert outcome.reply.chose == "opt_hisat2"


def test_an_option_nobody_offered_is_refused(clean_forge):
    """**The product claim, as a test.** *A model cannot produce a value outside the candidate
    set* is a sentence about a comparison, and this is the comparison failing to hold."""
    client = _client(json.dumps({"chose": "opt_salmon"}))
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0205"
    assert "opt_salmon" in outcome.refusal


def test_a_tool_named_in_prose_cannot_arrive_as_a_step_reference(clean_forge):
    """§1.3 from the other side: there is nowhere in the shape to put a module id, so a model
    that wants one has to cite a step — and an uncommitted tool is not a step."""
    client = _client(
        json.dumps({"setting": {
            "node": "salmon",
            "setting": "libtype",
            "value": "A",
            "because": "it is the usual default",
        }})
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0205"


def test_an_unsupported_request_is_an_admitted_answer_and_not_a_refusal(clean_forge):
    """Saying *I cannot do that here* is the model working, not failing. It is recorded as a
    success, because the call did exactly what it was asked to do."""
    client = _client(
        json.dumps({"unsupported": "I cannot add a tool to the registry from this conversation"})
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert _rows()[0].state == "succeeded"


# ── what goes wrong ───────────────────────────────────────────────────────────────────────


def test_an_answer_that_is_not_json_is_refused_and_recorded(clean_forge):
    """`comeni-ai` will not hand over an answer that does not validate, so this never reaches
    admission — and the row still has to exist, because a model that cannot produce the shape is
    the finding worth measuring."""
    client = _client("I think you should probably use STAR for this.")
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MA0004"
    assert _rows()[0].state == "refused"


def test_a_provider_failure_is_recorded_as_failed_and_never_as_refused(clean_forge):
    """The distinction `InvocationState` was split for: this one is retried, a refusal is a
    prompt or a model that cannot do the job. Folding them makes the second invisible."""
    client = _client(ModelUnavailableError("MA0007: fake/test: connection refused"))
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MA0007"
    assert _rows()[0].state == "failed"


def test_a_provider_failure_records_a_code_and_never_the_providers_words(clean_forge):
    """`failure_code` holds a declared code. A provider's own text carries an endpoint and
    sometimes a key prefix, and this column is rendered on a page."""
    client = _client(ModelUnavailableError("MA0002: the provider refused the credentials"))
    ai.follow_up(DRAFT, client=client)

    row = _rows()[0]
    assert row.failure_code == "MA0002"
    assert "credentials" not in row.failure_code


def test_no_configured_model_refuses_before_anything_is_recorded(monkeypatch, clean_forge):
    """**No row, because nothing was called.** An `ai_invocation` for a call that never happened
    would put a zero in every aggregate that counts attempts.

    Leaving the model unset is a legitimate way to run this, not a misconfiguration — but the
    builder is the one path that genuinely needs one, and saying so is the whole of the fix.
    """
    for name in ("COMENI_AI_MODEL", "MENDEL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    outcome = ai.follow_up(DRAFT)

    assert not outcome.admitted
    assert outcome.code == "MI0106"
    assert outcome.invocation_id is None
    assert _rows() == []


# ── grounding and the audit row ───────────────────────────────────────────────────────────


def test_the_tail_the_model_is_shown_is_bounded(clean_forge):
    """`CHAT_TAIL`, and it is applied where the payload is built rather than by each caller.

    Unbounded, a long conversation eventually pushes the pipeline out of the window and the
    model answers from the transcript alone — which is the one thing grounding exists to stop.
    """
    request = ai.compose(
        prompt="and now?",
        turns=[("person", f"turn {n}") for n in range(20)],
    )
    assert len(request.turns) == 6
    assert request.turns[-1].content == "turn 19"


def test_the_prompt_that_was_sent_carries_the_steps_and_the_option_ids(clean_forge):
    """What the model is shown and what it is held to are one list.

    If the options were rendered as labels, a reply naming a label would be refused by a check
    the model was never given the means to satisfy.
    """
    client = _client(json.dumps({"proceed": True}))
    ai.follow_up(DRAFT, client=client)

    sent = client._transport.sent[0]
    assert "opt_hisat2" in sent
    assert "align — nf-core/star/align@1.11.0" in sent


def test_the_recorded_row_names_the_builder_and_what_actually_crossed_the_wire(
    stack, clean_forge
):
    """`agent="builder"` is what the shared table was built for, and the digest is over
    `last_prompt` rather than the template render — the field exists so a stored row can be
    compared against a re-render, and the schema `generate` appends is part of what was sent."""
    client = _client(_goal_answer())
    outcome = ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)

    row = _rows()[0]
    assert row.id == outcome.invocation_id
    assert row.agent == "builder"
    assert row.purpose == "goal"
    assert row.prompt_id == "builder.goal.v1"
    assert row.prompt_version == "v1"
    assert row.provider == "local"
    assert row.state == "succeeded"
    assert row.failure_code == ""
    assert row.prompt_digest == hashlib.sha256(client.last_prompt.encode()).hexdigest()


def test_the_two_calls_are_told_apart_by_purpose_under_one_agent(stack, clean_forge):
    """One member per committed prompt id, scoped by `agent` rather than spelled to be globally
    unique — the Forge declares a `chat` purpose too, and that column is what separates them."""
    ai.understand(ai.compose(prompt="count genes"), stack=stack, client=_client(_goal_answer()))
    ai.follow_up(DRAFT, client=_client(json.dumps({"proceed": True})))

    assert {row.purpose for row in _rows()} == {"goal", "chat"}
    assert {row.agent for row in _rows()} == {"builder"}
