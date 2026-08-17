"""Closed choice, over `generate`.

The value a model returns must be one it was offered. That is the half of model output that
can be checked mechanically, and it is why the forge attempts candidate-bearing holes only.
"""

import json

from mendel_ai.access import ModelAccess
from mendel_ai.choice import WHY_LIMIT, Choice, Choices, Option, choose_many, choose_one
from mendel_ai.client import Client

ACCESS = ModelAccess(model="test/model")
OPTIONS = [Option(value="qc_per_sample", note="declared role"), Option(value="aligner")]


class Fixed:
    def __init__(self, body: str) -> None:
        self.body = body
        self.prompts: list[str] = []

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.body


def _client(body: str) -> Client:
    return Client(ACCESS, transport=Fixed(body))


def test_choose_one_returns_the_picked_value() -> None:
    client = _client('{"value": "qc_per_sample", "why": "it QCs one sample"}')
    assert choose_one(client, "which role?", OPTIONS, []) == Choice(
        value="qc_per_sample", why="it QCs one sample"
    )


def test_a_value_outside_the_options_is_refused() -> None:
    client = _client('{"value": "invented_role", "why": "seemed right"}')
    assert choose_one(client, "which role?", OPTIONS, []) is None
    assert "MA0005" in (client.last_refusal or "")


def test_choose_many_returns_several() -> None:
    client = _client('{"values": ["qc_per_sample", "aligner"], "why": "both apply"}')
    assert choose_many(client, "which roles?", OPTIONS, []) == Choices(
        values=["qc_per_sample", "aligner"], why="both apply"
    )


def test_choose_many_refuses_if_any_member_was_not_offered() -> None:
    """Member by member, the same rule `Hole.legal` applies for the same reason."""
    client = _client('{"values": ["qc_per_sample", "invented"], "why": "w"}')
    assert choose_many(client, "which roles?", OPTIONS, []) is None
    assert "MA0005" in (client.last_refusal or "")


def test_choose_many_accepts_an_empty_answer() -> None:
    """'None of these' is a real answer to a closed choice, and it is not a refusal."""
    client = _client('{"values": [], "why": "none of these describe it"}')
    assert choose_many(client, "which roles?", OPTIONS, []) == Choices(
        values=[], why="none of these describe it"
    )


def test_the_options_and_their_notes_reach_the_prompt() -> None:
    transport = Fixed('{"value": "qc_per_sample", "why": "w"}')
    choose_one(Client(ACCESS, transport=transport), "which role?", OPTIONS, [])
    assert "qc_per_sample" in transport.prompts[0]
    assert "declared role" in transport.prompts[0]


def test_a_declined_generate_stays_declined() -> None:
    assert choose_one(_client("not json at all"), "which role?", OPTIONS, []) is None


def test_an_overlong_rationale_is_refused_whole() -> None:
    """Refused rather than truncated: a shortened rationale is half a sentence a reviewer
    reads without knowing it was shortened."""
    body = json.dumps({"value": "qc_per_sample", "why": "x" * (WHY_LIMIT + 1)})
    client = _client(body)
    assert choose_one(client, "which role?", OPTIONS, []) is None
    assert "MA0006" in (client.last_refusal or "")


def test_a_rationale_at_the_limit_is_accepted() -> None:
    """An off-by-one here silently costs every long-but-legal answer."""
    body = json.dumps({"value": "qc_per_sample", "why": "x" * WHY_LIMIT})
    assert choose_one(_client(body), "which role?", OPTIONS, []) is not None


def test_choose_many_caps_its_rationale_too() -> None:
    """Two shapes, one limit. A cap on one of them is a cap somebody routes around."""
    body = json.dumps({"values": ["qc_per_sample"], "why": "x" * (WHY_LIMIT + 1)})
    client = _client(body)
    assert choose_many(client, "which roles?", OPTIONS, []) is None
    assert "MA0006" in (client.last_refusal or "")


def test_no_options_is_none_rather_than_a_free_answer() -> None:
    """A hole with no candidates is free text, and #70 gates it. Asking anyway would be the
    one thing this design says it does not do."""
    assert choose_one(_client('{"value": "x", "why": "w"}'), "q", [], []) is None
    assert choose_many(_client('{"values": ["x"], "why": "w"}'), "q", [], []) is None


def test_no_options_does_not_reach_the_model_at_all() -> None:
    """Declining after asking would still have sent the prose. This is why it returns early."""
    transport = Fixed('{"value": "x", "why": "w"}')
    choose_one(Client(ACCESS, transport=transport), "q", [], [])
    assert transport.prompts == []
