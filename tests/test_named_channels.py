"""A channel has a name, and a pipeline that predates that gets one assigned rather than guessed.

Plan 5B phase 2. **`StepInput.channel` was a `TypeId`**, so a channel's identity *was* its type:
two `annotation.gtf` inputs were one `params.gtf`, and a GTF could not vary per sample. That is
the defect the whole plan is about, and this phase is the rename that makes two of one type
addressable — with no behaviour change, which is what makes the diff readable.
"""

import pathlib
import subprocess

import pytest
import yaml
from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline
from mendel_compiler import pipeline_file
from mendel_compiler.emit import emit

ROOT = pathlib.Path(__file__).parent.parent


def _build(out: pathlib.Path) -> pathlib.Path:
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", "examples/rnaseq-goal.yml",
         "--registry", "registry", "--out", str(out)],
        check=True, cwd=ROOT, capture_output=True,
    )
    return out / "pipeline.yml"


def test_the_shipped_params_did_not_move(tmp_path):
    """**The property phase 2 has to preserve.** `entry_param` is declared per type rather than
    derived precisely so this holds: `genome.fasta` arrives as `params.fasta` and
    `annotation.gtf` as `params.gtf`, both derivable from the last segment — but `fastq.reads`
    arrives as `params.input`, nf-core's name for the samplesheet and not this type's name.

    A derivation would have renamed it, and a rename here is every laboratory's command line
    changing under them.
    """
    pipeline = pipeline_file.load(_build(tmp_path / "b"))
    assert {c.type_id: c.param for c in pipeline.channels} == {
        "fastq.reads": "input",
        "genome.fasta": "fasta",
        "annotation.gtf": "gtf",
    }
    assert "params.input" in emit(pipeline)


def test_a_channel_is_named_from_the_full_type_id(tmp_path):
    """Not the last segment. `qc.report` and `multiqc.report` both end in `report`, and deriving
    from the last segment made both `report` — one assignment shadowed the other and two ports
    were fed the same channel, silently."""
    pipeline = pipeline_file.load(_build(tmp_path / "b"))
    assert sorted(c.name for c in pipeline.channels) == [
        "annotation_gtf", "fastq_reads", "genome_fasta",
    ]


def test_two_channels_sharing_a_name_are_refused(tmp_path):
    """MD0226 — **a derived value that can collide needs a check, not a convention.**"""
    doc = yaml.safe_load(_build(tmp_path / "b").read_text())
    doc["channels"][1]["name"] = doc["channels"][0]["name"]
    with pytest.raises(ValueError, match="MD0226"):
        Pipeline.model_validate(doc)


def test_a_step_reading_an_undeclared_channel_is_refused(tmp_path):
    """MD0227. A dangling reference emits Groovy naming a variable nothing assigned, which fails
    at launch with a message about Nextflow rather than about the artifact somebody edited."""
    doc = yaml.safe_load(_build(tmp_path / "b").read_text())
    for step in doc["steps"]:
        for one in step["inputs"]:
            if one.get("channel"):
                one["channel"] = "no_such_channel"
                break
    with pytest.raises(ValueError, match="MD0227"):
        Pipeline.model_validate(doc)


def test_a_v5_artifact_still_loads_and_emits_the_same_nextflow(tmp_path):
    """**In the loader, not a script somebody has to remember to run.**

    A laboratory holding a v5 `pipeline.yml` runs `mendel emit` on it and it works, which is
    what *the artifact is the pipeline* has to mean. The names the migration assigns are the ones
    that file's behaviour already had: a v5 file has one channel per type and `inputs[].channel`
    holds a type id, so the channel a port reads is unambiguous.
    """
    current = pipeline_file.load(_build(tmp_path / "b"))
    fresh = emit(current)

    # Turn it back into what a v5 file looked like: no `name`, no `param`, and references by
    # type. The migration has to recover exactly what was lost.
    doc = yaml.safe_load((tmp_path / "b" / "pipeline.yml").read_text())
    doc["version"] = 5
    by_name = {c["name"]: c["type_id"] for c in doc["channels"]}
    for channel in doc["channels"]:
        channel.pop("name")
        channel.pop("param")
    for step in doc["steps"]:
        for one in step["inputs"]:
            if one.get("channel"):
                one["channel"] = by_name[one["channel"]]

    migrated = Pipeline.model_validate(doc)
    assert emit(migrated) == fresh, (
        "a migrated v5 artifact emits different Nextflow from the v6 it was made from — the "
        "migration guessed rather than recovering what the file already meant"
    )
    assert {c.type_id: c.param for c in migrated.channels} == {
        c.type_id: c.param for c in current.channels
    }


def test_the_migration_reads_the_param_out_of_the_expression(tmp_path):
    """**Not derived from the type**, which is the whole reason it can be byte-identical.

    A v5 expression hard-codes `params.input` for `fastq.reads`, which no derivation from
    `fastq.reads` produces. `Channel.params` already records which `params.<x>` the expression
    references — stored *and* derivable, with `MD0211` keeping the two honest — so the parameter
    that file actually used is right there in the document.
    """
    doc = yaml.safe_load(_build(tmp_path / "b").read_text())
    doc["version"] = 5
    for channel in doc["channels"]:
        channel.pop("name")
        channel.pop("param")
    by_name = {c["type_id"].replace(".", "_"): c["type_id"] for c in doc["channels"]}
    for step in doc["steps"]:
        for one in step["inputs"]:
            if one.get("channel"):
                one["channel"] = by_name[one["channel"]]

    migrated = Pipeline.model_validate(doc)
    assert next(c.param for c in migrated.channels if c.type_id == "fastq.reads") == "input"


def test_an_entry_channel_with_no_placeholder_is_refused(tmp_path):
    """MD0228, and **carrying on quietly would silently merge two inputs** — the defect this
    whole plan exists to remove.

    A type whose expression hard-codes `params.reads` gives every input of that type the same
    parameter, so a pipeline taking a tumour and a normal FASTQ takes one FASTQ twice and
    nothing says so.

    Refused at **load** rather than at emit, because a registry is a thing a laboratory installs
    and the useful moment to hear about it is the one where they can still choose a different
    version.
    """
    from mendel_resolver import layers

    layer = tmp_path / "old"
    layer.mkdir()
    (layer / "registry.yml").write_text("name: old\n")
    (layer / "fastq.reads.yml").write_text(
        "declares: vocabulary\nid: fastq.reads\nstates: []\n"
        'entry_channel: "Channel.fromFilePairs(params.reads)"\n'
    )
    with pytest.raises(ValueError, match="MD0228"):
        layers.load(layer)


def test_the_current_schema_is_what_this_test_was_written_against():
    """A guard-of-the-guard: the migration above is version-keyed, so a schema bump that does not
    update it would leave these tests exercising a branch nothing takes."""
    assert SCHEMA_VERSION == 6
