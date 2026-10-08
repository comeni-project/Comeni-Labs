"""Payloads describing a pipeline plan and a compilation or gate failure."""

from enum import StrEnum

from comeni_core.egress.base import EgressPayload
from comeni_core.plan.ir import PipelineIR
from comeni_core.spell.marks import NodeId, Text


class ErrorCategory(StrEnum):
    """Closed failure categories reported to the compiler repair adapter."""

    MISSING_INPUT = "missing_input"
    CHANNEL_CARDINALITY = "channel_cardinality"
    SYNTAX = "syntax"
    CONTAINER_PULL = "container_pull"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


class GateFailure(EgressPayload):
    """Process identity, exit code, and categorized failure facts for repair."""

    process: NodeId
    exit_code: int
    category: ErrorCategory
    tool_message: Text | None = None
    """Optional tool output; populated by callers only for the open profile."""


class RepairRequest(EgressPayload):
    """Resolved plan and categorized gate failure supplied for compiler repair."""

    ir: PipelineIR
    failure: GateFailure
