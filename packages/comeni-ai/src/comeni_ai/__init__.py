"""Validated model access for Comeni Labs.

The public surface sends prompts through a configurable transport and validates replies against
caller-supplied Pydantic models. Choice and conversation helpers retain that same validation
boundary. Prompt text and domain reply models remain owned by callers; this package supplies only
provider access, transport, generic helpers, and prompt-file mechanics.

This package is intentionally impure and may depend on :mod:`comeni_core`; pure workspace
packages must not depend on it. The deprecated :mod:`mendel_ai` package re-exports the older
public surface for compatibility.
"""

from comeni_ai.access import ModelAccess
from comeni_ai.chat import Role, Turn, converse
from comeni_ai.choice import WHY_LIMIT, Choice, Choices, Option, choose_many, choose_one
from comeni_ai.client import (
    Client,
    Metered,
    ModelUnavailableError,
    NoModelError,
    Transport,
    Usage,
)
from comeni_ai.prompts import PromptId, PromptTemplate, Rendered, UnknownPromptError

__all__ = [
    "WHY_LIMIT",
    "Choice",
    "Choices",
    "Client",
    "Metered",
    "ModelAccess",
    "ModelUnavailableError",
    "NoModelError",
    "Option",
    "PromptId",
    "PromptTemplate",
    "Rendered",
    "Role",
    "Transport",
    "Turn",
    "UnknownPromptError",
    "Usage",
    "choose_many",
    "choose_one",
    "converse",
]
