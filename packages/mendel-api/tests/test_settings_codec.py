"""The secret codec: Fernet, keyed by COMENI_SETTINGS_KEY (spec §8)."""

import pytest
from cryptography.fernet import Fernet
from mendel_api.services.settings_codec import (
    FernetCodec,
    Tolerant,
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


def test_tolerant_turns_an_unreadable_secret_into_nothing():
    sealed = FernetCodec(Fernet.generate_key().decode()).seal("sk-old")
    assert Tolerant(FernetCodec(KEY)).open(sealed) == ""


def test_the_codec_never_prints_its_key():
    codec = FernetCodec(KEY)
    assert KEY not in repr(codec) and KEY not in str(codec)
