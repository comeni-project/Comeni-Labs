"""A channel has a name, a port names one, and an upgrade renames nobody's command line.

Plan 5B phase 2, spec §1.1, §1.2 and §12.2.

**What the phase changes and what it must not.** `Channel` gains `name` and `param`;
`StepInput.channel` stops being a `TypeId` and becomes a `ChannelName`; `SCHEMA_VERSION` goes
5 → 6 with a migration in the loader. Every emitted `ch_*` variable moves — `ch_annotation_gtf`
is `ch_gtf` — and **nothing a laboratory types moves at all**, which is the line between a
rename and a break.

`tests/fixtures/pipeline-v5/` is a real schema-5 artifact, built by the schema-5 code at commit
`d8fd2be` and committed rather than generated here. A fixture produced by the code under test
cannot demonstrate anything about reading what a laboratory archived — the same argument as the
README beside `notes/audits/fixtures/pipeline-v1/`.
"""

import pathlib

import pytest
import yaml
from comeni_core.artifact.pipeline import SCHEMA_VERSION, Channel, Pipeline, StepInput
from mendel_compiler.cli import main
from mendel_compiler.emit import emit, entry_params

ROOT = pathlib.Path(__file__).parent.parent
V5 = ROOT / "tests" / "fixtures" / "pipeline-v5"


def _v5() -> Pipeline:
    return Pipeline.model_validate(yaml.safe_load((V5 / "pipeline.yml").read_text()))


# ═══ THE MIGRATION — spec §12.2 ═══════════════════════════════════════════════════════════


def test_a_v5_file_loads_and_is_stamped_as_the_version_it_now_is():
    """The shape is version 6 after the loader has run, so the number must say so.

    Leaving the number alone would produce an object claiming to be version 5 while carrying
    `name` and `param` on every channel — a file that could then be written back out as a
    version-5 document nothing could read.
    """
    assert yaml.safe_load((V5 / "pipeline.yml").read_text())["version"] == 5
    assert _v5().version == SCHEMA_VERSION


def test_the_migration_names_channels_the_way_a_fresh_build_does(tmp_path):
    """**§12.2's property, and the phase's real check.**

    `mendel upgrade` re-resolves against the current registry and replays every recorded
    decision, so only what you touched can move — issue #10 closed on that. If the migration's
    names and a fresh derivation's names differed by one, every `params.*` in a laboratory's
    command line would rename itself on an upgrade they asked for to pick up a registry fix.

    They cannot differ, because they are the same two functions in the same order —
    `materialise._stem` and `materialise._unique` over `sorted(type_id)`. This is that claim
    as a test rather than as an argument.
    """
    out = tmp_path / "upgraded"
    assert main(["upgrade", str(V5 / "pipeline.yml"), "--out", str(out), "--root", str(ROOT)]) == 0
    upgraded = Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))

    migrated = _v5()
    assert [(c.name, c.param, c.type_id) for c in migrated.channels] == [
        (c.name, c.param, c.type_id) for c in upgraded.channels
    ]


def test_upgrading_a_v5_artifact_renames_nothing_a_laboratory_types(tmp_path):
    """**The claim §12.2 is actually protecting**, stated over the command line.

    The plan asks for the emitted `.nf` to be *byte-identical to the v5 artifact's*, and that
    cannot hold in the one phase whose stated job is to rename every channel variable:
    `ch_annotation_gtf` is `ch_gtf` now, and the plan's own §2 says every golden file moves.

    What must not move is the interface — `params.*` — and it does not: a channel's `param` is
    the type's declared name, not its derived one, so `fastq.reads` keeps `params.input`. That
    is the difference between a rename and a break, and it is checkable where the other reading
    is not.
    """
    out = tmp_path / "upgraded"
    assert main(["upgrade", str(V5 / "pipeline.yml"), "--out", str(out), "--root", str(ROOT)]) == 0
    upgraded = Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))

    assert entry_params(upgraded) == entry_params(_v5())
    # And concretely, because a list comparison of two derived things can be vacuously equal.
    assert "input" in entry_params(upgraded)


