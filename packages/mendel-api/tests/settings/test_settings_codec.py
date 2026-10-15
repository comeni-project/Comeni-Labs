"""The secret codec: Fernet, keyed by COMENI_SETTINGS_KEY (spec §8)."""

import pytest
from cryptography.fernet import Fernet
from mendel_api.services.settings_codec import (
    FernetCodec,
    UnreadableSecret,
    codec_from_env,
    key_problem,
)

KEY = Fernet.generate_key().decode()


def test_a_secret_round_trips_and_the_sealed_text_is_not_the_secret():
    codec = FernetCodec(KEY)
    sealed = codec.seal("sk-abcdef1234")
    assert "sk-abcdef1234" not in sealed
    assert codec.open(sealed) == "sk-abcdef1234"


def test_no_key_means_no_codec_and_no_problem_to_report():
    assert codec_from_env({}) is None
    assert key_problem({}) is None


def test_a_malformed_key_means_no_codec_and_says_why():
    env = {"COMENI_SETTINGS_KEY": "correct horse battery staple"}
    assert codec_from_env(env) is None
    assert "COMENI_SETTINGS_KEY" in key_problem(env)


def test_a_secret_sealed_under_another_key_is_unreadable():
    sealed = FernetCodec(Fernet.generate_key().decode()).seal("sk-old")
    with pytest.raises(UnreadableSecret):
        FernetCodec(KEY).open(sealed)


def test_the_codec_never_prints_its_key():
    codec = FernetCodec(KEY)
    assert KEY not in repr(codec) and KEY not in str(codec)


def test_the_installation_says_precisely_why_secrets_cannot_be_stored(monkeypatch):
    """Review I1: a malformed key reads as malformed, not as missing."""
    from mendel_api.services import installation as made

    monkeypatch.setenv("COMENI_SETTINGS_KEY", "correct horse battery staple")
    monkeypatch.setattr(made, "PostgresStore", lambda: None)
    inst = made.installation()
    assert inst.codec is None
    assert "not a Fernet key" in inst.secrets_need


def test_a_rotated_key_reaches_the_installation_as_an_error_not_an_empty_key(monkeypatch):
    """Review I2: the code that uses a key learns it cannot be read."""
    from mendel_api.services import installation as made

    monkeypatch.setenv("COMENI_SETTINGS_KEY", KEY)
    monkeypatch.setattr(made, "PostgresStore", lambda: None)
    sealed = FernetCodec(Fernet.generate_key().decode()).seal("sk-old")
    with pytest.raises(UnreadableSecret):
        made.installation().codec.open(sealed)
