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
from mendel_api_tests.database import reachable
from sqlalchemy import select

pytestmark = pytest.mark.skipif(not reachable(), reason="no database — run `make test-db`")


# **`clean_invocations` in `conftest.py` is the fixture**: every foreign key in its block is
# `RESTRICT`, so the whole set is truncated in one statement or none of it is.


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
    """A well-formed `Understanding` (`goal.v8`, #307), so each test overrides only what it is
    about."""
    body = {
        "wants": [{"type": "counts.matrix", "quote": "gene counts"}],
        "questions": [],
    }
    body.update(overrides)
    return json.dumps(body)


def _rows() -> list[AiInvocation]:
    with session_scope() as session:
        return list(session.scalars(select(AiInvocation)).all())


# ── the goal call ─────────────────────────────────────────────────────────────────────────


def test_a_paired_rnaseq_request_comes_back_as_a_typed_want(stack, clean_invocations):
    """The flagship case under v3: prose in, what they want out, and nothing about what they
    have. The engine works that out and asks (14.7.3)."""
    client = _client(
        _goal_answer(
            requires=[{"type": "counts.matrix", "states": ["gene_level"], "quote": "gene counts"}],
            facts=[{"subject": "paired", "value": True, "quote": "paired"}],
        )
    )
    request = ai.compose(prompt="I have 12 paired RNA-seq samples and want gene counts")
    outcome = ai.understand(request, stack=stack, client=client)

    assert outcome.admitted, outcome.refusal
    assert [w.type for w in outcome.reply.wants] == ["counts.matrix"]
    assert outcome.reply.requires[0].states == ["gene_level"]
    assert outcome.reply.facts[0].quote == "paired"


def test_an_ambiguous_want_comes_back_as_a_question(stack, clean_invocations):
    """A question only when the want itself is unclear. What they have is the engine's to ask."""
    client = _client(
        _goal_answer(
            questions=[
                {
                    "asks": "counts per gene, or per transcript?",
                    "why_open": "the two are different outputs and the request names neither",
                    "choices": ["per gene", "per transcript"],
                    "exhaustive": False,
                }
            ]
        )
    )
    outcome = ai.understand(ai.compose(prompt="count my reads"), stack=stack, client=client)

    assert outcome.admitted, outcome.refusal
    assert len(outcome.reply.questions) == 1


def test_a_want_naming_a_type_the_registry_does_not_declare_is_refused(stack, clean_invocations):
    """`MI0204`, and the reason it refuses rather than trims.

    `rnaseq.counts` is not a declared type. It reads perfectly, validates as a string, and
    routes to nothing — dropping it silently would leave a goal quietly missing the thing
    somebody asked for.
    """
    client = _client(_goal_answer(wants=[{"type": "rnaseq.counts"}]))
    outcome = ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0204"
    assert "rnaseq.counts" in outcome.refusal


def test_a_constraint_naming_a_state_that_type_does_not_declare_is_refused(
    stack, clean_invocations
):
    """The same code on the other axis: `counts.matrix` is real and `polished` is not one of
    its states."""
    client = _client(_goal_answer(requires=[{"type": "counts.matrix", "states": ["polished"]}]))
    outcome = ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)

    assert not outcome.admitted
    assert outcome.code == "MI0204"
    assert "polished" in outcome.refusal


def test_a_fact_the_registry_refuses_refuses_the_reply(stack, clean_invocations):
    """#307 (spec §9): an undeclared id, or a value its measurement refuses, is refused at
    admission and nothing is recorded — where #170 dropped a bad stated candidate. A change is
    recorded or offered as it stands, so one the registry cannot hold has nowhere to go."""
    client = _client(_goal_answer(facts=[{"subject": "read_length", "value": -5}]))
    outcome = ai.understand(ai.compose(prompt="150 bp"), stack=stack, client=client)
    assert not outcome.admitted
    assert outcome.code == "MI0204"


# ── the chat call ─────────────────────────────────────────────────────────────────────────


