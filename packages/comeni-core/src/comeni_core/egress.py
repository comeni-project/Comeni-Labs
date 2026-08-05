"""The doors data may leave through, and the types that may pass them.

Invariant 14. There are four: goal extraction, tier-4 resolution, compiler repair,
and publication. Each carries one declared payload type.

This module declares those types and can never send one. Invariant 1 keeps every
transport in the impure packages, so pure code decides what may leave and impure
code does the leaving; neither can do the other's job.

Publication is the door with no undo. A leaked prompt in a model call is an
incident; a leaked prompt in a signed public registry is in every clone's history
permanently, and git is built to make that hard to reverse.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from comeni_core.decision import DecisionRecord
from comeni_core.goal import Goal
from comeni_core.ir import PipelineIR
from comeni_core.lockfile import Lockfile
from comeni_core.marks import (
    ContractId,
    NodeId,
    Subject,
    Text,
    TypeId,
)


class EgressPayload(BaseModel):
    """Base for anything that may cross a door.

    `extra="forbid"` so a field cannot be smuggled in at runtime; `frozen=True` so
    what was reviewed is what is sent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class ErrorCategory(StrEnum):
    """Why a gate failed, as closed vocabulary.

    Nextflow's stderr carries work directories and input filenames, and the repair
    loop would forward it to a model. Machine-generated text is the likeliest leak
    precisely because nobody wrote it and nobody reads it. So the category is
    parsed from the output and the output itself stays on the machine that made it.
    """

    MISSING_INPUT = "missing_input"
    CHANNEL_CARDINALITY = "channel_cardinality"
    SYNTAX = "syntax"
    CONTAINER_PULL = "container_pull"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


class GateFailure(EgressPayload):
    """A gate failure reduced to facts."""

    process: NodeId
    exit_code: int
    category: ErrorCategory
    tool_message: Text | None = None
    """Populated only in the `open` profile. Free text, and declared as such."""


class PromptRequest(EgressPayload):
    """Door 1 — goal extraction. The single taint source."""

    prompt: Text


class AmbiguityRequest(EgressPayload):
    """Door 2 — tier-4 resolution. Registry vocabulary and nothing else.

    Deliberately not a free-form context dict. `dict[str, Any]` would carry
    anything, which is why the guard forbids it — the fields a tier-4 call
    actually needs are these.
    """

    node_id: NodeId
    subject: Subject
    candidates: list[ContractId] = []
    states: list[TypeId] = []
    tier_hint: int | None = None


class RepairRequest(EgressPayload):
    """Door 3 — compiler repair. The IR, plus typed failure facts."""

    ir: PipelineIR
    failure: GateFailure


class PublishBundle(EgressPayload):
    """Door 4 — publication. The door with no undo.

    A shareable pipeline is what a human asked for, what it resolved to, why each choice
    was made, and against exactly which registry — federation spec §4.1. All four, or the
    recipient cannot reproduce it and cannot audit it.
    """

    goal: Goal
    ir: PipelineIR
    decisions: list[DecisionRecord] = []
    lockfile: Lockfile = Lockfile()


DOORS: dict[str, type[EgressPayload]] = {
    "goal_extraction": PromptRequest,
    "tier4_resolution": AmbiguityRequest,
    "compiler_repair": RepairRequest,
    "publication": PublishBundle,
}
