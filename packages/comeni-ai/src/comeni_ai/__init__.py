"""Model access for Comeni Labs.

**One primitive.** `generate(instruction, shape, evidence)` asks a model for something and
validates the answer against a declared Pydantic shape before any caller sees it. Closed
choice — `choose_one`, `choose_many` — is a helper over it, for the case where the shape is
*one of these values*, and `converse` is the same validation over a multi-turn exchange.

That is the boundary, and it is the one the rest of the system already enforces: not that a
model may not speak, but that nothing it says is taken on trust. A drafted rule has the rule
validator; a `Goal` is a Pydantic model. **A module's script body has no shape**, which is why
`MF0005` refuses it and why nothing here will fill one.

**This package holds no domain types.** It speaks in strings and shapes its caller declares,
which is what lets the tier-4 ambiguity resolver reuse it unchanged when Plan 3 arrives
(`docs/notes/README.md` row 17). `comeni-core` is imported for `coded()` and nothing else.

**It was `mendel-ai` until 2026-09-04.** The rename is not cosmetic: an engine-specific name
on the shared transport is what would have produced three clients — one for the Forge, one for
the builder, one for Wiener's agents — and `MENDEL_MODEL` configuring a Wiener agent is a lie
in a `.env` file. `mendel_ai` survives as re-exports for the compatibility window;
`packages/mendel-ai/src/mendel_ai/__init__.py` says when it goes.

**`prompts` is here and prompt text is not.** This package loads, renders and versions a
caller's committed prompt files; what those files *say* about contracts, roles or Nextflow
belongs to the caller. Shared infrastructure that accumulates every agent's prompts has become
a shared pile rather than a boundary.

**It is impure and classified as such** in `tests/guards/test_purity.py`. The arrow points
`comeni-ai -> comeni-core`, never back.

Read `docs/notes/specs/2026-08-17-forge-phase-2.md` §4 before changing this package's surface —
§4.3 records two ways the first design of it was wrong.
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
