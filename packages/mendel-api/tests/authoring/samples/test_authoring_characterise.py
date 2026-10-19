"""The characteriser's two calls (14.7.7), against a fake transport and a real database.

Same seam as `test_authoring_ai.py`: `Client` takes a transport, and each test hands one a
committed body. What is under test is what comes back in: which ids are admitted, which refused,
and what is recorded.
"""

import json

import pytest
from comeni_ai import Client, ModelAccess, ModelUnavailableError
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation
from mendel_api.services import authoring_ai as ai
from mendel_api.services import registry
from sqlalchemy import select

ACCESS = ModelAccess(model="fake/test", base_url="http://localhost:1")
BAM_HEAD = "@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chr1\tLN:248956422\n"


class Answers:
    def __init__(self, *bodies):
        self.bodies, self.sent = list(bodies), []

    def send(self, access, prompt):
        self.sent.append(prompt)
        body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        if isinstance(body, Exception):
            raise body
        return body


class Choosing(Client):
    def __init__(self, *bodies):
        self.answers = Answers(*bodies)
        super().__init__(ACCESS, transport=self.answers)
        self.choices = []

    def chat(self, system, user, shape, choices=None):
        self.choices.append(choices)
        return super().chat(system, user, shape, choices=choices)


@pytest.fixture
def stack():
    return registry.stack()


def _text(sent) -> str:
    """What reached the transport: a prompt string, or the chat messages' contents."""
    return sent if isinstance(sent, str) else "\n".join(m["content"] for m in sent)


def _rows():
    with session_scope() as db:
        return list(db.scalars(select(AiInvocation)).all())


def _request(text=BAM_HEAD, binary_before=True):
    return ai.compose_characterise(text, binary_before=binary_before, registry="sha256:" + "0" * 64)


def _reply(**over):
    """A v2 reply. A state given as a bare id quotes `SO:coordinate`, which `BAM_HEAD` holds."""
    body = {
        "type_id": "alignment.bam",
        "states": ["coordinate_sorted"],
        "measurements": [],
        "undetermined": [],
        "unmatched": [],
    } | over
    body["states"] = [
        s if isinstance(s, dict) else {"id": s, "evidence": "SO:coordinate"} for s in body["states"]
    ]
    return json.dumps(body)


# ── call 1: the families ──────────────────────────────────────────────────────────────


def test_the_family_call_is_held_to_the_declared_families(stack, clean_invocations):
    client = Choosing(json.dumps({"families": ["alignment"]}))
    outcome = ai.characterise_families(_request(), stack=stack, client=client)
    assert outcome.admitted and outcome.reply.families == ["alignment"]
    assert client.choices == [{"families": sorted(stack.families.families)}]
    [row] = _rows()
    assert row.purpose == "characterise_family"
    assert row.prompt_id == "builder.characterise-family.v1"


def test_no_family_is_an_answer_meaning_the_ai_could_not_tell(stack, clean_invocations):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(json.dumps({"families": []}))
    )
    assert outcome.admitted and outcome.reply.families == []


def test_a_family_nothing_declares_is_refused(stack, clean_invocations):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(json.dumps({"families": ["variants"]}))
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_the_excerpt_and_whether_binary_came_first_reach_the_model(stack, clean_invocations):
    client = Choosing(json.dumps({"families": ["alignment"]}))
    ai.characterise_families(_request(), stack=stack, client=client)
    sent = _text(client.answers.sent[0])
    assert "SO:coordinate" in sent
    assert "binary bytes came before this text" in sent


# ── call 2: the type, its states, its facts ─────────────────────────────────────────


def test_the_type_call_is_shown_only_the_chosen_families_types(stack, clean_invocations):
    client = Choosing(_reply())
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"], client=client)
    assert outcome.admitted and outcome.reply.type_id == "alignment.bam"
    assert [s.id for s in outcome.reply.states] == ["coordinate_sorted"]
    shown = sorted(t for t in stack.vocabulary.types if t.startswith("alignment."))
    assert client.choices[0]["type_id"] == shown
    sent = _text(client.answers.sent[0])
    assert "alignment.bam" in sent and "fastq.reads" not in sent
    assert _rows()[0].prompt_id == "builder.characterise.v2"


def test_with_the_family_step_off_every_type_is_shown(stack, clean_invocations):
    client = Choosing(_reply())
    ai.characterise(_request(), stack=stack, families=None, client=client)
    assert client.choices[0]["type_id"] == sorted(registry.builder_types(stack))


