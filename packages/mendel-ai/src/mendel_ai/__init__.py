"""Deprecated compatibility exports for :mod:`comeni_ai`.

The module preserves the original ``mendel_ai`` object identities for existing consumers and
warns on import. Newer ``comeni_ai`` names remain absent so new code uses the replacement package.
The repository import guard prevents new internal consumers of this shim.
"""

import warnings

from comeni_ai.access import ModelAccess
from comeni_ai.choice import WHY_LIMIT, Choice, Choices, Option, choose_many, choose_one
from comeni_ai.client import Client, ModelUnavailableError, NoModelError, Transport

warnings.warn(
    "mendel_ai is deprecated and re-exports comeni_ai; import comeni_ai instead. "
    "The environment variables moved too: COMENI_AI_MODEL, COMENI_AI_API_KEY, "
    "COMENI_AI_BASE_URL. The MENDEL_* names are read as a fallback for now.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "WHY_LIMIT",
    "Choice",
    "Choices",
    "Client",
    "ModelAccess",
    "ModelUnavailableError",
    "NoModelError",
    "Option",
    "Transport",
    "choose_many",
    "choose_one",
]
