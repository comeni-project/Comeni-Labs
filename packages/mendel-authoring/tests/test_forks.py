"""A fork's subject: what it switches on, its cases, and the case a snapshot is in (spec §12.2)."""

from comeni_core.settings.declare import Setting
from mendel_authoring.forks import DEFAULT, SettingSubject, Snapshot

HELP = "A setting used by the fork tests."
PACING = Setting.choice(
    key="building.pacing",
    label="Pacing",
    help=HELP,
    options=[("together", "T"), ("stop_where_needed", "S"), ("ask", "A")],
    default="ask",
)
DEV = Setting.toggle(key="dev.mode", label="Dev mode", help=HELP, default=False)
NAME = Setting.text(key="dev.name", label="A name", help=HELP)


def test_a_choices_cases_are_its_option_values():
    subject = SettingSubject.of(PACING)
    assert subject.options() == {"together", "stop_where_needed", "ask"}
    assert subject.title == "Pacing"


def test_a_designed_option_is_still_a_case():
    """Review Focus 4: greyed in the menu, but a stored value may hold it once built."""
    greyed = Setting.choice(
        key="dev.greyed",
        label="K",
        help=HELP,
        options=[("a", "A"), ("b", "B")],
        designed={"b": "later"},
        default="a",
    )
    assert SettingSubject.of(greyed).options() == {"a", "b"}


def test_a_toggles_cases_are_on_and_off():
    assert SettingSubject.of(DEV).options() == {"on", "off"}


def test_any_other_kind_is_open():
    assert SettingSubject.of(NAME).options() is None


def test_the_snapshot_names_the_case():
    subject = SettingSubject.of(PACING)
    assert subject.value(Snapshot(settings={"building.pacing": "together"})) == "together"


def test_a_toggle_stored_as_a_bool_is_on_or_off():
    """Review Focus 1: the store holds a toggle as a bool."""
    subject = SettingSubject.of(DEV)
    assert subject.value(Snapshot(settings={"dev.mode": True})) == "on"
    assert subject.value(Snapshot(settings={"dev.mode": False})) == "off"


def test_a_setting_the_snapshot_lacks_takes_its_declared_default():
    """Review Focus 2: never set, so nothing is stored."""
    assert SettingSubject.of(PACING).value(Snapshot()) == "ask"
    assert SettingSubject.of(DEV).value(Snapshot()) == "off"


def test_a_title_can_be_given():
    assert SettingSubject.of(DEV, title="Dev mode?").title == "Dev mode?"


def test_default_is_a_case_no_option_can_be():
    assert DEFAULT == "*"
