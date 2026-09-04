"""What a call cost, when the provider said, and nothing invented when it did not.

§2's audit rule asks that every model response record its model, timing and token counts
*when the provider supplies them*. The whole risk here is the last clause: a `0` where nothing
was reported is a measurement nobody took, and an audit row cannot tell the two apart.
"""

from comeni_ai.access import ModelAccess
from comeni_ai.client import Client, Metered, Transport, Usage
from pydantic import BaseModel, ConfigDict

ACCESS = ModelAccess(model="ollama/llama3")


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


class Plain:
    """A `send`-only transport. Every fake in the suite is this shape."""

    def send(self, access: ModelAccess, prompt: str) -> str:
        return '{"answer": "ok"}'


class Counting:
    """A transport that also reports what the call cost."""

    def send(self, access: ModelAccess, prompt: str) -> str:
        return self.deliver(access, prompt)[0]

    def deliver(self, access: ModelAccess, prompt: str) -> tuple[str, Usage]:
        return '{"answer": "ok"}', Usage(
            model="ollama/llama3:8b-q4",
            duration_ms=1234,
            input_tokens=900,
            output_tokens=12,
            finish_reason="stop",
        )


def test_a_plain_transport_still_works_and_reports_no_usage() -> None:
    """The compatibility half: nothing that implements only `send` had to change."""
    client = Client(ACCESS, Plain())
    assert client.generate("q", Answer, []) == Answer(answer="ok")
    assert client.last_usage is None


def test_a_plain_transport_is_not_mistaken_for_a_metered_one() -> None:
    assert isinstance(Plain(), Transport)
    assert not isinstance(Plain(), Metered)


def test_a_metered_transport_reports_what_the_provider_said() -> None:
    client = Client(ACCESS, Counting())
    assert client.generate("q", Answer, []) == Answer(answer="ok")
    assert client.last_usage is not None
    assert client.last_usage.input_tokens == 900
    assert client.last_usage.duration_ms == 1234


def test_the_recorded_model_is_what_answered_not_what_was_asked_for() -> None:
    """A provider may serve a dated snapshot for a floating alias, and a review record naming
    the alias cannot be reproduced."""
    client = Client(ACCESS, Counting())
    client.generate("q", Answer, [])
    assert client.access.model == "ollama/llama3"
    assert client.last_usage.model == "ollama/llama3:8b-q4"


def test_usage_is_cleared_before_each_call() -> None:
    """A usage record left over from a previous call is attributed to this one by whatever
    reads it afterwards — worse than recording nothing."""

    class Once:
        def __init__(self) -> None:
            self.calls = 0

        def send(self, access: ModelAccess, prompt: str) -> str:
            self.calls += 1
            return '{"answer": "ok"}'

        def deliver(self, access: ModelAccess, prompt: str) -> tuple[str, Usage]:
            self.calls += 1
            if self.calls > 1:
                raise TimeoutError("MA0003 no answer")
            return '{"answer": "ok"}', Usage(model="m", duration_ms=1)

    client = Client(ACCESS, Once())
    assert client.generate("q", Answer, []) is not None
    assert client.last_usage is not None
    assert client.generate("q", Answer, []) is None
    assert client.last_usage is None, "a timed-out call kept the previous call's usage"


def test_the_exact_prompt_sent_is_readable_for_a_digest() -> None:
    """The instruction a caller passed is not what crossed the wire — the schema and the
    evidence are composed around it — so a digest of the caller's own string is of the wrong
    text."""
    client = Client(ACCESS, Plain())
    client.generate("the instruction", Answer, ["E001 something"])
    assert client.last_prompt is not None
    assert "the instruction" in client.last_prompt
    assert "E001 something" in client.last_prompt
    assert client.last_prompt != "the instruction"


def test_token_counts_are_absent_rather_than_zero_when_unreported() -> None:
    """A local endpoint may report no usage block at all."""
    usage = Usage(model="m", duration_ms=5)
    assert usage.input_tokens is None
    assert usage.output_tokens is None
