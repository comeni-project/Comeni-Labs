"""Recorded fixtures, so a contract test can run offline and forever.

A recording is keyed by a digest of the prompt, not by call order: a test that adds a call at
the front must not silently re-point every later assertion at the wrong answer.
"""

import json
from pathlib import Path

import pytest
from mendel_ai.access import ModelAccess
from mendel_ai.choice import Option, choose_one
from mendel_ai.client import Client
from mendel_ai.recorded import RecordedTransport, key_for

ACCESS = ModelAccess(model="test/model")
FIXTURES = Path(__file__).parent / "fixtures"


def test_a_recorded_prompt_replays(tmp_path: Path) -> None:
    prompt = "which role?"
    path = tmp_path / "f.json"
    path.write_text(json.dumps({key_for(ACCESS, prompt): "an answer"}))
    assert RecordedTransport(path).send(ACCESS, prompt) == "an answer"


def test_an_unrecorded_prompt_fails_loudly_naming_its_key(tmp_path: Path) -> None:
    """Silence here would mean a test passing against a fixture for a different question."""
    path = tmp_path / "f.json"
    path.write_text("{}")
    with pytest.raises(KeyError) as raised:
        RecordedTransport(path).send(ACCESS, "unrecorded")
    assert key_for(ACCESS, "unrecorded") in str(raised.value)


def test_the_failure_prints_the_prompt_it_wanted(tmp_path: Path) -> None:
    """A key alone cannot be diffed against the prompt that moved."""
    path = tmp_path / "f.json"
    path.write_text("{}")
    with pytest.raises(KeyError) as raised:
        RecordedTransport(path).send(ACCESS, "a distinctive question")
    assert "a distinctive question" in str(raised.value)


def test_the_key_depends_on_the_model_as_well_as_the_prompt() -> None:
    """The same question to two models is two recordings."""
    other = ModelAccess(model="other/model")
    assert key_for(ACCESS, "q") != key_for(other, "q")


def test_the_key_is_not_positional() -> None:
    """The whole reason for a digest: order must not address a recording."""
    assert key_for(ACCESS, "first") != key_for(ACCESS, "second")
    assert key_for(ACCESS, "first") == key_for(ACCESS, "first")


def test_the_committed_fixture_drives_a_real_choose() -> None:
    """The contract test: the shipped fixture, through the real Client and real choose_one."""
    client = Client(ACCESS, transport=RecordedTransport(FIXTURES / "roles-fastqc.json"))
    picked = choose_one(
        client,
        "Which role does this tool play?",
        [Option(value="qc_per_sample", note="declared role"), Option(value="aligner")],
        ["FASTQC in main.nf:3"],
    )
    assert picked is not None
    assert picked.value == "qc_per_sample"
    assert "per-sample" in picked.why

