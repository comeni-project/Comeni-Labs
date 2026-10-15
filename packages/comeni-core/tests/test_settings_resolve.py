"""The resolver: one case per layer path (spec §3, §9)."""

from comeni_core.settings.declare import Setting
from comeni_core.settings.reasons import Designed, Needs, Pinned, ReadOnlyHere
from comeni_core.settings.resolve import SETTINGS_KEY_ENV, Source, resolve

HELP = "How the build walks you through its steps, one at a time or all at once."
PACING = Setting.choice(
    key="building.pacing", label="Pacing", help=HELP,
    options=[("together", "Together"), ("ask", "Ask")], default="ask", env="COMENI_BUILD_PACING",
)
KEY = Setting.secret(key="models.key", label="Key", help=HELP, env="COMENI_AI_API_KEY")


def test_nothing_set_is_the_default():
    got = resolve(PACING, {}, {})
    assert (got.value, got.source, got.locked, got.reason) == ("ask", Source.DEFAULT, False, None)


def test_the_menu_beats_the_default():
    got = resolve(PACING, {"building.pacing": "together"}, {})
    assert (got.value, got.source, got.locked) == ("together", Source.INSTALLATION, False)


def test_env_beats_the_menu_and_locks_it():
    got = resolve(PACING, {"building.pacing": "ask"}, {"COMENI_BUILD_PACING": "together"})
    assert (got.value, got.source, got.locked) == ("together", Source.ENVIRONMENT, True)
    assert got.reason == Pinned(env="COMENI_BUILD_PACING")


def test_an_empty_env_string_is_not_a_value():
    got = resolve(PACING, {"building.pacing": "together"}, {"COMENI_BUILD_PACING": "  "})
    assert got.source is Source.INSTALLATION


def test_an_illegal_env_value_locks_the_default_and_says_which_variable():
    got = resolve(PACING, {}, {"COMENI_BUILD_PACING": "purple"})
    assert (got.value, got.source, got.locked) == ("ask", Source.DEFAULT, True)
    assert isinstance(got.reason, Needs)
    assert "COMENI_BUILD_PACING" in got.reason.what and "purple" in got.reason.what


def test_a_stored_value_no_longer_legal_falls_back_to_the_default():
    got = resolve(PACING, {"building.pacing": "sometimes"}, {})
    assert (got.value, got.source, got.locked) == ("ask", Source.DEFAULT, False)


def test_designed_says_designed_even_when_env_is_set():
    designed = PACING.model_copy(update={"unavailable": Designed(where="arrives with 14.7.8")})
    got = resolve(designed, {"building.pacing": "together"}, {"COMENI_BUILD_PACING": "together"})
    assert (got.value, got.locked, got.reason) == ("ask", True, designed.unavailable)


def test_read_only_here_still_shows_the_pinned_value():
    lost = Setting.readonly(
        key="running.lost_after", label="Lost after", help=HELP, default=30,
        env="WIENER_LOST_AFTER_MS", unavailable=ReadOnlyHere(why="Wiener reads its own .env"),
    )
    assert resolve(lost, {}, {}).reason == lost.unavailable
    pinned = resolve(lost, {}, {"WIENER_LOST_AFTER_MS": "900"})
    assert (pinned.value, pinned.reason) == ("900", Pinned(env="WIENER_LOST_AFTER_MS"))


def test_a_secret_without_a_codec_needs_the_settings_key():
    got = resolve(KEY, {"models.key": "sealed-token"}, {}, secrets_available=False)
    assert got.locked and got.value is None
    assert isinstance(got.reason, Needs) and SETTINGS_KEY_ENV in got.reason.what


def test_a_secret_pinned_in_env_needs_no_codec():
    got = resolve(KEY, {}, {"COMENI_AI_API_KEY": "sk-live"}, secrets_available=False)
    assert (got.value, got.source) == ("sk-live", Source.ENVIRONMENT)


def test_every_locked_result_carries_a_reason():
    cases = [
        resolve(PACING, {}, {"COMENI_BUILD_PACING": "together"}),
        resolve(PACING, {}, {"COMENI_BUILD_PACING": "purple"}),
        resolve(KEY, {}, {}, secrets_available=False),
    ]
    assert cases, "nothing was resolved — this test is measuring nothing"
    for got in cases:
        assert got.locked and got.reason is not None
