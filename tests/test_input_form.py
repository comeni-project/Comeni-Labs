"""`params.input` has two meanings, and one artifact may claim only one.

Plan 5B phase 5.2. With a single sample-scoped channel `params.input` is a glob; with two or
more it is the path to a CSV whose columns are those channels, because *reads with their
respective annotations* is a table and not two globs.

**A glob and a CSV path are both a string**, so nothing downstream can tell them apart. Wiener
reads the artifact's nulls to ask a laboratory what to supply, and without this field it asks
the same question either way — somebody answers with the wrong kind of thing, the run fails
inside Nextflow minutes later, and the one place that could have said so is the form that asked.

**The choice is in the artifact and the sentence is generated.** §2.2 originally asked the
artifact to say which form it wants *"in words, next to the param"* — and `Pipeline` is door 4's
payload, so words next to a param is a **fifteenth free-text field**, in a spec whose §5 claims
it adds none. The general rule, worth carrying beyond this plan: when a fact is a closed choice,
put the choice in the artifact and generate the sentence.
"""

import pathlib
import subprocess

import pytest
import yaml
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.tiers import InputForm, Scope
from mendel_compiler import pipeline_file

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture(scope="module")
def spine(tmp_path_factory) -> Pipeline:
    out = tmp_path_factory.mktemp("input-form")
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", "examples/rnaseq-goal.yml",
         "--registry", "registry", "--out", str(out)],
        check=True, cwd=ROOT, capture_output=True,
    )
    return pipeline_file.load(out / "pipeline.yml")


def test_the_spine_is_direct_and_must_stay_that_way(spine):
    """**5.1's first bullet, and it is a regression guard.** One sample-scoped channel emits
    what it always emitted: `fromFilePairs`, one queue, no samplesheet.

    `tests/test_counts.py` is the only check exercising the v1 criterion and it runs this shape.
    """
    per_sample = [c.name for c in spine.channels if c.scope is Scope.SAMPLE]
    assert per_sample == ["reads"], f"the spine's sample-scoped channels moved: {per_sample}"
    assert spine.input_form is InputForm.DIRECT


def test_it_is_derived_and_not_authored(spine):
    """Two sample-scoped channels is a table; one is a glob. Nobody types this."""
    doc = yaml.safe_load(spine.model_dump_json())
    doc["channels"][0]["scope"] = "sample"
    doc["channels"][1]["scope"] = "sample"
    doc["input_form"] = "samplesheet"
    # Two sample-scoped channels *and* a samplesheet is the consistent pair, so this loads —
    # which is the check that the refusal below is about disagreement and not about counting.
    assert Pipeline.model_validate(doc).input_form is InputForm.SAMPLESHEET


def test_a_samplesheet_with_one_column_is_refused(spine):
    """MD0229. A table with one column is a glob written the long way, and saying it is a
    samplesheet would make Wiener ask for a CSV that has no reason to exist."""
    doc = yaml.safe_load(spine.model_dump_json())
    doc["input_form"] = "samplesheet"
    with pytest.raises(ValueError, match="MD0229"):
        Pipeline.model_validate(doc)


def test_two_channels_reading_one_parameter_are_refused(spine):
    """**What *claimed twice* actually means.** A laboratory supplies one path and both
    channels silently read it, which is the merge this plan exists to remove."""
    doc = yaml.safe_load(spine.model_dump_json())
    doc["channels"][1]["param"] = doc["channels"][0]["param"]
    with pytest.raises(ValueError, match="MD0229"):
        Pipeline.model_validate(doc)


def test_an_archived_v5_artifact_still_loads():
    """**The arm the plan asked for would have refused every pipeline ever written here.**

    §5.2 asks MD0229 to refuse *a non-samplesheet form with more than one sample-scoped
    channel*. Every archived schema-5 artifact has three channels with three parameters and no
    scope at all, so migration gives them the `SAMPLE` default — that arm refuses the lot, and
    `mendel emit` stops being able to read the artifacts it exists for.

    Sharing a *scope* is not claiming a parameter twice. This is the fixture that says so.
    """
    archived = ROOT / "tests" / "fixtures" / "pipeline" / "rnaseq-spine.yml"
    doc = yaml.safe_load(archived.read_text())
    assert doc["version"] == 5, "this fixture is the point; a v6 one proves nothing"

    loaded = Pipeline.model_validate(doc)
    assert loaded.input_form is InputForm.DIRECT
    assert len({c.param for c in loaded.channels}) == len(loaded.channels)


def test_the_words_are_generated_rather_than_authored():
    """The spec asked for prose in the artifact and that would have been a fifteenth free-text
    field. The choice is an enum; a reader's sentence is built from it and the channel names.

    Checked against the *schema*, because an optional prose field that happens to be empty in
    one fixture is exactly the shape that starts holding data later without anybody deciding.
    """
    schema = Pipeline.model_json_schema()
    field = schema["properties"]["input_form"]
    assert "$ref" in str(field) or "enum" in str(field), (
        "input_form is not a closed choice — a string here is how a boundary widens"
    )
    assert [c.value for c in InputForm] == ["direct", "samplesheet"]
