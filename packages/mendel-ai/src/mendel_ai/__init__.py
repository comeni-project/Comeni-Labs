"""Model access for Mendel.

**One primitive.** `generate(instruction, shape, evidence)` asks a model for something and
validates the answer against a declared Pydantic shape before any caller sees it. Closed
choice — `choose_one`, `choose_many` — is a helper over it, for the case where the shape is
*one of these values*.

That is the boundary, and it is the one the rest of the system already enforces: not that a
model may not speak, but that nothing it says is taken on trust. A drafted rule has the rule
validator; a `Goal` is a Pydantic model. **A module's script body has no shape**, which is why
`MF0005` refuses it and why nothing here will fill one.

**This package holds no Mendel domain types.** It speaks in strings and shapes its caller
declares, which is what lets the tier-4 ambiguity resolver reuse it unchanged when Plan 3
arrives (`docs/notes/README.md` row 17). `comeni-core` is imported for `coded()` and nothing else.

**It is impure and classified as such** in `tests/guards/test_purity.py`. The arrow points
`mendel-ai -> comeni-core`, never back.

Read `docs/notes/specs/2026-08-17-forge-phase-2.md` §4 before changing this package's surface —
§4.3 records two ways the first design of it was wrong.
"""

from mendel_ai.access import ModelAccess
from mendel_ai.choice import WHY_LIMIT, Choice, Choices, Option, choose_many, choose_one
from mendel_ai.client import Client, ModelUnavailableError, NoModelError, Transport

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
