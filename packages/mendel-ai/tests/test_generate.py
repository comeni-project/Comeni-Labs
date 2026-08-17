"""`generate` validates before it returns, and declines rather than repairs.

Every test here injects a transport. No test in this repository may call a live model —
`tests/test_no_live_model.py` is the guard that enforces it.
"""

import json

import pytest
from mendel_ai.access import ModelAccess
from mendel_ai.client import Client, NoModelError, Transport
from pydantic import BaseModel, Field

ACCESS = ModelAccess(model="test/model")


class Answer(BaseModel):
    value: str
    why: str


class Capped(BaseModel):
    value: str
    why: str = Field(max_length=500)


class Fixed:
    """A transport that always returns the same body."""

    def __init__(self, body: str) -> None:
        self.body = body
        self.prompts: list[str] = []

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.body


def test_a_well_shaped_answer_is_returned() -> None:
    client = Client(ACCESS, transport=Fixed('{"value": "qc", "why": "it QCs"}'))
    assert client.generate("pick one", Answer, ["evidence"]) == Answer(value="qc", why="it QCs")


def test_an_answer_that_does_not_validate_is_declined_not_repaired() -> None:
    """A half-built value is worse than an open hole: the hole is visible."""
    client = Client(ACCESS, transport=Fixed('{"value": "qc"}'))  # no `why`
    assert client.generate("pick one", Answer, []) is None


def test_a_non_json_answer_is_declined() -> None:
    client = Client(ACCESS, transport=Fixed("I think it should be qc, probably."))
    assert client.generate("pick one", Answer, []) is None


def test_json_inside_a_fenced_block_is_accepted() -> None:
    """Models fence JSON constantly. Refusing that is refusing a right answer for its wrapper."""
    client = Client(ACCESS, transport=Fixed('```json\n{"value": "qc", "why": "w"}\n```'))
    assert client.generate("pick one", Answer, []) == Answer(value="qc", why="w")


def test_the_evidence_reaches_the_prompt() -> None:
    transport = Fixed('{"value": "qc", "why": "w"}')
    Client(ACCESS, transport=transport).generate("pick one", Answer, ["FASTQC in main.nf:3"])
    assert "FASTQC in main.nf:3" in transport.prompts[0]


def test_the_shape_reaches_the_prompt() -> None:
    """A model asked for a shape it was never shown cannot produce it."""
    transport = Fixed('{"value": "qc", "why": "w"}')
    Client(ACCESS, transport=transport).generate("pick one", Answer, [])
    assert "why" in transport.prompts[0] and "value" in transport.prompts[0]


def test_no_model_configured_raises_a_coded_refusal() -> None:
    with pytest.raises(NoModelError) as raised:
        Client.for_env({})
    assert "MA0001" in str(raised.value)


def test_a_configured_env_builds_a_client() -> None:
    assert isinstance(Client.for_env({"MENDEL_MODEL": "test/model"}), Client)


def test_transport_is_a_protocol_anything_can_satisfy() -> None:
    """The seam recorded fixtures plug into, and the reason no test needs a network."""
    assert isinstance(Fixed("{}"), Transport)


def test_a_shape_mismatch_is_reported_with_its_code() -> None:
    client = Client(ACCESS, transport=Fixed('{"value": "qc"}'))
    assert client.generate("pick one", Answer, []) is None
    assert "MA0004" in (client.last_refusal or "")


def test_an_overlong_field_is_refused_with_its_own_code() -> None:
    """Not MA0004. The one shape violation with an obvious cause says so."""
    body = json.dumps({"value": "qc", "why": "x" * 5000})
    client = Client(ACCESS, transport=Fixed(body))
    assert client.generate("pick one", Capped, []) is None
    assert "MA0006" in (client.last_refusal or "")
    assert "MA0004" not in (client.last_refusal or "")


def test_the_overlong_refusal_names_the_field() -> None:
    """A code alone does not tell a reader which field overran."""
    body = json.dumps({"value": "qc", "why": "x" * 5000})
    client = Client(ACCESS, transport=Fixed(body))
    client.generate("pick one", Capped, [])
    assert "why" in (client.last_refusal or "")


def test_the_declared_limit_reaches_the_prompt() -> None:
    """A model told the number can keep to it; one punished for not guessing cannot."""
    transport = Fixed('{"value": "qc", "why": "w"}')
    Client(ACCESS, transport=transport).generate("pick one", Capped, [])
    assert "500" in transport.prompts[0]


def test_a_successful_call_clears_a_previous_refusal() -> None:
    """A stale refusal read after a later success would name the wrong call."""
    client = Client(ACCESS, transport=Fixed('{"value": "qc"}'))
    client.generate("pick one", Answer, [])
    assert client.last_refusal is not None
    client._transport = Fixed('{"value": "qc", "why": "w"}')
    assert client.generate("pick one", Answer, []) is not None
    assert client.last_refusal is None


def test_a_timeout_is_declined_rather_than_raised() -> None:
    """A hole nobody answered is a hole a person still sees — MA0003 does not refuse."""

    class TimesOut:
        def send(self, access: ModelAccess, prompt: str) -> str:
            raise TimeoutError("MA0003: too slow")

    client = Client(ACCESS, transport=TimesOut())
    assert client.generate("pick one", Answer, []) is None
    assert "MA0003" in (client.last_refusal or "")
