"""Every real declaration, held to the spec's rules, and the served menu as a golden file."""

import json
import os
from pathlib import Path

from comeni_core.settings import CATALOGUE, Designed, Installation, Kind, Source, resolve
from comeni_core.settings.catalogue import BUILDING, PACING, TIER4_ANSWERS

GOLDEN = Path(__file__).parent / "golden" / "settings-menu.json"


class Empty:
    def values(self):
        return {}

    def put(self, key, value, by):
        raise AssertionError("the golden menu never writes")


def test_the_catalogue_is_not_empty():
    assert CATALOGUE.settings(), "no setting is declared — every test below would pass on nothing"


def test_every_setting_has_help_and_a_legal_default():
    for setting in CATALOGUE.settings():
        assert len(setting.help) >= 20, setting.key
        if setting.kind not in (Kind.SECRET, Kind.READONLY):
            assert setting.check(setting.default) == setting.default


def test_every_locked_setting_says_why_with_and_without_env():
    for setting in CATALOGUE.settings():
        for env in ({}, {setting.env: "x"} if setting.env else {}):
            got = resolve(setting, {}, env, secrets_available=False)
            assert not got.locked or got.reason is not None, setting.key


def test_the_served_menu_matches_the_golden_file():
    """A renamed key or reworded help shows up as a reviewable diff. Regenerate with
    SETTINGS_GOLDEN=update, and READ the diff before committing it."""
    produced = Installation(CATALOGUE, Empty(), {}).menu().model_dump_json(indent=2) + "\n"
    if os.environ.get("SETTINGS_GOLDEN") == "update":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(produced)
    assert json.loads(produced) == json.loads(GOLDEN.read_text())


def test_building_sits_between_appearance_and_models():
    assert [s.key for s in CATALOGUE.sections][:3] == ["appearance", "building", "models"]
    assert BUILDING.settings == (PACING, TIER4_ANSWERS)


def test_pacing_is_live_and_an_env_pin_wins_over_the_stored_value():
    """14.7.8.3b: the Pacing fork reads it, so it is no longer designed."""
    got = resolve(
        PACING, {"building.pacing": "together"}, {"COMENI_BUILD_PACING": "stop_where_needed"}
    )
    assert (got.value, got.source, got.locked) == ("stop_where_needed", Source.ENVIRONMENT, True)


def test_tier4_shows_todays_behaviour_designed():
    got = resolve(TIER4_ANSWERS, {}, {})
    assert got.value == "stop" and isinstance(got.reason, Designed)


def test_every_section_says_in_a_line_what_it_holds():
    """The overlay's design (2026-10-01) opens each section with one line under its title;
    like every word about a setting, it comes from the declaration."""
    assert CATALOGUE.sections, "no section is declared — this test is measuring nothing"
    for section in CATALOGUE.sections:
        assert 20 <= len(section.lede) <= 140, section.key


def test_protection_level_0_is_built_and_the_others_are_designed():
    from comeni_core.settings.catalogue import PROTECTION

    assert PROTECTION.unavailable is None
    assert PROTECTION.env == "COMENI_PROTECTION_LEVEL"
    designed = {o.value for o in PROTECTION.options if o.designed}
    assert designed == {"open", "guarded", "sealed"}
    assert PROTECTION.default == "level_0"


def test_a_default_cannot_be_a_designed_option():
    import pytest
    from comeni_core.settings.declare import Setting

    with pytest.raises(ValueError, match="must be built"):
        Setting.choice(
            key="x.y", label="Y", help="Which of two things this setting picks.", default="b",
            options=[("a", "A"), ("b", "B")], designed={"b": "issue 1"},
        )


def test_the_author_is_a_text_setting_under_system_pinned_by_its_env():
    """Issue 268: the name recorded beside what a person does, when git cannot say."""
    from comeni_core.settings.declare import Kind

    setting = CATALOGUE.setting("system.author")
    assert setting.kind is Kind.TEXT and setting.env == "COMENI_AUTHOR"
    assert CATALOGUE.section_of("system.author").key == "system"
