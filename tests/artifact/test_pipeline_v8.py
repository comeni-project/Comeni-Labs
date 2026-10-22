"""`pipeline.yml` version 8: what was wanted and what is known, at the top (Part I.0 Plan B,
spec §8.1), whose constraints may carry a person's structural intent (A1). Only version 8
is read: before v0.1.0 an older file is rebuilt, not upgraded."""

import pytest
import yaml
from comeni_core.artifact.pipeline import Pipeline
from pydantic import ValidationError
from support.paths import ROOT
from support.pipeline import _build

V8 = ROOT / "tests" / "fixtures" / "pipeline-v8" / "pipeline.yml"
EXAMPLE_NF = ROOT / "tests" / "golden" / "example" / "main.nf"


def test_a_v8_file_puts_intent_and_facts_first(tmp_path):
    out = _build(tmp_path)
    keys = list(yaml.safe_load((out / "pipeline.yml").read_text()))
    assert keys[:3] == ["version", "intent", "facts"]
    assert "goal" not in keys


def _without_checkout(text: str) -> dict:
    """A file without what depends on the registry checkout (layer digests and locators) or
    follows from it (the emitted digests)."""
    document = yaml.safe_load(text)
    document["registry"]["layers"] = [layer["name"] for layer in document["registry"]["layers"]]
    document.pop("emitted")
    return document


def test_the_golden_v7_file_is_what_the_example_builds(tmp_path):
    out = _build(tmp_path)
    built = _without_checkout((out / "pipeline.yml").read_text())
    assert built == _without_checkout(V8.read_text())


def test_the_example_still_emits_what_it_did_before_version_7(tmp_path):
    """Same analysis, byte-identical `.nf` across the change (invariant 10)."""
    out = _build(tmp_path)
    assert (out / "main.nf").read_text() == EXAMPLE_NF.read_text()


@pytest.mark.parametrize("version", [1, 5, 6, 7])
def test_an_older_file_is_refused_and_told_to_rebuild(version):
    raw = yaml.safe_load(V8.read_text())
    raw["version"] = version
    with pytest.raises(ValidationError, match="MD0207.*Rebuild it"):
        Pipeline.model_validate(raw)


def test_a_newer_file_is_refused_and_told_to_upgrade_mendel():
    raw = yaml.safe_load(V8.read_text())
    raw["version"] = 9
    with pytest.raises(ValidationError, match="MD0207.*Upgrade Mendel"):
        Pipeline.model_validate(raw)
