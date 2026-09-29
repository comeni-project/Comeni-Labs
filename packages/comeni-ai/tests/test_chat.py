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


# ── the two-part send (14.7.4, #183) ──────────────────────────────────────────────────────


def _recording(seen: list):
    class Records:
        def send(self, access, prompt):
            seen.append(prompt)
            return '{"answer": "x"}'

    return Records()


def test_a_split_prompt_is_sent_as_system_then_user():
    import json

    seen: list = []
    client = Client(ACCESS, transport=_recording(seen))
    assert client.chat("fixed part", "per call", Answer).answer == "x"
    [messages] = seen
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "fixed part" in json.dumps(messages[0]) and "per call" in json.dumps(messages[1])
    assert client.last_prompt.startswith("fixed part") and "per call" in client.last_prompt


def test_the_schema_is_in_the_fixed_part_and_the_json_line_closes_the_user_part():
    seen: list = []
    Client(ACCESS, transport=_recording(seen)).chat("fixed", "per call", Answer)
    system, user = seen[0]
    assert '"answer"' in system["content"] and "schema exactly" in system["content"]
    assert user["content"].rstrip().endswith("matching the schema above.")


def test_anthropic_gets_cache_markers_and_other_providers_do_not():
    from comeni_ai.client import _messages

    blocks = _messages(
        ModelAccess(model="anthropic/claude-sonnet-5"), "one\n<!-- cache -->\ntwo", "u", Answer
    )[0]["content"]
    assert [b.get("cache_control") for b in blocks] == [{"type": "ephemeral"}] * 2
    plain = _messages(
        ModelAccess(model="ollama_chat/gemma3:12b"), "one\n<!-- cache -->\ntwo", "u", Answer
    )
    assert isinstance(plain[0]["content"], str)
    assert "<!-- cache -->" not in plain[0]["content"]


def test_choose_one_can_send_a_fixed_part():
    from comeni_ai.choice import Option, choose_one

    seen: list = []

    class Chooses:
        def send(self, access, prompt):
            seen.append(prompt)
            return '{"value": "a", "why": "because"}'

    client = Client(ACCESS, transport=Chooses())
    answer = choose_one(client, "which?", [Option(value="a"), Option(value="b")], [],
                        system="the fixed framing")
    assert answer.value == "a"
    assert [m["role"] for m in seen[0]] == ["system", "user"]
