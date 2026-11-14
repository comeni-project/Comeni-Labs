"""A refusal is a sentence for a person, including a failed shape check (issue 494)."""

import asyncio
import json

from mendel_api.refusals import refusal_handler
from pydantic import BaseModel, ValidationError


class _Strict(BaseModel):
    kind: int


def _answer(exc: Exception):
    response = asyncio.run(refusal_handler(None, exc))
    return response.status_code, json.loads(response.body)["detail"]


def test_a_coded_refusal_is_passed_on_as_written():
    assert _answer(ValueError("MI0204: that names nothing")) == (422, "MI0204: that names nothing")


def test_a_failed_check_is_said_in_words_not_the_validator_dump():
    """Switching an optional input showed the person Pydantic's message and its errors link."""
    try:
        _Strict.model_validate({"kind": "x"})
    except ValidationError as exc:
        status, detail = _answer(exc)
    assert status == 422
    assert "pydantic" not in detail and "validation error" not in detail
    assert detail.startswith("Mendel could not apply this: kind")
