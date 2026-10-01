"""Every real declaration, held to the spec's rules, and the served menu as a golden file."""

import json
import os
from pathlib import Path

from comeni_core.settings import CATALOGUE, Installation, Kind, resolve

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
