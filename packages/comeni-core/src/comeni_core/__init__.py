"""Shared data model for Comeni Labs: contracts, vocabularies, measurements, IR.

This package is **pure**: no web framework, no HTTP client, no model library. That is
enforced by a closed import allowlist in `tests/guards/test_purity.py`, which covers the standard
library and the dynamic import forms as well as third-party names. If a change here seems
to need one of those, the design is wrong rather than the guard.

It keeps the platform name rather than the product name because its IR is the interface
the execution layer will consume.
"""

from comeni_core.declared.contract import (
    Alternative,
    InputPort,
    ModuleContract,
    NfInput,
    OutputPort,
    Param,
    Provenance,
)
from comeni_core.declared.layered import DeclaredKind, Displacement, Layer
from comeni_core.declared.measurement import (
    BadMeasurementValueError,
    Measurement,
    MeasurementKind,
    MeasurementRegistry,
    UnknownMeasurementError,
)
from comeni_core.declared.registry import Registry, module_key
from comeni_core.declared.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary
from comeni_core.egress.authoring import AuthoringRequest, AuthoringRole, AuthoringTurn, KnownStep
from comeni_core.egress.base import EgressPayload
from comeni_core.egress.boundaries import (
    BOUNDARIES,
    FLOWS,
    PAYLOADS,
    Boundary,
    BoundaryFlow,
    payloads_for,
)
from comeni_core.egress.forge_review import ForgeReviewRequest, ReviewRole, ReviewTurn
from comeni_core.egress.repair import ErrorCategory, GateFailure, RepairRequest
from comeni_core.egress.resolution import AmbiguityRequest
from comeni_core.goal.asked import Constraints, Goal, GoalInput, ParamOverride
from comeni_core.goal.profile import DataProfile, Measured
from comeni_core.plan.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.plan.draft import (
    DraftChannel,
    DraftEdge,
    DraftGraph,
    DraftLabel,
    DraftNode,
)
from comeni_core.plan.ir import IREdge, IRNode, ParamBinding, PipelineIR, ResolvedValue
from comeni_core.plan.tiers import ReviewLevel, Tier, ValueSource, review_level_for
from comeni_core.review import Answer, Candidate, Excerpt, Question
from comeni_core.review.verdict import Finding, Level, Verdict
from comeni_core.spell.marks import Mark, ParamValue

__version__ = "0.1.0"

__all__ = [
    "Alternative",
    "Ambiguity",
    "AmbiguityRequest",
    "Answer",
    "BadMeasurementValueError",
    "Candidate",
    "Constraints",
    "DataProfile",
    "DecisionRecord",
    "BOUNDARIES",
    "DeclaredKind",
    "Displacement",
    "Boundary",
    "BoundaryFlow",
    "PAYLOADS",
    "payloads_for",
    "DraftChannel",
    "DraftEdge",
    "DraftGraph",
    "DraftLabel",
    "DraftNode",
    "EgressPayload",
    "ErrorCategory",
    "Excerpt",
    "Finding",
    "ForgeReviewRequest",
    "GateFailure",
    "Goal",
    "GoalInput",
    "InputPort",
    "IREdge",
    "IRNode",
    "Layer",
    "Level",
    "Mark",
    "Measured",
    "Measurement",
    "MeasurementKind",
    "MeasurementRegistry",
    "module_key",
    "ModuleContract",
    "NfInput",
    "OutputPort",
    "Param",
    "ParamBinding",
    "ParamOverride",
    "ParamValue",
    "FLOWS",
    "PipelineIR",
    "AuthoringRequest",
    "AuthoringRole",
    "AuthoringTurn",
    "KnownStep",
    "Provenance",
    "Question",
    "Registry",
    "RepairRequest",
    "Resolution",
    "ResolvedValue",
    "review_level_for",
    "ReviewLevel",
    "ReviewRole",
    "ReviewTurn",
    "Tier",
    "UnknownMeasurementError",
    "UnknownStateError",
    "UnknownTypeError",
    "ValueSource",
    "Verdict",
    "Vocabulary",
]
