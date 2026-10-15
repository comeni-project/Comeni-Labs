"""Unrelated API tests use production defaults, not authoring-scenario defaults."""

from mendel_api.settings import Settings, settings


def test_family_selection_default_is_not_replaced_outside_authoring():
    assert settings.family_step_from == Settings().family_step_from
