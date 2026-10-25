"""Represent an answered review question and the provenance of its value.

This module stays below :mod:`comeni_core.plan` in the dependency graph because plan decisions
specialize these models. ``ValueSource`` is re-exported from ``plan.tiers`` for compatibility.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ValueSource(StrEnum):
    """Identify who or what settled a value, independently of its resolution tier."""

    RESOLVER = "resolver"
    """The deterministic resolution ladder selected the value."""

    SAID = "said"
    """The person stated the value before resolution encountered an ambiguity."""

    HUMAN = "human"
    """A person answered an ambiguity that resolution could not settle."""

    MODEL = "model"
    """A model answered an ambiguity that deterministic resolution could not settle."""

    MEASURED = "measured"
    """A named measurement tool established the value from data."""

    DERIVED = "derived"
    """The value was read directly from source material."""


class Answer(BaseModel):
    """Record a value, its source, the responsible actor or tool, and the rationale.

    The base model is deliberately inert and permits any value. Domain-specific subclasses such
    as ``Resolution`` narrow ``value`` and add their own fields.
    """

    model_config = ConfigDict(extra="forbid")

    value: Any
    by: str
    """Username, model identifier, measurement tool, or source name."""
    how: ValueSource
    why: str
