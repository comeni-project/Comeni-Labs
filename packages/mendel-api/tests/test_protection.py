"""May this cross? Level 0 lets every crossing through; every other level refuses, coded."""

from mendel_api.services import protection


def test_level_0_allows_every_crossing(monkeypatch):
    monkeypatch.setattr(protection, "level", lambda: "level_0")
    assert all(protection.allows(c) for c in protection.Crossing)


def test_any_other_level_refuses_with_a_code(monkeypatch):
    monkeypatch.setattr(protection, "level", lambda: "sealed")
    assert not protection.allows(protection.Crossing.UPLOAD)
    assert "MI0213" in protection.refuse(protection.Crossing.UPLOAD)


def test_a_designed_level_says_it_is_not_built(monkeypatch):
    """Issue 226: `COMENI_PROTECTION_LEVEL=open` failed every crossing with an opaque MI0213."""
    monkeypatch.setattr(protection, "level", lambda: "open")
    said = protection.refuse(protection.Crossing.UPLOAD)
    assert "MI0213" in said and "designed, not built" in said


def test_a_designed_level_pinned_in_the_environment_is_warned_at_startup(monkeypatch, caplog):
    import logging

    from mendel_api.main import create_app

    monkeypatch.setenv("COMENI_PROTECTION_LEVEL", "guarded")
    with caplog.at_level(logging.WARNING, logger="mendel_api.services.protection"):
        create_app()
    assert any("guarded" in r.getMessage() and "not built" in r.getMessage()
               for r in caplog.records), caplog.text


def test_level_0_in_the_environment_is_not_warned(monkeypatch, caplog):
    import logging

    from mendel_api.main import create_app

    monkeypatch.setenv("COMENI_PROTECTION_LEVEL", "level_0")
    with caplog.at_level(logging.WARNING, logger="mendel_api.services.protection"):
        create_app()
    assert not [r for r in caplog.records if r.name == "mendel_api.services.protection"]
