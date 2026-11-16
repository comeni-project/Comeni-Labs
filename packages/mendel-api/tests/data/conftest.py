"""Shared fixtures for the data tests (#511): a data root, and a client whose queue is
recorded. The helpers are `mendel_api_tests.data`."""

import pytest
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.main import create_app
from mendel_api.settings import settings


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / "data"
    base.mkdir()
    monkeypatch.setattr(settings, "data_roots", [base])
    return base


@pytest.fixture
def client(monkeypatch):
    queued = []

    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE, expires=None):
        queued.append((name, args, job_id))
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    app = TestClient(create_app())
    app.queued = queued
    return app
