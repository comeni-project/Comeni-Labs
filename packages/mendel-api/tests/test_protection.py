"""May this cross? Level 0 lets every crossing through; every other level refuses, coded."""

from mendel_api.services import protection


def test_level_0_allows_every_crossing(monkeypatch):
    monkeypatch.setattr(protection, "level", lambda: "level_0")
    assert all(protection.allows(c) for c in protection.Crossing)


def test_any_other_level_refuses_with_a_code(monkeypatch):
    monkeypatch.setattr(protection, "level", lambda: "sealed")
    assert not protection.allows(protection.Crossing.UPLOAD)
    assert "MI0213" in protection.refuse(protection.Crossing.UPLOAD)
