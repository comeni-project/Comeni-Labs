"""The preview uses the resolver and is read-only, including refusals and stale revisions."""

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import forging
from mendel_forge.forging.model import Adaptation, Item, Revision, Status

RULE = {
    "decides": [{"effect": "implementation", "of": "alignment"},
                {"effect": "param", "of": "alignment", "name": "seed"}],
    "rows": [
        {"when": {"read_length": ">= 70", "paired": True},
         "then": "long", "because": "long paired reads"},
        {"when": {"read_length": "< 70"}, "then": "short"},
    ],
}
KEY = "rules:rule:alignment"


@pytest.fixture
def preview(monkeypatch):
    state = Adaptation(items={KEY: Item(key=KEY, piece="rules", status="proposed",
        revisions=(Revision(n=2, move="draft", actor="ai", value=RULE),))})

    def load(adaptation_id):
        if adaptation_id != "a1":
            raise KeyError(adaptation_id)
        return state

    monkeypatch.setattr(forging, "load", load)
    client = TestClient(create_app())

    def call(premises, **extra):
        before = state.model_dump()
        response = client.post("/api/forge/adaptations/a1/rule-preview",
            json={"item": KEY, "expected": 2, "premises": premises, **extra})
        assert state.model_dump() == before
        return response

    return call, client, state


@pytest.mark.parametrize(("facts", "chosen"), [
    ({"read_length": 69}, "short"),
    ({"read_length": 70, "paired": True}, "long"),
    ({"read_length": 150, "paired": False}, None),
    ({"read_length": 150}, None),
    ({}, None),
])
def test_real_predicates_boundary_and_all_targets(preview, facts, chosen):
    response = preview[0](facts)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["revision"] == 2
    if chosen is None:
        assert result["effects"] == []
    else:
        assert len(result["effects"]) == 2
        assert {e["value"] for e in result["effects"]} == {chosen}
        assert {e["effect"] for e in result["effects"]} == {"implementation", "param"}


def test_stale_rule_is_refused(preview):
    response = preview[0]({"read_length": 90}, expected=1)
    assert response.status_code == 422
    assert "changed since you looked" in response.json()["detail"]


@pytest.mark.parametrize("key", ["rules:none", "contract:process", "rules:rule:missing"])
def test_preview_does_not_accept_other_items(preview, key):
    response = preview[0]({}, item=key)
    assert response.status_code == 422
    assert response.json()["detail"].startswith("MF0506")


def test_unknown_adaptation_is_404(preview):
    response = preview[1].post("/api/forge/adaptations/absent/rule-preview",
        json={"item": KEY, "expected": 2, "premises": {}})
    assert response.status_code == 404


@pytest.mark.parametrize("status", ["removed", "rejected"])
def test_removed_or_rejected_rule_is_not_previewed(preview, monkeypatch, status):
    call, _, state = preview
    item = state.items[KEY].model_copy(update={"status": Status(status)})
    monkeypatch.setattr(forging, "load", lambda _: Adaptation(items={KEY: item}))
    assert call({}).status_code == 422


def test_first_matching_row_wins(preview, monkeypatch):
    call, _, state = preview
    value = {**RULE, "rows": [{"when": {}, "then": "first"}, *RULE["rows"]]}
    current = state.items[KEY]
    revision = current.current.model_copy(update={"value": value})
    item = current.model_copy(update={"revisions": (revision,)})
    monkeypatch.setattr(forging, "load", lambda _: Adaptation(items={KEY: item}))
    response = call({"read_length": 70, "paired": True})
    assert response.status_code == 200, response.text
    effects = response.json()["effects"]
    assert effects and {e["value"] for e in effects} == {"first"}
