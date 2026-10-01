"""The installation facade: reading, writing, secrets and the served menu (spec §4, §8)."""

import pytest
from comeni_core.settings.declare import IllegalValue, Setting, Where
from comeni_core.settings.installation import Installation, SettingLocked
from comeni_core.settings.reasons import Designed
from comeni_core.settings.sections import Catalogue, Section

HELP = "How the build walks you through its steps, one at a time or all at once."


class MemoryStore:
    def __init__(self):
        self.rows: dict[str, object] = {}
        self.by: dict[str, str] = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value
        self.by[key] = by


class Reversing:
    """A stand-in codec. Not encryption, which is the point: the test is about where it is
    called, and part 2's Fernet codec is tested against the real library."""

    def seal(self, plain):
        return "sealed:" + plain[::-1]

    def open(self, sealed):
        return sealed.removeprefix("sealed:")[::-1]


PACING = Setting.choice(
    key="building.pacing", label="Pacing", help=HELP,
    options=[("together", "Together"), ("ask", "Ask")], default="ask", env="COMENI_BUILD_PACING",
)
KEY = Setting.secret(key="models.key", label="Key", help=HELP)
THEME = Setting.choice(
    key="appearance.theme", label="Theme", help=HELP, options=[("dark", "Dark")],
    default="dark", where=Where.BROWSER,
)
LATER = Setting.toggle(
    key="building.later", label="Later", help=HELP, default=False,
    unavailable=Designed(where="arrives with 14.7.8"),
)
CATALOGUE = Catalogue(
    sections=(
        Section(key="building", title="Building", order=2, settings=(PACING, LATER)),
        Section(key="models", title="Models", order=3, settings=(KEY,)),
        Section(key="appearance", title="Appearance", order=1, settings=(THEME,)),
    )
)


REVERSING = Reversing()


def _installation(env=None, codec=REVERSING):
    return Installation(CATALOGUE, MemoryStore(), env or {}, codec=codec)


def test_a_put_is_read_back_with_its_source_and_who():
    inst = _installation()
    shown = inst.put("building.pacing", "together", by="someone")
    assert (shown.value, shown.source) == ("together", "installation")
    assert inst.get(PACING) == "together"
    assert inst.store.by["building.pacing"] == "someone"


def test_a_locked_setting_refuses_a_put_and_says_why():
    inst = _installation(env={"COMENI_BUILD_PACING": "together"})
    with pytest.raises(SettingLocked) as refused:
        inst.put("building.pacing", "ask", by="someone")
    assert refused.value.reason.kind == "pinned"
    assert inst.store.rows == {}


def test_a_designed_setting_refuses_a_put():
    with pytest.raises(SettingLocked):
        _installation().put("building.later", True, by="someone")


def test_an_illegal_value_is_refused_and_nothing_is_stored():
    inst = _installation()
    with pytest.raises(IllegalValue):
        inst.put("building.pacing", "sometimes", by="someone")
    assert inst.store.rows == {}


def test_an_unknown_key_is_a_key_error():
    with pytest.raises(KeyError):
        _installation().put("building.nothing", 1, by="someone")


def test_a_browser_setting_is_never_stored_on_the_server():
    with pytest.raises(SettingLocked):
        _installation().put("appearance.theme", "dark", by="someone")


def test_a_secret_is_sealed_in_the_store_and_opened_for_the_code_that_uses_it():
    inst = _installation()
    inst.put("models.key", "sk-abcdef1234", by="someone")
    assert inst.store.rows["models.key"] != "sk-abcdef1234"
    assert inst.get(KEY) == "sk-abcdef1234"


def test_a_secret_is_shown_as_set_and_its_last_four_never_its_value():
    inst = _installation()
    shown = inst.put("models.key", "sk-abcdef1234", by="someone")
    assert (shown.value, shown.set, shown.last4) == (None, True, "1234")
    assert "sk-abcdef1234" not in inst.menu().model_dump_json()


def test_an_unset_secret_is_shown_as_not_set():
    shown = _installation().shown(KEY)
    assert (shown.value, shown.set, shown.last4) == (None, False, None)


def test_a_secret_without_a_codec_is_locked_with_its_reason():
    inst = _installation(codec=None)
    assert inst.shown(KEY).locked
    with pytest.raises(SettingLocked):
        inst.put("models.key", "sk-abcdef1234", by="someone")


def test_the_menu_is_every_section_in_order_with_every_setting():
    menu = _installation().menu()
    assert [s.key for s in menu.sections] == ["appearance", "building", "models"]
    entries = [e for s in menu.sections for e in s.entries]
    assert entries, "the menu is empty — this test is measuring nothing"
    assert {e.setting.key for e in entries} == {s.key for s in CATALOGUE.settings()}


def test_the_store_is_read_on_every_use():
    """Never cached: a change in the menu applies to the next call, in every process."""
    inst = _installation()
    inst.store.rows["building.pacing"] = "together"
    assert inst.get(PACING) == "together"


def test_a_secret_the_codec_cannot_open_is_shown_as_not_set():
    class Forgetful(Reversing):
        def open(self, sealed):
            return ""

    inst = Installation(CATALOGUE, MemoryStore(), {}, codec=Forgetful())
    inst.store.rows["models.key"] = "sealed:anything"
    shown = inst.shown(KEY)
    assert (shown.set, shown.last4) == (False, None)
