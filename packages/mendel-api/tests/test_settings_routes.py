"""The settings routes (spec §8). The catalogue and store are overridden: these tests are about
the transport, and the store has its own tests."""

import pytest
from comeni_core.settings import Catalogue, Installation, Section, Setting
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services.installation import installation

HELP = "How the build walks you through its steps, one at a time or all at once."
PACING = Setting.choice(
    key="building.pacing", label="Pacing", help=HELP,
    options=[("together", "Together"), ("ask", "Ask")], default="ask", env="COMENI_BUILD_PACING",
)
KEY = Setting.secret(key="models.key", label="Key", help=HELP)
LEVEL = Setting.choice(
    key="building.level", label="Level", help=HELP, default="zero",
    options=[("zero", "Zero"), ("sealed", "Sealed")], designed={"sealed": "designed (issue 71)"},
)
CATALOGUE = Catalogue(
    sections=(
        Section(key="building", title="Building", order=1, settings=(PACING, LEVEL)),
        Section(key="models", title="Models", order=2, settings=(KEY,)),
    )
)


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value


class Reversing:
    def seal(self, plain):
        return "sealed:" + plain[::-1]

    def open(self, sealed):
        return sealed.removeprefix("sealed:")[::-1]


@pytest.fixture
def made():
    return {"env": {}, "store": MemoryStore()}


@pytest.fixture
def client(made):
    app = create_app()
    app.dependency_overrides[installation] = lambda: Installation(
        CATALOGUE, made["store"], made["env"], codec=Reversing()
    )
    return TestClient(app)


def test_the_menu_lists_every_section_with_values_and_sources(client):
    body = client.get("/api/settings").json()
    assert [s["key"] for s in body["sections"]] == ["building", "models"]
    entry = body["sections"][0]["entries"][0]
    assert entry["setting"]["key"] == "building.pacing"
    assert entry["shown"] == {
        "value": "ask", "source": "default", "locked": False, "reason": None,
        "set": None, "last4": None,
    }


def test_a_put_is_stored_and_answered_with_what_is_now_shown(client, made):
    answer = client.put("/api/settings/building.pacing", json={"value": "together"})
    assert answer.status_code == 200
    assert answer.json()["source"] == "installation"
    assert made["store"].rows == {"building.pacing": "together"}


def test_a_locked_setting_answers_409_with_its_code_and_reason(client, made):
    made["env"]["COMENI_BUILD_PACING"] = "together"
    answer = client.put("/api/settings/building.pacing", json={"value": "ask"})
    assert answer.status_code == 409
    assert answer.json()["detail"].startswith("MI0300")
    assert "COMENI_BUILD_PACING" in answer.json()["detail"]


def test_an_illegal_value_answers_422_with_its_code(client):
    answer = client.put("/api/settings/building.pacing", json={"value": "sometimes"})
    assert answer.status_code == 422
    assert answer.json()["detail"].startswith("MI0302")


@pytest.mark.parametrize("body", [{}, {"value": None}])
def test_a_put_with_no_value_answers_422(client, made, body):
    answer = client.put("/api/settings/building.pacing", json=body)
    assert answer.status_code == 422
    assert made["store"].rows == {}


def test_an_unknown_setting_answers_404(client):
    assert client.put("/api/settings/building.nothing", json={"value": 1}).status_code == 404


def test_a_secret_comes_back_as_set_and_last_four(client, made):
    answer = client.put("/api/settings/models.key", json={"value": "sk-abcdef1234"})
    assert answer.json()["value"] is None and answer.json()["last4"] == "1234"
    assert "sk-abcdef1234" not in client.get("/api/settings").text
    assert made["store"].rows["models.key"] != "sk-abcdef1234"


def test_a_designed_option_answers_409_with_mi0303(client, made):
    answer = client.put("/api/settings/building.level", json={"value": "sealed"})
    assert answer.status_code == 409
    assert answer.json()["detail"].startswith("MI0303")
    assert "issue 71" in answer.json()["detail"]