def test_a_migrated_port_names_a_channel_rather_than_a_type():
    """§1.2. The v5 file says `channel: annotation.gtf`; a v6 port says `channel: gtf`.

    This is the change that makes two same-type inputs addressable, so a migration that left
    the reference as a type id would produce a file that loads (the string is still a legal
    identifier for some types) and wires nothing — which `MD0227` now refuses outright.
    """
    migrated = _v5()
    declared = {channel.name for channel in migrated.channels}
    referenced = {
        item.channel
        for step in migrated.steps
        for item in step.inputs
        if item.channel is not None
    }
    assert referenced
    assert referenced <= declared
    assert "annotation.gtf" not in referenced


def test_the_type_keeps_its_own_param_across_the_migration():
    """`fastq.reads` reads `params.input` and every other shipped type reads its last segment.

    Deriving the param from the channel name would have renamed it to `params.reads` inside a
    phase that is supposed to change no behaviour — and would have dissolved the ambiguity spec
    §12.1 says phase 5 has to solve.
    """
    by_type = {channel.type_id: channel for channel in _v5().channels}
    assert by_type["fastq.reads"].name == "reads"
    assert by_type["fastq.reads"].param == "input"
    assert by_type["annotation.gtf"].param == "gtf"


# ═══ MD0226 AND MD0227 ════════════════════════════════════════════════════════════════════


def _with_channels(pipeline: Pipeline, channels: list[Channel]) -> dict:
    data = pipeline.model_dump(mode="json")
    data["channels"] = [channel.model_dump(mode="json") for channel in channels]
    return data


def test_two_channels_sharing_a_name_are_refused():
    """MD0226. A derived value that can collide needs a check, not a convention.

    `qc.report` and `multiqc.report` both end in `report`, and `_channel_name`'s own docstring
    recorded that collision costing two ports the same channel *silently*.
    """
    pipeline = _v5()
    doubled = list(pipeline.channels) + [
        pipeline.channels[0].model_copy(update={"type_id": "qc.report"})
    ]
    with pytest.raises(ValueError, match="MD0226"):
        Pipeline.model_validate(_with_channels(pipeline, doubled))


def test_a_port_naming_no_declared_channel_is_refused():
    """MD0227. The reference can dangle now, which the type version could not — every type in
    a well-formed v5 file had exactly one channel. This is that cost, paid where it is loud."""
    pipeline = _v5()
    data = pipeline.model_dump(mode="json")
    for step in data["steps"]:
        for item in step["inputs"]:
            if item.get("channel") is not None:
                item["channel"] = "no_such_channel"
                break
        else:
            continue
        break
    with pytest.raises(ValueError, match="MD0227"):
        Pipeline.model_validate(data)


def test_a_channel_name_is_an_identifier_and_not_a_type_id():
    """`ChannelName` is `_identifier`, so the old spelling fails on the field.

    Stated separately from `MD0227` because they catch different mistakes: this one refuses
    `annotation.gtf` as a *shape*, and `MD0227` refuses `gtf_2` as a *reference to nothing*.
    A file hand-edited from a v5 one hits the first; one edited by somebody guessing at names
    hits the second.
    """
    with pytest.raises(ValueError):
        StepInput(port="gtf", channel="annotation.gtf")


def test_the_emitted_variable_is_the_channel_s_own_name(tmp_path):
    """`ch_<name>`, and the emitter derives nothing.

    Deriving a channel's identity in `emit._channel_name` is what made a channel a property of
    the type: two channels of one type had one name, one `params.*` and one hole, whatever the
    drawing said. The name is decided once, at materialisation, and recorded.
    """
    out = tmp_path / "upgraded"
    assert main(["upgrade", str(V5 / "pipeline.yml"), "--out", str(out), "--root", str(ROOT)]) == 0
    upgraded = Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))
    source = emit(upgraded)
    for channel in upgraded.channels:
        assert f"ch_{channel.name} =" in source
