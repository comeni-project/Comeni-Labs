"""Settings: declarations, and the reasons a setting is greyed out (spec §4, §5)."""

import pytest
from comeni_core.settings.declare import IllegalValue, Kind, Setting, Where
from comeni_core.settings.reasons import (
    REASON_KINDS,
    Designed,
    Needs,
    Pinned,
    ReadOnlyHere,
    Reason,
)
from pydantic import TypeAdapter, ValidationError


def test_every_reason_says_something_a_person_can_read():
    reasons = [
        Pinned(env="COMENI_AI_MODEL"),
        Designed(where="arrives with the consultant build"),
        Needs(what="choose a connection first"),
        ReadOnlyHere(why="Wiener reads this from its own .env"),
    ]
    assert reasons, "no reasons were built — this test is measuring nothing"
    for reason in reasons:
        assert len(reason.says) > 20, reason
    assert "COMENI_AI_MODEL" in reasons[0].says


def test_the_list_is_closed():
    """A fifth kind is a change to `reasons.py`, never a string somebody invents."""
    assert REASON_KINDS == ("pinned", "designed", "needs", "read_only_here")
    with pytest.raises(ValidationError):
        TypeAdapter(Reason).validate_python({"kind": "because", "why": "x"})


def test_a_reason_round_trips_through_json():
    adapter = TypeAdapter(Reason)
    reason = Needs(what="set COMENI_SETTINGS_KEY")
    assert adapter.validate_json(adapter.dump_json(reason)) == reason



HELP = "How the build walks you through its steps, one at a time or all at once."


def _pacing(**over):
    fields = {
        "key": "building.pacing",
        "label": "Pacing",
        "help": HELP,
        "options": [("together", "Go through it together"), ("ask", "Ask me every time")],
        "default": "ask",
        "env": "COMENI_BUILD_PACING",
    }
    return Setting.choice(**{**fields, **over})


def test_a_choice_accepts_only_its_options():
    pacing = _pacing()
    assert pacing.kind is Kind.CHOICE
    assert pacing.check("together") == "together"
    with pytest.raises(IllegalValue, match="not one of"):
        pacing.check("sometimes")


def test_a_default_outside_the_options_cannot_be_declared():
    with pytest.raises(ValidationError, match="default"):
        _pacing(default="sometimes")


def test_help_is_required_and_says_something():
    with pytest.raises(ValidationError, match="help"):
        Setting.toggle(key="a.b", label="B", help="short", default=False)


def test_a_key_is_dotted_and_lower_case():
    with pytest.raises(ValidationError, match="key"):
        Setting.toggle(key="Pacing", label="B", help=HELP, default=False)


def test_a_number_respects_its_bounds_and_refuses_a_bool():
    lost = Setting.number(
        key="running.lost_after", label="Lost after", help=HELP, default=30, minimum=1, maximum=600
    )
    assert lost.check(45) == 45
    for bad in (0, 601, True, "45"):
        with pytest.raises(IllegalValue):
            lost.check(bad)


def test_a_toggle_reads_the_usual_spellings_from_env():
    flag = Setting.toggle(key="privacy.telemetry", label="T", help=HELP, default=False)
    assert flag.parse_env("true") is True and flag.parse_env("0") is False
    with pytest.raises(IllegalValue):
        flag.parse_env("maybe")


def test_a_number_reads_an_integer_from_env_as_an_int():
    n = Setting.number(key="a.n", label="N", help=HELP, default=1)
    assert n.parse_env("30") == 30 and isinstance(n.parse_env("30"), int)
    assert n.parse_env("0.5") == 0.5


def test_a_secret_has_no_default():
    with pytest.raises(ValidationError, match="secret"):
        Setting(key="a.k", label="K", help=HELP, kind=Kind.SECRET, default="sk-123")
    key = Setting.secret(key="models.key", label="Key", help=HELP)
    assert key.default is None
    with pytest.raises(IllegalValue):
        key.check("")


def test_a_browser_setting_cannot_be_pinned_by_the_server():
    with pytest.raises(ValidationError, match="browser"):
        Setting.choice(
            key="appearance.theme", label="Theme", help=HELP, options=[("dark", "Dark")],
            default="dark", where=Where.BROWSER, env="COMENI_THEME",
        )


def test_a_readonly_setting_can_never_be_written():
    shown = Setting.readonly(key="system.version", label="Version", help=HELP, default="0.1.0")
    with pytest.raises(IllegalValue, match="read-only"):
        shown.check("0.2.0")


def test_options_belong_to_choices_only():
    with pytest.raises(ValidationError, match="options"):
        Setting(key="a.t", label="T", help=HELP, kind=Kind.TEXT, default="", options=(("a", "A"),))