DRAFT = ai.compose(
    prompt="why STAR?",
    steps=[("align", "nf-core/star/align@1.11.0"), ("sort", "nf-core/samtools/sort@1.21.0")],
    options=["opt_hisat2", "opt_keep_star"],
)


def test_an_explanation_comes_back_as_something_to_say(clean_invocations):
    """#307: an explanation is `say`; it changes nothing."""
    client = _client(json.dumps({"say": "STAR is here because your reads are 150 bp long"}))
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert outcome.reply.say.startswith("STAR is here")
    assert not outcome.reply.facts and not outcome.reply.pins


def test_a_correction_in_words_comes_back_as_a_fact_quoting_them(clean_invocations):
    """*actually it is single-end* is a change to a fact, quoting them — no longer a revision
    re-read from the top (#307)."""
    client = _client(
        json.dumps({"facts": [{"subject": "paired", "value": False, "quote": "single-end"}]})
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert outcome.reply.facts[0].value is False


def test_a_tool_the_registry_does_not_declare_is_refused(clean_invocations):
    """**The product claim, as a test.** A model cannot produce a value outside the candidate
    set: a pin names a declared tool or it is set aside, and never reaches what is recorded.
    Since #326 the rest of the reply stands; the row keeps the code, so it is still counted."""
    client = _client(
        json.dumps({"pins": [{"type": "alignment.bam", "tool": "nf-core/salmon/quant@1.0.0"}]})
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.reply.pins == []
    assert outcome.code == "MI0204"
    assert "salmon" in outcome.refusal
    assert (_rows()[0].state, _rows()[0].failure_code) == ("succeeded", "MI0204")


def test_a_setting_no_step_declares_is_refused(clean_invocations):
    client = _client(json.dumps({"parameters": [{"name": "libtype", "value": "A"}]}))
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.reply.parameters == []
    assert outcome.code == "MI0204"


def test_saying_what_cannot_be_done_is_an_admitted_answer_and_not_a_refusal(clean_invocations):
    """Saying *I cannot do that here* is the model working, not failing."""
    client = _client(
        json.dumps({"say": "I cannot add a tool to the registry from this conversation"})
    )
    outcome = ai.follow_up(DRAFT, client=client)

    assert outcome.admitted, outcome.refusal
    assert _rows()[0].state == "succeeded"


# ── what goes wrong ───────────────────────────────────────────────────────────────────────


def test_an_answer_that_is_not_json_is_refused_and_recorded(clean_invocations):
    """`comeni-ai` will not hand over an answer that does not validate, so this never reaches
    admission — and the row still has to exist, because a model that cannot produce the shape is
    the finding worth measuring."""
    client = _client("I think you should probably use STAR for this.")
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MA0004"
    assert _rows()[0].state == "refused"


def test_a_provider_failure_is_recorded_as_failed_and_never_as_refused(clean_invocations):
    """The distinction `InvocationState` was split for: this one is retried, a refusal is a
    prompt or a model that cannot do the job. Folding them makes the second invisible."""
    client = _client(ModelUnavailableError("MA0007: fake/test: connection refused"))
    outcome = ai.follow_up(DRAFT, client=client)

    assert not outcome.admitted
    assert outcome.code == "MA0007"
    assert _rows()[0].state == "failed"


def test_a_provider_failure_records_a_code_and_never_the_providers_words(clean_invocations):
    """`failure_code` holds a declared code. A provider's own text carries an endpoint and
    sometimes a key prefix, and this column is rendered on a page."""
    client = _client(ModelUnavailableError("MA0002: the provider refused the credentials"))
    ai.follow_up(DRAFT, client=client)

    row = _rows()[0]
    assert row.failure_code == "MA0002"
    assert "credentials" not in row.failure_code


def test_no_configured_model_refuses_before_anything_is_recorded(monkeypatch, clean_invocations):
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


def test_the_tail_the_model_is_shown_is_bounded(clean_invocations):
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


def test_the_prompt_that_was_sent_carries_the_steps_and_the_option_ids(clean_invocations):
    """What the model is shown and what it is held to are one list.

    If the options were rendered as labels, a reply naming a label would be refused by a check
    the model was never given the means to satisfy.
    """
    client = _client(json.dumps({"say": "Noted."}))
    ai.follow_up(DRAFT, client=client)

    sent = client.last_prompt  # both parts of the split, as one string (#183)
    assert "opt_hisat2" in sent
    assert "align — nf-core/star/align@1.11.0" in sent


def test_the_recorded_row_names_the_builder_and_what_actually_crossed_the_wire(
    stack, clean_invocations
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
    assert row.prompt_id == "builder.goal.v9"
    assert row.prompt_version == "v9"
    assert row.provider == "local"
    assert row.state == "succeeded"
    assert row.failure_code == ""
    assert row.prompt_digest == hashlib.sha256(client.last_prompt.encode()).hexdigest()


def test_the_row_says_which_reply_format_the_call_used(stack, clean_invocations):
    """#194: a reader of a refusal needs to know whether the server enforced the shape."""

    class Enforcing(Answers):
        enforces_formats = True

        def send(self, access, prompt, response_format=None):
            return super().send(access, prompt)

    local = ModelAccess(model="ollama_chat/fake", base_url="http://localhost:1")
    ai.understand(
        ai.compose(prompt="count genes"),
        stack=stack,
        client=Client(local, transport=Enforcing(_goal_answer())),
    )
    ai.understand(ai.compose(prompt="count genes"), stack=stack, client=_client(_goal_answer()))
    assert sorted(row.reply_format for row in _rows()) == ["in_prompt", "ollama"]


def test_the_two_calls_are_told_apart_by_purpose_under_one_agent(stack, clean_invocations):
    """One member per committed prompt id, scoped by `agent` rather than spelled to be globally
    unique — the Forge declares a `chat` purpose too, and that column is what separates them."""
    ai.understand(ai.compose(prompt="count genes"), stack=stack, client=_client(_goal_answer()))
    ai.follow_up(DRAFT, client=_client(json.dumps({"say": "Noted."})))

    assert {row.purpose for row in _rows()} == {"goal", "chat"}
    assert {row.agent for row in _rows()} == {"builder"}


# ── what a call row keeps (14.7.4, #182 #191) ─────────────────────────────────────────────


def _session() -> str:
    """A session that exists: a reply for one that does not is stored cleared (Part H), which
    is what a draft deleted mid-call looks like."""
    from comeni_core.plan.draft import DraftGraph
    from mendel_api.services import drafts
    from mendel_api.services import session as facade
    from mendel_authoring import commands

    return facade.perform(
        commands.OpenSession(drafts.create(DraftGraph(), "t", "ana"), "ana")
    ).result


def test_a_call_stores_its_reply_and_its_session(stack, clean_invocations):
    sid = _session()
    ai.understand(
        ai.compose(prompt="count genes"),
        stack=stack,
        client=_client(_goal_answer()),
        session_id=sid,
    )
    row = _rows()[0]
    assert row.response == _goal_answer()
    assert row.session_id == sid


def test_a_refused_call_keeps_the_reply_that_was_refused(stack, clean_invocations):
    ai.understand(
        ai.compose(prompt="count genes"),
        stack=stack,
        client=_client(_goal_answer(want=["rnaseq.counts"])),
        session_id=_session(),
    )
    row = _rows()[0]
    assert row.state == "refused" and "rnaseq.counts" in row.response


def test_the_session_never_enters_the_door_payload():
    """Door 1's payload is typed and counted; a session id is not something a model is sent."""
    assert "session_id" not in ai.AuthoringRequest.model_fields


def test_a_builder_call_sends_the_split_and_digests_what_it_sent(stack, clean_invocations):
    """#183: the fixed part as a system message, the per-call part after it."""
    seen: list = []

    class Records:
        def send(self, access, prompt):
            seen.append(prompt)
            return _goal_answer()

    client = Client(ACCESS, transport=Records())
    ai.understand(ai.compose(prompt="count genes"), stack=stack, client=client)
    [messages] = seen
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "count genes" in messages[1]["content"]
    assert "count genes" not in str(messages[0]["content"])
    assert _rows()[0].prompt_digest == hashlib.sha256(client.last_prompt.encode()).hexdigest()


def test_a_phrasing_keeps_its_words_and_drops_an_already_nobody_offered(stack, clean_invocations):
    """#167: `already` is held like `chose`, but a bad one is dropped, not refused."""
    gap = {
        "subject": "paired",
        "kind": "measurement",
        "asks": "Whether paired?",
        "description": "paired-end",
        "options": {"yes": "Yes", "no": "No"},
        "facts": "",
    }
    request = ai.compose(prompt="paired-end reads", options=["yes", "no"])
    outcome = ai.phrase_gap(
        request,
        gap=gap,
        stack=stack,
        session_id="s" * 32,
        client=_client(
            json.dumps({"asks": "Were both ends sequenced?", "already_option": "maybe"})
        ),
    )
    assert outcome.admitted and outcome.reply.asks == "Were both ends sequenced?"
    assert outcome.reply.already_option is None
    assert _rows()[0].purpose == "ask"


def test_the_read_back_call_is_given_the_goal_after_the_divider(stack, clean_invocations):
    seen: list = []

    class Records:
        def send(self, access, prompt):
            seen.append(prompt)
            return json.dumps({"text": "Gene counts from your paired reads."})

    outcome = ai.read_back(
        ai.compose(prompt="paired-end RNA-seq"),
        goal="have: fastq.reads (you said)",
        client=Client(ACCESS, transport=Records()),
        session_id="s" * 32,
    )
    assert outcome.admitted and outcome.reply.text.startswith("Gene counts")
    assert "fastq.reads (you said)" in seen[0][1]["content"]
    assert _rows()[0].purpose == "readback"


# ── allowed lists (#194) ──────────────────────────────────────────────────────────────────


class _Choosing(Client):
    """Records the allowed lists each call names, and answers with a committed body."""

    def __init__(self, body: str) -> None:
        super().__init__(ACCESS, transport=Answers(body))
        self.choices: list = []

    def chat(self, system, user, shape, choices=None):
        self.choices.append(choices)
        return super().chat(system, user, shape, choices=choices)


def test_each_call_holds_its_ids_to_what_it_was_shown(stack, clean_invocations):
    goal = _Choosing(_goal_answer())
    ai.understand(ai.compose(prompt="count genes"), stack=stack, client=goal)
    [held] = goal.choices
    assert held["wants.type"] == sorted(registry.builder_types(stack))
    measured = set(stack.measurements.measurements)
    assert set(held["facts.subject"]) == set(registry.builder_types(stack)) | measured

    gap = {
        "subject": "paired",
        "kind": "measurement",
        "asks": "Whether paired?",
        "description": "paired-end",
        "options": {"yes": "Yes", "no": "No"},
        "facts": "",
    }
    asked = _Choosing(json.dumps({"asks": "Paired?"}))
    ai.phrase_gap(ai.compose(prompt="p", options=["yes", "no"]), gap=gap, stack=stack, client=asked)
    # `ask.v2` is words only (#307): nothing it writes is held to a list.
    assert asked.choices == [None]


def test_prose_only_calls_name_no_list(clean_invocations):
    reader = _Choosing(json.dumps({"text": "You will get a counts matrix."}))
    ai.read_back(ai.compose(prompt="p"), goal="want: counts.matrix", client=reader)
    assert reader.choices == [None]


def test_an_empty_list_is_not_sent_as_an_enum_of_nothing():
    """An id list with nothing in it constrains nothing: `with_choices` leaves the field
    unconstrained rather than making it an enum of nothing (#244)."""
    from comeni_ai.formats import with_choices
    from mendel_api.authoring.types import ChatReply

    assert "enum" not in str(with_choices(ChatReply.model_json_schema(), {"pins.tool": []}))


# ── choosing the type by family (#194) ────────────────────────────────────────────────────


def test_the_verdict_comes_before_any_family():
    """#202: judged first, so declining is a value the model picks, not a list it skips."""
    from mendel_api.authoring.types import FamilyChoice

    assert next(iter(FamilyChoice.model_json_schema()["properties"])) == "fits"
    assert "fits" in FamilyChoice.model_json_schema()["required"]


def test_the_family_call_holds_its_answer_to_the_declared_families(stack, clean_invocations):
    chooser = _Choosing(
        json.dumps({"fits": "yes", "families": ["counts"], "ack": "Gene counts — got it."})
    )
    outcome = ai.choose_families(ai.compose(prompt="gene counts"), stack=stack, client=chooser)
    assert outcome.admitted and outcome.reply.families == ["counts"]
    assert chooser.choices == [{"families": sorted(stack.families.families)}]
    assert _rows()[0].purpose == "family" and _rows()[0].prompt_id == "builder.family.v4"


def test_a_family_nothing_declares_is_refused(stack, clean_invocations):
    outcome = ai.choose_families(
        ai.compose(prompt="variant calls"),
        stack=stack,
        client=_client(
            json.dumps({"fits": "yes", "families": ["variants"], "ack": "Variants — got it."})
        ),
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_the_goal_call_is_shown_only_the_chosen_families_whole(stack, clean_invocations):
    goal = _Choosing(_goal_answer())
    ai.understand(ai.compose(prompt="gene counts"), stack=stack, families=["counts"], client=goal)
    counts = sorted(t for t in stack.vocabulary.types if t.startswith("counts."))
    assert goal.choices[0]["wants.type"] == counts
    assert "fastq.reads" not in goal.last_prompt and "counts.matrix" in goal.last_prompt
    assert _rows()[0].prompt_id == "builder.goal.v9"


def test_with_the_family_step_off_the_goal_call_sees_every_type_and_acknowledges(
    stack, clean_invocations
):
    goal = _Choosing(_goal_answer())
    ai.understand(ai.compose(prompt="gene counts"), stack=stack, families=None, client=goal)
    assert goal.choices[0]["wants.type"] == sorted(registry.builder_types(stack))
    assert _rows()[0].prompt_id == "builder.goal.v9"
    assert "Acknowledge them in `say`" in goal.last_prompt


# ── what the chat call is shown (issue 324) ───────────────────────────────────────────────


def _chat_call(monkeypatch, stack, **kwargs) -> dict:
    seen: dict = {}
    monkeypatch.setattr(ai, "_call", lambda request, **kw: seen.update(kw))
    ai.follow_up(DRAFT, stack=stack, **kwargs)
    return seen


def test_the_chat_call_is_shown_every_measurement_with_what_it_holds(monkeypatch, stack):
    """From the walk: never shown a measurement id, the model answered *"so 100 bp"* with an
    invented setting, `sequenced_read_length`. It is shown what the goal call is shown."""
    values = _chat_call(monkeypatch, stack)["values"]
    assert "read_length (integer bp) — Sequenced read length" in values["vocabulary"]
    assert "(nothing is waiting for an answer)" in values["open"]


def test_the_chat_call_is_told_which_measurement_the_open_question_asks(monkeypatch, stack):
    values = _chat_call(monkeypatch, stack, open_question="read_length")["values"]
    assert '"subject": "read_length"' in values["open"]


def test_a_setting_name_is_held_to_the_declared_ones(monkeypatch, stack):
    names = _chat_call(monkeypatch, stack)["choices"]["parameters.name"]
    declared = {p.name for c in stack.registry.all() for p in c.params}
    assert names and set(names) == declared


def test_the_prompt_lists_a_measurement_as_a_measurement_and_never_as_a_type(stack):
    """The walk's model required the type `measurement.read_length` for *read length is 50*."""
    assert any(t.startswith("measurement.") for t in stack.vocabulary.types)
    text = ai._vocabulary_text(stack)
    types, measurements = text.split("Measurements (", 1)
    assert "measurement." not in types
    assert "  read_length (" in measurements
