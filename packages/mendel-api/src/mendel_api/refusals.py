"""What a refusal looks like on the wire, and in the schema.

**One place, because two transports over one operation must not disagree.**
A coded `ValueError` becomes `422 {"detail": "MF0003: ..."}`. That shape came from the forge's
own transport, which the CLI still matches — a client that learned the forge's contract must not
need a second one. (That transport was deleted in phase 6; the convention it set outlived it.)

**What is added here is the schema half.** The forge's handler is correct and invisible: nothing
in its OpenAPI document says a 422 can carry a coded string, so a generated client types the
refusal as FastAPI's validation shape and the UI renders `undefined` for the one message a
curator needs. `REFUSES` declares it, and `test_openapi.py` holds every operation to it.
"""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Refusal(BaseModel):
    """A coded refusal. `detail` is `"<code>: <message>"` — `forge explain <code>` expands it."""

    detail: str


async def refusal_handler(request: Request, exc: Exception) -> JSONResponse:
    """422 rather than 400: the body parsed and the values were wrong for it, which is what
    FastAPI already means by 422. A coded refusal is the same kind of answer."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


#: Attach to any operation that can refuse.
#:
#: **Declared as `Refusal` alone, and that is a judgement rather than the whole truth.** A body
#: that fails *validation* also arrives as 422, in FastAPI's own `HTTPValidationError` shape.
#: Declaring both was tried and abandoned: `HTTPValidationError` is a raw dict inside FastAPI
#: rather than an importable model, so the union can only be written as a hand-rolled `anyOf`
#: beside the `$ref` FastAPI emits — and a schema carrying both keywords at one level is what
#: generators render wrongly.
#:
#: What makes the narrower declaration defensible is the consumer: `frontend/src/api/` is
#: generated from this document, so a malformed body is a compile error rather than a runtime
#: 422. The shape a client can actually receive is this one.
REFUSES: dict[int | str, dict[str, Any]] = {
    422: {
        "model": Refusal,
        "description": (
            "A coded refusal — `MF0002`, `MF0003`, `MD…`. `forge explain <code>` expands it. "
            "A malformed body also answers 422, in FastAPI's validation shape."
        ),
    }
}
