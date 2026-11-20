"""Validated model access for Comeni Labs.

The public surface sends prompts through a configurable transport and validates replies against
caller-supplied Pydantic models. Choice and conversation helpers retain that same validation
boundary. Prompt text and domain reply models remain owned by callers; this package supplies only
provider access, transport, generic helpers, and prompt-file mechanics.

This package is intentionally impure and may depend on :mod:`comeni_core`; pure workspace
packages must not depend on it.
"""

import os

# litellm runs `load_dotenv()` when it is first imported unless `LITELLM_MODE` says otherwise,
# which would put whatever `.env` sits in the working directory into this process, beside the
# settings store that owns configuration (#602). Set before any import of litellm below; a mode
# the deployment chose is kept.
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

from comeni_ai.access import ModelAccess  # noqa: E402
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
