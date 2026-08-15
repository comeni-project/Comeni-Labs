"""Shared data model for Comeni Labs: contracts, vocabularies, measurements, IR.

This package is **pure**: no web framework, no HTTP client, no model library. That is
enforced by a closed import allowlist in `tests/test_purity.py`, which covers the standard
library and the dynamic import forms as well as third-party names. If a change here seems
to need one of those, the design is wrong rather than the guard.

It keeps the platform name rather than the product name because its IR is the interface
the execution layer will consume.
"""

from comeni_core.artifact.egress import (
    DOORS,
    AmbiguityRequest,
    EgressPayload,
    ErrorCategory,
    GateFailure,
    PromptRequest,
    RepairRequest,
)
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
from comeni_core.goal.asked import Constraints, Goal, GoalInput, ParamOverride
from comeni_core.goal.profile import DataProfile, Measured
from comeni_core.plan.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.plan.ir import IREdge, IRNode, ParamBinding, PipelineIR, ResolvedValue
from comeni_core.plan.tiers import ReviewLevel, Tier, ValueSource, review_level_for
from comeni_core.spell.marks import Mark, ParamValue

__version__ = "0.1.0"

__all__ = [
    "DOORS",
    "Alternative",
    "Ambiguity",
    "AmbiguityRequest",
    "BadMeasurementValueError",
    "Constraints",
    "DataProfile",
    "DeclaredKind",
    "Displacement",
    "DecisionRecord",
    "EgressPayload",
    "ErrorCategory",
    "Mark",
    "GateFailure",
    "Goal",
    "GoalInput",
    "IREdge",
    "IRNode",
    "InputPort",
    "Layer",
    "Measured",
    "Measurement",
    "MeasurementKind",
    "MeasurementRegistry",
    "ModuleContract",
    "NfInput",
    "OutputPort",
    "Param",
    "ParamBinding",
    "ParamOverride",
    "ParamValue",
    "PipelineIR",
    "PromptRequest",
    "Provenance",
    "Registry",
    "RepairRequest",
    "Resolution",
    "ResolvedValue",
    "ReviewLevel",
    "Tier",
    "UnknownMeasurementError",
    "UnknownStateError",
    "UnknownTypeError",
    "ValueSource",
    "Vocabulary",
    "module_key",
    "review_level_for",
]
