"""Reusable characterisation scenarios and fixtures for API tests."""

import pytest
from comeni_ai import Client, ModelAccess
from mendel_api.services import characterise
from mendel_api.services import session as facade
from mendel_api.stages import samples

from mendel_api_tests.samples import (  # noqa: F401
    _gathering,
    _payload,
    _pending_for,
    clean,
)


@pytest.fixture
def readable(monkeypatch):
    """Level 0 and a model configured: the characteriser is available."""
    monkeypatch.setattr(characterise, "available", lambda: True)
    # `conftest` switches the family step off for every test; the characteriser's two calls are
    # what is under test here, so it is switched back on (production's `0`).
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "family_step_from", 0)


def _at(subject):
    sid = _gathering(["counts.matrix"])
    return sid, _pending_for(sid, subject)


def _facts(sid):
    return facade.read(sid)["facts"]


class _Answers:
    def __init__(self, *bodies):
        self.bodies, self.sent = list(bodies), []

    def send(self, access, prompt):
        self.sent.append(prompt)
        body = self.bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return body


def _clients(*bodies):
    answers = _Answers(*bodies)
    client = Client(
        ModelAccess(model="fake/test", base_url="http://localhost:1"), transport=answers
    )
    return (lambda purpose: client), answers


FASTA = ">chr1 a reference\n" + "ACGT" * 60 + "\n"


def _read(pid, sid, *bodies):
    client_for, answers = _clients(*bodies)
    attempt = samples.start_reading(pid)
    state = characterise.read_sample(sid, pid, attempt, FASTA, False, client_for=client_for)
    return state, answers
