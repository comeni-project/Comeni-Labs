"""A conversation with tools: what the builder agent sends and gets back (#463).

The agent loop keeps the messages, in the provider's chat shape, and the tool specs; a transport
returns the model's text and the tools it called. Running a tool is the caller's: this package
only carries the conversation. :class:`ScriptedAgentTransport` replays a fixed script for tests,
which never call a live model.
"""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from comeni_ai.access import ModelAccess
from comeni_ai.client import Usage


class ToolSpec(BaseModel):
    """One tool the model may call: its name, what it is for, and its arguments' JSON schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    parameters: dict

    def as_provider(self) -> dict:
        """The tool in the OpenAI function-calling shape LiteLLM sends to every provider."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


class ToolCall(BaseModel):
    """One call the model made: the provider's id, the tool's name and its arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class AgentReply(BaseModel):
    """What the model answered: its text, the tools it called, usage, and why it was refused.

    `refusal` is a coded reason the reply could not be read whole (MA0004: arguments that were
    not JSON); the calls are still returned, with empty arguments, so the loop can tell the model
    what went wrong rather than failing the turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = ""
    calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage | None = None
    refusal: str | None = None
    tool_choice: Literal["required"] | None = None
    """Effective provider policy for invocation provenance; None means auto/omitted."""


@runtime_checkable
class AgentTransport(Protocol):
    """Send a conversation and the tools it may use; return what the model answered."""

    def converse(self, access: ModelAccess, messages: list[dict],
                 tools: list[ToolSpec], *, tool_choice: Literal["required"] | None = None,
                 cache_key: str | None = None) -> AgentReply:
        """`cache_key` names the conversation a call continues, the same for every call of
        one (#555): an opaque digest, never a person's words, so a provider's prompt cache can
        find the prefix it already holds."""
        ...


class ScriptedAgentTransport:
    """Answer with fixed replies, in order, and keep each conversation it was sent."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = list(replies)
        self.sent: list[list[dict]] = []
        self.tool_choices: list[Literal["required"] | None] = []
        self.keys: list[str | None] = []

    def converse(self, access: ModelAccess, messages: list[dict],
                 tools: list[ToolSpec], *, tool_choice: Literal["required"] | None = None,
                 cache_key: str | None = None) -> AgentReply:
        self.sent.append([dict(m) for m in messages])
        self.tool_choices.append(tool_choice)
        self.keys.append(cache_key)
        if len(self.sent) > len(self._replies):
            raise AssertionError("the script ran out: the agent called the model again")
        return self._replies[len(self.sent) - 1]
