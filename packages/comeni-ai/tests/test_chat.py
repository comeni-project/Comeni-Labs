"""A conversation is validated the same way a single answer is.

The one thing this must not become is the call in this package that returns free prose.
"""

from comeni_ai.access import ModelAccess
from comeni_ai.chat import Role, Turn, converse
from comeni_ai.client import Client
from pydantic import BaseModel, ConfigDict

ACCESS = ModelAccess(model="ollama/llama3")


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


class Spy:
    """Records the prompt it was handed and returns whatever it was told to."""

    def __init__(self, body: str) -> None:
        self.body = body
        self.seen: str | None = None

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.seen = prompt
        return self.body


def test_an_answer_is_validated_against_the_callers_shape() -> None:
    spy = Spy('{"answer": "because the port declares it"}')
    got = converse(Client(ACCESS, spy), [], "why?", Answer, [])
    assert got == Answer(answer="because the port declares it")


def test_an_answer_that_will_not_fit_is_declined() -> None:
    """`None`, not a repaired half-answer — the same rule `generate` holds."""
    client = Client(ACCESS, Spy('{"nonsense": 1}'))
    assert converse(client, [], "why?", Answer, []) is None
    assert client.last_refusal is not None


def test_the_history_reaches_the_prompt_oldest_first() -> None:
    spy = Spy('{"answer": "ok"}')
    history = [
        Turn(role=Role.USER, text="what type is the input?"),
        Turn(role=Role.ASSISTANT, text="alignment.bam"),
    ]
    converse(Client(ACCESS, spy), history, "and its state?", Answer, [])
    assert spy.seen is not None
    first = spy.seen.index("what type is the input?")
    second = spy.seen.index("alignment.bam")
    assert first < second, "the transcript is not oldest first"
    assert "and its state?" in spy.seen


def test_each_turn_is_labelled_with_its_role() -> None:
    """An unlabelled transcript reads as one speaker, and the model answers the wrong turn."""
    spy = Spy('{"answer": "ok"}')
    converse(
        Client(ACCESS, spy),
        [Turn(role=Role.ASSISTANT, text="alignment.bam")],
        "and?",
        Answer,
        [],
    )
    assert "assistant: alignment.bam" in spy.seen


def test_an_empty_history_sends_the_question_alone() -> None:
    """No empty `The conversation so far:` preamble — a header over nothing is noise the
    model has to interpret."""
    spy = Spy('{"answer": "ok"}')
    converse(Client(ACCESS, spy), [], "why?", Answer, [])
    assert "conversation so far" not in spy.seen


def test_evidence_still_reaches_the_prompt() -> None:
    """Chat grounds on the same evidence a generation does; a chat that dropped it would
    answer from the model's own memory of the tool."""
    spy = Spy('{"answer": "ok"}')
    converse(Client(ACCESS, spy), [], "why?", Answer, ["E001 the port is declared sorted"])
    assert "E001 the port is declared sorted" in spy.seen


def test_the_refusal_is_readable_off_the_client() -> None:
    """The reason `converse` takes a `Client`. An earlier draft stashed this in a module-level
    map keyed by `id(access)`, which CPython reuses once the object is collected."""
    client = Client(ACCESS, Spy("not json at all"))
    assert converse(client, [], "why?", Answer, []) is None
    assert "MA0004" in client.last_refusal
