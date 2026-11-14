"""What the builder agent's tools return to its model (#463): one result per tool call.

A tool's name, whether it worked, a typed view of what it read or did, or the coded refusal the
engine gave. The views are declared here, beside the door, so the egress guards walk every shape
that reaches a model. At protection level 0 a view may carry a sample's name (the operator's
decision, 2026-11-14); stricter levels filter before a view is built.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import Line, SampleName


class ViewKind(StrEnum):
    """Which view a tool returned: the union's discriminator."""

    TEXT = "text"
    SAMPLES = "samples"


class TextView(EgressPayload):
    """A sentence from the engine about what a tool did."""

    kind: Literal[ViewKind.TEXT] = ViewKind.TEXT
    text: Line


class SamplesView(EgressPayload):
    """The samples of the person's last upload, by name."""

    kind: Literal[ViewKind.SAMPLES] = ViewKind.SAMPLES
    names: list[SampleName] = Field(default_factory=list)


AgentView = Annotated[TextView | SamplesView, Field(discriminator="kind")]
"""Every view a tool may return. Each tool's own view joins this union."""


class AgentToolResult(EgressPayload):
    """One tool call's result, as its model reads it."""

    tool: Line
    ok: bool
    view: AgentView | None = None
    refusal: Line | None = None
