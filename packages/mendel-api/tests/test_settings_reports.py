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
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    monkeypatch.setattr(reports, "_ENGINE", None)
    assert reports.REPORTERS["system.database"]() == "not reachable"


def test_a_queue_that_does_not_answer_says_so(monkeypatch):
    """Review I1: health's probe swallows the error, so the row claimed the queue answered."""
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1")
    assert reports.REPORTERS["system.redis"]() == "not reachable"


def test_the_database_row_is_bounded_in_time(monkeypatch):
    """Review I2: a database that drops packets held the page for 130 s. The reporter connects
    with its own short timeout."""
    seen = {}

    def engine(url, **kwargs):
        seen.update(kwargs)
        raise ConnectionRefusedError()

    monkeypatch.setattr(reports, "create_engine", engine)
    monkeypatch.setattr(reports, "_ENGINE", None)
    assert reports.REPORTERS["system.database"]() == "not reachable"
    assert seen.get("connect_args", {}).get("connect_timeout", 99) <= 3