def test_a_type_outside_the_chosen_families_is_refused(stack, clean_invocations):
    outcome = ai.characterise(
        _request(),
        stack=stack,
        families=["alignment"],
        client=Choosing(_reply(type_id="genome.fasta", states=[])),
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_a_state_of_another_type_is_refused(stack, clean_invocations):
    outcome = ai.characterise(
        _request(">chr1\nACGT\n", binary_before=False),
        stack=stack,
        families=["genome"],
        client=Choosing(_reply(type_id="genome.fasta", states=["coordinate_sorted"])),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_measurement_the_type_does_not_offer_is_refused(stack, clean_invocations):
    outcome = ai.characterise(
        _request(),
        stack=stack,
        families=["alignment"],
        client=Choosing(_reply(measurements=[{"id": "library_prep", "value": "poly_a"}])),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_value_outside_its_declaration_is_dropped_and_the_rest_admitted(stack, clean_invocations):
    # `paired` and `quality_encoding` declare `describes: fastq.reads`; `read_length` does not,
    # so a model is never offered it (spec §2's rule A, as the registry stands).
    assert {"paired", "quality_encoding"} <= ai.offered(stack, "fastq.reads")[1]
    reply = _reply(
        type_id="fastq.reads",
        states=[],
        measurements=[
            {"id": "quality_encoding", "value": "phred99", "evidence": "@r1 pair 1/1"},
            {"id": "paired", "value": True, "evidence": "@r1 pair 1/1"},
        ],
    )
    outcome = ai.characterise(
        _request("@r1 pair 1/1\nACGT\n+\nIIII\n", binary_before=False),
        stack=stack,
        families=["fastq"],
        client=Choosing(reply),
    )
    assert outcome.admitted
    assert [m.id for m in outcome.reply.measurements] == ["paired"]


def test_no_type_is_an_answer_meaning_the_ai_could_not_tell(stack, clean_invocations):
    outcome = ai.characterise(
        _request(),
        stack=stack,
        families=["alignment"],
        client=Choosing(_reply(type_id=None, states=[])),
    )
    assert outcome.admitted and outcome.reply.type_id is None


def test_unmatched_is_kept_in_the_reply_and_never_admitted_into_anything(stack, clean_invocations):
    unmatched = [{"kind": "state", "name": "unsorted", "cite": "SAM v1.6 §1.3"}]
    outcome = ai.characterise(
        _request(),
        stack=stack,
        families=["alignment"],
        client=Choosing(_reply(unmatched=unmatched)),
    )
    assert outcome.admitted and outcome.reply.unmatched[0].name == "unsorted"
    assert "unsorted" in (_rows()[0].response or "")


def test_a_provider_that_does_not_answer_is_recorded_as_failed(stack, clean_invocations):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(ModelUnavailableError("down"))
    )
    assert not outcome.admitted and outcome.code == "MA0007"
    assert _rows()[0].state == "failed"


def test_states_and_measurements_offered_come_from_the_registry(stack):
    states, _ = ai.offered(stack, "alignment.bam")
    assert "coordinate_sorted" in states
    _, measurements = ai.offered(stack, "fastq.reads")
    assert measurements, "a loop over nothing asserts nothing"
    assert all(stack.measurements.get(m).describes == "fastq.reads" for m in measurements)


# ── each list against its own set (issue 237) ─────────────────────────────────────────


def _fastq(**over):
    return ai.characterise(
        _request("@r1\nACGT\n+\nIIII\n", binary_before=False),
        stack=registry.stack(),
        families=["fastq"],
        client=Choosing(_reply(**({"type_id": "fastq.reads", "states": []} | over))),
    )


def test_a_measurement_id_named_as_a_state_is_refused(clean_invocations):
    outcome = _fastq(states=["paired"])
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_state_named_as_a_measurement_is_refused(clean_invocations):
    reply = _reply(measurements=[{"id": "coordinate_sorted", "value": True}])
    outcome = ai.characterise(
        _request(), stack=registry.stack(), families=["alignment"], client=Choosing(reply)
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_measurement_read_twice_is_refused(clean_invocations):
    outcome = _fastq(
        measurements=[{"id": "paired", "value": True}, {"id": "paired", "value": False}]
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_measurement_read_is_not_also_undetermined(clean_invocations):
    outcome = _fastq(
        measurements=[{"id": "paired", "value": True}], undetermined=["paired", "quality_encoding"]
    )
    assert outcome.admitted and outcome.reply.undetermined == ["quality_encoding"]


def test_states_and_measurement_ids_are_held_to_what_was_offered(stack, clean_invocations):
    """Issue 243: walked live, a model wrote free-text states and states into `undetermined`.
    Every id list is held at the server to the offered ids of the types shown, as `type_id` is."""
    client = Choosing(_reply())
    ai.characterise(_request(), stack=stack, families=["alignment", "fastq"], client=client)
    [held] = client.choices
    shown = stack.families.types_of(["alignment", "fastq"], stack.vocabulary.types)
    states = sorted({s for t in shown for s in ai.offered(stack, t)[0]})
    measured = sorted({m for t in shown for m in ai.offered(stack, t)[1]})
    assert states and measured, "a loop over nothing asserts nothing"
    assert held["states.id"] == states
    assert held["undetermined"] == measured
    assert held["measurements.id"] == measured


# ── evidence, checked against the excerpt (#244) ──────────────────────────────────────


def test_a_state_proven_by_a_line_of_the_file_is_admitted(stack, clean_invocations):
    reply = _reply(states=[{"id": "coordinate_sorted", "evidence": "@HD VN:1.6 SO:coordinate"}])
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"], client=Choosing(reply)
    )
    assert outcome.admitted and [s.id for s in outcome.reply.states] == ["coordinate_sorted"]


def test_a_state_whose_quote_is_not_in_the_file_is_dropped_and_the_type_stands(
    stack, clean_invocations
):
    reply = _reply(
        states=[
            {"id": "coordinate_sorted", "evidence": "SO:coordinate"},
            {"id": "deduplicated", "evidence": "@PG ID:picard MarkDuplicates"},
        ]
    )
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"], client=Choosing(reply)
    )
    assert outcome.admitted and outcome.reply.type_id == "alignment.bam"
    assert [s.id for s in outcome.reply.states] == ["coordinate_sorted"]


def test_a_quote_too_short_to_prove_anything_is_dropped(stack, clean_invocations):
    reply = _reply(states=[{"id": "coordinate_sorted", "evidence": "SO"}])
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"], client=Choosing(reply)
    )
    assert outcome.admitted and outcome.reply.states == []


def test_a_measurement_whose_quote_is_not_in_the_file_is_dropped(stack, clean_invocations):
    outcome = _fastq(measurements=[{"id": "paired", "value": True, "evidence": "R1 and R2"}])
    assert outcome.admitted and outcome.reply.measurements == []


def test_undetermined_ids_nothing_offered_are_dropped_not_refused(stack, clean_invocations):
    reply = _reply(undetermined=["deduplicated", "chromosome_length"])
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"], client=Choosing(reply)
    )
    assert outcome.admitted and outcome.reply.undetermined == []


