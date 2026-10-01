"""The installation facade: reading, writing, secrets and the served menu (spec §4, §8)."""

import pytest
from comeni_core.settings import ReadOnlyHere, Source
from comeni_core.settings.declare import FROM_ENV, EnvItem, IllegalValue, Setting, Where
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
    assert inst.get(KEY).get_secret_value() == "sk-abcdef1234"


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


def test_a_secret_the_codec_cannot_open_is_not_set_and_says_why():
    """A rotated key (review I2): not set, and a reason naming the key — never a 500."""

    class Rotated(Reversing):
        def open(self, sealed):
            raise ValueError("sealed under another key")

    inst = Installation(CATALOGUE, MemoryStore(), {}, codec=Rotated())
    inst.store.rows["models.key"] = "sealed:anything"
    shown = inst.shown(KEY)
    assert (shown.set, shown.last4) == (False, None)
    assert shown.reason is not None and "COMENI_SETTINGS_KEY" in shown.reason.what


def test_a_secret_is_handed_over_hidden():
    """Spec §8 (review I3): the plaintext travels in a type that prints as hidden."""
    inst = _installation()
    inst.put("models.key", "sk-abcdef1234", by="someone")
    secret = inst.get(KEY)
    assert "sk-abcdef1234" not in repr(secret) and "sk-abcdef1234" not in str(secret)
    assert secret.get_secret_value() == "sk-abcdef1234"


def test_a_short_secret_shows_no_last_four():
    """Review M2, re-graded: the last four of a short key is most of the key."""
    shown = _installation().put("models.key", "sk-12345", by="someone")
    assert (shown.set, shown.last4) == (True, None)


def test_why_secrets_cannot_be_stored_can_be_said_precisely():
    """Review I1: a malformed COMENI_SETTINGS_KEY must not read as a missing one."""
    inst = Installation(
        CATALOGUE, MemoryStore(), {}, codec=None,
        secrets_need="COMENI_SETTINGS_KEY in .env is not a Fernet key",
    )
    assert inst.shown(KEY).reason.what == "COMENI_SETTINGS_KEY in .env is not a Fernet key"


def test_a_setting_another_server_serves_is_never_written_here():
    """Review I4: a PUT to Wiener's setting through Mendel would be a control that does nothing."""
    running = Setting.toggle(key="running.flag", label="Flag", help=HELP, default=False)
    catalogue = Catalogue(
        sections=(Section(key="running", title="Running", order=1, served_by="wiener",
                          settings=(running,)),)
    )
    inst = Installation(catalogue, MemoryStore(), {}, codec=REVERSING)
    with pytest.raises(SettingLocked) as refused:
        inst.put("running.flag", True, by="someone")
    assert refused.value.reason.kind == "read_only_here"
    assert inst.store.rows == {}


CONNECTIONS = Setting.collection(
    key="models.connections", label="Connections", help=HELP,
    fields=(
        Setting.text(key="connection.name", label="Name", help=HELP),
        Setting.text(key="connection.endpoint", label="Endpoint", help=HELP),
        Setting.secret(key="connection.key", label="Key", help=HELP),
    ),
    from_env=EnvItem(
        name=FROM_ENV, present_when="COMENI_AI_MODEL",
        fields={"endpoint": "COMENI_AI_BASE_URL", "key": "COMENI_AI_API_KEY"},
    ),
)
WANT = Setting.model(key="models.want", label="Want", help=HELP, of="models.connections")
WHERE = Setting.readonly(
    key="models.where", label="Where", help=HELP, unavailable=ReadOnlyHere(why="worked out"),
)
MODELS = Catalogue(
    sections=(Section(key="models", title="Models", order=1, settings=(CONNECTIONS, WANT, WHERE)),)
)
LOCAL = {"name": "Local", "endpoint": "http://ollama:11434", "key": None}


def _models(env=None, codec=REVERSING, reporters=None):
    return Installation(MODELS, MemoryStore(), env or {}, codec, reporters=reporters)


