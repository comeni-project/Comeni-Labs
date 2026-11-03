"""What a model must reply when forging (spec §3). Validated where it arrives: a reply that does
not fit is refused, never repaired into a proposal.

**An `approve` cannot be spelled here**: `AiCommand.move` admits only the AI's proposals, so a
reply that tries to decide fails validation and changes nothing.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AskedQuestion(_Reply):
    key: str
    """`questions:<subject>[:<name>]`, e.g. `questions:role`, `questions:input_type:reads`."""
    asks: str
    options: list[dict]
    allows_new: bool = True
    suggested: str | None = None


class QuestionsReply(_Reply):
    questions: list[AskedQuestion]


class DraftReply(_Reply):
    items: dict[str, JsonValue]
    """Item key → value, each the registry's own model (`mendel_forge.forging.values`)."""
    because: dict[str, str] = {}


class AiCommand(_Reply):
    move: Literal["revise", "add", "propose_removal"]
    item: str
    value: JsonValue = None
    because: str


class ChatReply(_Reply):
    text: str
    commands: list[AiCommand] = []


class ReviewComment(_Reply):
    item: str
    comment: str = Field(min_length=1, max_length=4000)
    quote: str | None = None
    file: Literal["main.nf", "meta.yml", "tests/main.nf.test"] | None = None


class ReviewReply(_Reply):
    comments: list[ReviewComment]