def test_a_state_on_a_type_that_declares_none_is_still_refused(stack, clean_invocations):
    reply = _reply(
        type_id="genome.fasta", states=[{"id": "sorted by coordinate", "evidence": ">chr1"}]
    )
    outcome = ai.characterise(
        _request(">chr1 test\nACGT\n" * 20, binary_before=False),
        stack=stack,
        families=["genome"],
        client=Choosing(reply),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_nothing_offered_is_nothing_the_server_allows(stack, clean_invocations):
    client = Choosing(_reply(type_id="genome.fasta", states=[]))
    ai.characterise(
        _request(">chr1\nACGT\n" * 30, binary_before=False),
        stack=stack,
        families=["genome"],
        client=client,
    )
    assert client.choices[0]["states.id"] == []


def test_evidence_is_compared_with_whitespace_as_one_space():
    assert ai._evidenced("@HD VN:1.6  SO:coordinate", "@HD\tVN:1.6\tSO:coordinate\n")
    assert not ai._evidenced("SO:queryname", "@HD\tVN:1.6\tSO:coordinate\n")


def test_evidence_too_short_to_tell_one_file_from_another_proves_nothing():
    """Issue 246: `@HD` is in every BAM; a quote must be long enough to say something."""
    assert not ai._evidenced("@HD VN", "@HD\tVN:1.6\tSO:coordinate\n")


def test_evidence_must_fall_within_one_line():
    """Issue 246: squashed whitespace let a quote join the end of one line to the next."""
    assert not ai._evidenced("coordinate @SQ SN:chr1", "@HD\tSO:coordinate\n@SQ\tSN:chr1\n")


def test_the_schema_sent_keeps_each_state_an_object_with_its_evidence(stack, clean_invocations):
    """Issue 245: the enum goes on a state's `id`, never on the state; walked live, a schema
    saying a state is a string got strings back, and every reply failed its shape."""
    from comeni_ai.formats import with_choices
    from mendel_api.authoring.types import CharacteriseReply

    client = Choosing(_reply())
    ai.characterise(_request(), stack=stack, families=["alignment"], client=client)
    sent = with_choices(CharacteriseReply.model_json_schema(), client.choices[0])
    state = sent["$defs"]["StateRead"]
    assert "enum" not in state and "coordinate_sorted" in state["properties"]["id"]["enum"]
    assert "evidence" in state["properties"]
