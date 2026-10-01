"""What Mendel reports in the read-only sections (spec §7)."""

from comeni_core.settings import catalogue as c
from mendel_api.services import reports


def test_every_mendel_read_only_setting_has_a_reporter():
    served = [
        s for section in c.CATALOGUE.served_by("mendel") for s in section.settings
        if s.kind == "readonly"
    ]
    assert served, "nothing is read-only — this test is measuring nothing"
    from mendel_api.services.installation import installation

    assert {s.key for s in served} <= set(installation().reporters)


def test_a_token_is_reported_as_set_never_as_itself(monkeypatch):
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN", "ghp_secret_value_1234")
    assert reports.REPORTERS["registry.github"]() == "set"
    monkeypatch.delenv("COMENI_FORGE_GITHUB_TOKEN")
    assert reports.REPORTERS["registry.github"]() == "not set"


def test_docker_hub_needs_both_halves(monkeypatch):
    monkeypatch.setenv("COMENI_FORGE_DOCKERHUB_USER", "someone")
    monkeypatch.delenv("COMENI_FORGE_DOCKERHUB_TOKEN", raising=False)
    half = reports.REPORTERS["registry.dockerhub"]()
    assert half == "not set (needs both the user and the token)"


def test_versions_name_every_package():
    names = {row["part"] for row in reports.REPORTERS["system.versions"]()}
    assert {"comeni-core", "mendel-api", "comeni-ai"} <= names


def test_a_registry_that_cannot_be_read_says_so(monkeypatch, tmp_path):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "registry_root", tmp_path / "nowhere")
    assert reports.REPORTERS["registry.layers"]().startswith("not readable")


def test_the_source_check_time_is_the_workers_own():
    assert reports.REPORTERS["registry.source_check"]() == "every day at 03:00"


def test_a_database_that_does_not_answer_says_so(monkeypatch):
    from mendel_api import db

    def refuse():
        raise ConnectionRefusedError()

    monkeypatch.setattr(db, "session_scope", refuse)
    assert reports.REPORTERS["system.database"]() == "not reachable"
