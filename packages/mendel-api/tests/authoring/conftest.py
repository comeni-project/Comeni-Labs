"""Fixtures scoped to authoring scenarios; other API tests retain production defaults."""

import pytest


@pytest.fixture(autouse=True)
def one_step_by_default(monkeypatch):
    """**The first call is one step in this suite unless a test says otherwise** (#194).

    Production chooses a family first (`family_step_from = 0`). Nearly every test here feeds the
    goal call's answer as the model's first reply, which the family step would now receive; the
    one-step path stays a supported setting, and the tests of the family step switch it on.
    """
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "family_step_from", 10**9)


@pytest.fixture(autouse=True)
def together_by_default(monkeypatch):
    """**The walk stops at every step in this suite unless a test says otherwise** (14.7.8.3b).

    Production asks how to pace each build (`building.pacing` defaults to *ask*). Most tests
    here walk a pipeline a step at a time, which is *together*; the tests of pacing itself clear
    or change this. Pinned through the setting's own environment variable, the way an operator
    would pin it.
    """
    monkeypatch.setenv("COMENI_BUILD_PACING", "together")
