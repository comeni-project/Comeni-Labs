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
    body = {"type_id": "alignment.bam", "states": ["coordinate_sorted"], "measurements": [],
            "undetermined": [], "unmatched": []}
    return json.dumps(body | over)


# ── call 1: the families ──────────────────────────────────────────────────────────────


def test_the_family_call_is_held_to_the_declared_families(stack, clean_forge):
    client = Choosing(json.dumps({"families": ["alignment"]}))
    outcome = ai.characterise_families(_request(), stack=stack, client=client)
    assert outcome.admitted and outcome.reply.families == ["alignment"]
    assert client.choices == [{"families": sorted(stack.families.families)}]
    [row] = _rows()
    assert row.purpose == "characterise_family"
    assert row.prompt_id == "builder.characterise-family.v1"


def test_no_family_is_an_answer_meaning_the_ai_could_not_tell(stack, clean_forge):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(json.dumps({"families": []}))
    )
    assert outcome.admitted and outcome.reply.families == []


def test_a_family_nothing_declares_is_refused(stack, clean_forge):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(json.dumps({"families": ["variants"]}))
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_the_excerpt_reaches_the_model_and_the_name_never_does(stack, clean_forge):
    client = Choosing(json.dumps({"families": ["alignment"]}))
    ai.characterise_families(_request(), stack=stack, client=client)
    sent = _text(client.answers.sent[0])
    assert "SO:coordinate" in sent
    assert "binary bytes came before this text" in sent


# ── call 2: the type, its states, its facts ─────────────────────────────────────────


def test_the_type_call_is_shown_only_the_chosen_families_types(stack, clean_forge):
    client = Choosing(_reply())
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"], client=client)
    assert outcome.admitted and outcome.reply.type_id == "alignment.bam"
    assert outcome.reply.states == ["coordinate_sorted"]
    shown = sorted(t for t in stack.vocabulary.types if t.startswith("alignment."))
    assert client.choices[0]["type_id"] == shown
    sent = _text(client.answers.sent[0])
    assert "alignment.bam" in sent and "fastq.reads" not in sent
    assert _rows()[0].prompt_id == "builder.characterise.v1"


def test_with_the_family_step_off_every_type_is_shown(stack, clean_forge):
    client = Choosing(_reply())
    ai.characterise(_request(), stack=stack, families=None, client=client)
    assert client.choices[0]["type_id"] == sorted(stack.vocabulary.types)


def test_a_type_outside_the_chosen_families_is_refused(stack, clean_forge):
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(type_id="genome.fasta", states=[])),
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_a_state_of_another_type_is_refused(stack, clean_forge):
    outcome = ai.characterise(
        _request(">chr1\nACGT\n", binary_before=False), stack=stack, families=["genome"],
        client=Choosing(_reply(type_id="genome.fasta", states=["coordinate_sorted"])),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_measurement_the_type_does_not_offer_is_refused(stack, clean_forge):
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(measurements=[{"id": "library_prep", "value": "poly_a"}])),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_value_outside_its_declaration_is_dropped_and_the_rest_admitted(stack, clean_forge):
    # `paired` and `quality_encoding` declare `describes: fastq.reads`; `read_length` does not,
    # so a model is never offered it (spec §2's rule A, as the registry stands).
    assert {"paired", "quality_encoding"} <= ai.offered(stack, "fastq.reads")[1]
    reply = _reply(type_id="fastq.reads", states=[],
                   measurements=[{"id": "quality_encoding", "value": "phred99"},
                                 {"id": "paired", "value": True}])
    outcome = ai.characterise(
        _request("@r1\nACGT\n+\nIIII\n", binary_before=False), stack=stack,
        families=["fastq"], client=Choosing(reply),
    )
    assert outcome.admitted
    assert [m.id for m in outcome.reply.measurements] == ["paired"]


def test_no_type_is_an_answer_meaning_the_ai_could_not_tell(stack, clean_forge):
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(type_id=None, states=[])),
    )
    assert outcome.admitted and outcome.reply.type_id is None


def test_unmatched_is_kept_in_the_reply_and_never_admitted_into_anything(stack, clean_forge):
    unmatched = [{"kind": "state", "name": "unsorted", "cite": "SAM v1.6 §1.3"}]
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(unmatched=unmatched)),
    )
    assert outcome.admitted and outcome.reply.unmatched[0].name == "unsorted"
    assert "unsorted" in (_rows()[0].response or "")


def test_a_provider_that_does_not_answer_is_recorded_as_failed(stack, clean_forge):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(ModelUnavailableError("down"))
    )
    assert not outcome.admitted and outcome.code == "MA0007"
    assert _rows()[0].state == "failed"


def test_states_and_measurements_offered_come_from_the_registry(stack):
    states, measurements = ai.offered(stack, "alignment.bam")
    assert "coordinate_sorted" in states
    assert all(stack.measurements.get(m).describes == "alignment.bam" for m in measurements)
