"""A130 — the artifact can state that no model was consulted.

The design audit's row: *the artifact cannot state that no model was consulted; `resolved_by`
and `confidence` are the resolver's claims about itself.* Under the engine decision of
2026-08-14, where the primary operator is an AI, that stops being a legibility gap and becomes a
gap in the protection profiles — `guarded` and `sealed` both require attribution.

Two fields, because the per-value answer and the "none" answer need different evidence.
`ValueSource.MODEL` is the per-value answer and is a *claim*; `Pipeline.ai.available` is a fact
about how the build was configured, and is what makes "none" trustworthy.
"""

import pathlib

import pytest
import yaml
from comeni_core.artifact.pipeline import AiPoint, Pipeline
from pydantic import ValidationError

ROOT = pathlib.Path(__file__).parent.parent


def _claim_a_model(raw: dict) -> str:
    """Mark the first setting that exists as model-authored, and return its key."""
    for step in raw["steps"]:
        for setting in step["settings"]:
            setting["why"]["source"] = "model"
            return f"{step['id']}.{setting['name']}"
    raise AssertionError("the built pipeline has no settings to mark")


def _built(tmp_path: pathlib.Path) -> Pipeline:
    from mendel_compiler.cli import main

    out = tmp_path / "build"
    assert main([
        "build", "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(out), "--root", str(ROOT), "--gate", "lint",
    ]) == 0
    return Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))


def test_a_build_states_that_no_model_was_consulted(tmp_path):
    """Through Plan 1 nothing is wired to a model, so both lists are empty — and empty is a
    statement, not an absence."""
    pipeline = _built(tmp_path)
    assert pipeline.ai.available == []
    assert pipeline.ai.used == []


def test_MD0225_a_value_cannot_claim_a_model_that_was_not_available(tmp_path):
    """The checkable half of A130. The other half is documented on `AiProvenance`."""
    pipeline = _built(tmp_path)
    raw = pipeline.model_dump(mode="json")
    key = _claim_a_model(raw)
    with pytest.raises(ValidationError) as caught:
        Pipeline.model_validate(raw)
    assert "MD0225" in str(caught.value)
    assert key in str(caught.value), "the refusal must name which value claims it"


def test_a_file_from_before_the_question_states_nothing(tmp_path):
    """Absence and emptiness differ — the lesson `for_value` taught in #48, one field over.

    A `version: 3` artifact was written before anything asked about models. Loading it as
    `available: []` would invent a statement nobody made, and `MD0225` would then be
    enforcing it.
    """
    pipeline = _built(tmp_path)
    raw = pipeline.model_dump(mode="json")
    raw["version"] = 3
    del raw["ai"]
    older = Pipeline.model_validate(raw)
    assert older.ai.available is None
    assert older.ai.used is None


def test_a_pre_ai_file_claiming_a_model_is_not_refused(tmp_path):
    """`MD0225` fires on `available == []`, never on `None`. A v3 file makes no claim about
    what was available, so it cannot contradict one."""
    pipeline = _built(tmp_path)
    raw = pipeline.model_dump(mode="json")
    raw["version"] = 3
    del raw["ai"]
    _claim_a_model(raw)
    Pipeline.model_validate(raw)  # must not raise


def test_the_three_ai_points_are_the_three_invariant_3_declares():
    """Invariant 3: runtime AI is confined to three declared points. If a fourth is added to
    this enum, the invariant moved and this test is where somebody has to say so."""
    assert [point.value for point in AiPoint] == ["prompt", "tier-4", "repair"]