def test_the_env_record_comes_first_and_locked():
    inst = _models(env={"COMENI_AI_MODEL": "ollama_chat/gemma3:12b", "COMENI_AI_BASE_URL": "http://o"})
    inst.put("models.connections", [LOCAL], by="a")
    records = inst.shown(CONNECTIONS).value
    assert [r["name"] for r in records] == [FROM_ENV, "Local"]
    assert records[0]["locked"] is True and "locked" not in records[1]


def test_a_put_never_stores_the_env_record():
    inst = _models(env={"COMENI_AI_MODEL": "m"})
    inst.put("models.connections", [{"name": FROM_ENV, "endpoint": "x"}, LOCAL], by="a")
    assert [r["name"] for r in inst.store.rows["models.connections"]] == ["Local"]


def test_a_record_key_is_sealed_kept_on_null_and_cleared_on_empty():
    inst = _models()
    inst.put("models.connections", [{**LOCAL, "key": "sk-abcdef1234"}], by="a")
    sealed = inst.store.rows["models.connections"][0]["key"]
    assert sealed != "sk-abcdef1234"
    inst.put("models.connections", [{**LOCAL, "endpoint": "http://new"}], by="a")
    assert inst.store.rows["models.connections"][0]["key"] == sealed
    assert inst.record(CONNECTIONS, "Local")["key"].get_secret_value() == "sk-abcdef1234"
    inst.put("models.connections", [{**LOCAL, "key": ""}], by="a")
    assert inst.store.rows["models.connections"][0]["key"] is None


def test_a_record_key_is_shown_masked():
    inst = _models()
    inst.put("models.connections", [{**LOCAL, "key": "sk-abcdef1234"}], by="a")
    shown = inst.shown(CONNECTIONS).value[0]
    assert shown["key"] == {"set": True, "last4": "1234"}  # 13 characters: past the floor
    assert "sk-abcdef1234" not in inst.menu().model_dump_json()


def test_a_record_key_without_a_codec_is_refused():
    with pytest.raises(SettingLocked):
        _models(codec=None).put("models.connections", [{**LOCAL, "key": "sk-1"}], by="a")


def test_the_env_record_key_comes_from_env():
    inst = _models(env={"COMENI_AI_MODEL": "m", "COMENI_AI_API_KEY": "sk-env-0000-9999"})
    assert inst.record(CONNECTIONS, FROM_ENV)["key"].get_secret_value() == "sk-env-0000-9999"
    assert inst.shown(CONNECTIONS).value[0]["key"] == {"set": True, "last4": "9999"}


def test_a_model_naming_a_gone_connection_needs_another():
    inst = _models()
    inst.put("models.connections", [LOCAL], by="a")
    inst.put("models.want", {"connection": "Local", "model": "ollama_chat/gemma3:4b"}, by="a")
    inst.put("models.connections", [], by="a")
    got = inst.resolved(WANT)
    assert (got.value, got.locked) == (None, False)
    assert "Local" in got.reason.what


def test_a_model_cannot_be_put_naming_a_connection_that_does_not_exist():
    with pytest.raises(IllegalValue, match="Nowhere"):
        _models().put("models.want", {"connection": "Nowhere", "model": "m"}, by="a")


def test_a_reported_value_comes_from_its_reporter():
    inst = _models(reporters={"models.where": lambda: [{"purpose": "Want", "goes": "here"}]})
    got = inst.resolved(WHERE)
    assert (got.source, got.locked) == (Source.REPORTED, True)
    assert got.value == [{"purpose": "Want", "goes": "here"}]


def test_a_reporter_that_raises_is_a_row_that_says_so():
    def broken():
        raise ConnectionError("redis://localhost:6379 refused")

    inst = _models(reporters={"models.where": broken})
    got = inst.resolved(WHERE)
    assert got.locked and got.value == "could not be read (ConnectionError)"
    assert "6379" not in str(got.value)
