"""What Mendel reports in the read-only sections (spec §7)."""

from comeni_core.settings import catalogue as c
from mendel_api.services import reports


def test_every_mendel_read_only_setting_has_a_reporter():
    served = [
        s
        for section in c.CATALOGUE.served_by("mendel")
        for s in section.settings
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
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN_SET", "set")
    assert reports.REPORTERS["registry.github"]() == "set"


def test_versions_name_every_package():
    names = {row["part"] for row in reports.REPORTERS["system.versions"]()}
    assert {"comeni-core", "mendel-api", "comeni-ai"} <= names


def test_a_registry_that_cannot_be_read_says_so(monkeypatch, tmp_path):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "registry_root", tmp_path / "nowhere")
    assert reports.REPORTERS["registry.layers"]().startswith("not readable")


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


def test_the_model_row_does_not_probe_the_model_server(monkeypatch):
    """**Settings opens at once** (walk 2026-11-17): the row probed the default model's server on
    every read, and an unreachable one held the whole page for its timeout (3.3 s). It says what
    is configured; **Test** on the connection is where the server is tried."""
    from mendel_api.services import probe

    def probed(*args, **kwargs):
        raise AssertionError("the menu probed the model server")

    from types import SimpleNamespace

    from mendel_api import settings as mendel_settings

    monkeypatch.setattr(probe, "answers", probed)
    monkeypatch.setattr(mendel_settings, "model_access",
                        lambda: SimpleNamespace(model="gemma3:12b", base_url="http://ollama:11434"))
    said = reports.REPORTERS["system.model"]()
    assert isinstance(said, str) and said
    assert "gemma3:12b" in said and "answer" not in said


def test_the_model_server_is_checked_on_its_own_after_the_menu(monkeypatch):
    """The menu says what is configured and that a check follows; the check is its own request,
    so an unreachable server holds that row, never the page."""
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from mendel_api import settings as mendel_settings
    from mendel_api.main import create_app
    from mendel_api.services import probe

    async def silent(url, *args, **kwargs):
        return False

    monkeypatch.setattr(probe, "answers", silent)
    monkeypatch.setattr(mendel_settings, "model_access",
                        lambda: SimpleNamespace(model="gemma3:12b", base_url="http://ollama:11434"))
    client = TestClient(create_app())
    entries = {e["setting"]["key"]: e["shown"]
               for s in client.get("/api/settings").json()["sections"] for e in s["entries"]}
    assert entries["system.model"]["checks"] is True
    assert entries["system.database"].get("checks", False) is False
    assert client.get("/api/settings/system.model/check").json() == {"says": "nothing answered"}
    assert client.get("/api/settings/system.database/check").status_code == 404
