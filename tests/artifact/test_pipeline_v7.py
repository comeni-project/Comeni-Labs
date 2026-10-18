"""`pipeline.yml` version 7: what was wanted and what is known, at the top (Part I.0 Plan B,
spec §8.1, §8.3). A version-6 file upgrades in memory and emits exactly what it did."""

import pytest
import yaml
from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline
from comeni_core.goal.asked import Goal
from mendel_compiler import pipeline_file
from mendel_compiler.emit import emit
from pydantic import ValidationError
from support.paths import ROOT
from support.pipeline import _build

V6 = ROOT / "tests" / "fixtures" / "pipeline-v6"
V7 = ROOT / "tests" / "fixtures" / "pipeline-v7" / "pipeline.yml"


def _said(value):
    """The v6 goal as v7 reads it: a stated value's source is `said`."""
    if isinstance(value, dict):
        return {k: ("said" if k == "source" and v == "goal" else _said(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_said(v) for v in value]
    return value


def test_a_v7_file_puts_intent_and_facts_first(tmp_path):
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
    assert built == _without_checkout(V7.read_text())


def test_a_v6_file_upgrades_with_the_same_goal_and_nf():
    raw = yaml.safe_load((V6 / "pipeline.yml").read_text())
    assert raw["version"] == 6, "this fixture is the point; a v7 one proves nothing"
    loaded = pipeline_file.load(V6 / "pipeline.yml")
    assert loaded.version == SCHEMA_VERSION == 7
    assert loaded.goal == Goal.model_validate(_said(raw["goal"]))
    # In process: `mendel emit` also needs the fixture's `modules/`, which is not the subject.
    assert emit(loaded) == (V6 / "main.nf").read_text()


def test_the_example_still_emits_the_v6_nf(tmp_path):
    """Same goal, byte-identical `.nf` across the change (invariant 10)."""
    out = _build(tmp_path)
    assert (out / "main.nf").read_text() == (V6 / "main.nf").read_text()


def test_a_stamped_v6_file_predates_the_schema_not_hand_edited():
    loaded = pipeline_file.load(V6 / "pipeline.yml")
    assert pipeline_file.predates_schema(loaded) is True
    assert pipeline_file.hand_edited(V6, loaded) == []


def test_goal_beside_intent_is_refused():
    raw = yaml.safe_load((V6 / "pipeline.yml").read_text())
    raw["intent"] = {"want": ["counts.matrix"]}
    with pytest.raises(ValidationError, match="goal.*intent|intent.*goal"):
        Pipeline.model_validate(raw)
