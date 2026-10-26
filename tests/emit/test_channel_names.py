"""Channel names are unique identities used consistently by ports and emitted variables."""

import pytest
import yaml
from comeni_core.artifact.pipeline import Channel, Pipeline, StepInput
from comeni_core.declared.vocabulary import TypeDeclaration
from mendel_compiler.cli import main
from mendel_compiler.emit import emit
from mendel_resolver import layers
from support.paths import ROOT

SPINE = ROOT / "tests" / "fixtures" / "pipeline" / "rnaseq-spine.yml"


def _spine() -> Pipeline:
    return Pipeline.model_validate(yaml.safe_load(SPINE.read_text()))


def _with_channels(pipeline: Pipeline, channels: list[Channel]) -> dict:
    data = pipeline.model_dump(mode="json")
    data["channels"] = [channel.model_dump(mode="json") for channel in channels]
    return data


def test_two_channels_sharing_a_name_are_refused():
    """MD0226. A derived value that can collide needs a check, not a convention.

    `qc.report` and `multiqc.report` both end in `report`, and `_channel_name`'s own docstring
    recorded that collision costing two ports the same channel *silently*.
    """
    pipeline = _spine()
    doubled = list(pipeline.channels) + [
        pipeline.channels[0].model_copy(update={"type_id": "qc.report"})
    ]
    with pytest.raises(ValueError, match="MD0226"):
        Pipeline.model_validate(_with_channels(pipeline, doubled))


def test_a_port_naming_no_declared_channel_is_refused():
    """MD0227. The reference can dangle now, which a type could not: every type had exactly
    one channel. This is that cost, paid where it is loud."""
    pipeline = _spine()
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
    out = tmp_path / "built"
    assert main(["build", str(ROOT / "examples" / "rnaseq.yml"), "--out", str(out),
                 "--root", str(ROOT)]) == 0
    built = Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))
    source = emit(built)
    assert built.channels
    for channel in built.channels:
        assert f"ch_{channel.name} =" in source


# ═══ MD0228 AND THE TEMPLATE — spec §1.3, plan §2.2 and §2.6 ══════════════════════════════


def test_a_type_naming_a_param_literally_is_refused():
    """MD0228, and the message names the param it found.

    A literal fuses a PIPELINE decision into a TYPE: two channels of one type had one param
    and were therefore one hole, whatever the drawing said.
    """
    with pytest.raises(ValueError, match="MD0228"):
        TypeDeclaration(
            id="annotation.gtf",
            entry_channel="Channel.fromPath(params.gtf, checkIfExists: true)",
        )


def test_a_template_is_accepted_and_so_is_an_expression_reading_no_param():
    """Two passing cases, and the second is the one the first draft got wrong.

    `Channel.empty()` hardcodes nothing, so there is nothing for a pipeline to have been
    deprived of. Refusing it was a check firing on the absence of a placeholder rather than on
    the presence of a hardcoded name — which is not what the spec asks for and broke several
    fixtures exercising other diagnostics.
    """
    assert TypeDeclaration(
        id="annotation.gtf",
        entry_channel="Channel.fromPath(params.{param}, checkIfExists: true)",
    )
    assert TypeDeclaration(id="qc.report", entry_channel="Channel.empty()")


def test_a_template_that_also_names_one_literally_is_refused():
    """Half-migrated is refused, and it is the shape a hand-edit actually takes.

    `fastq.reads` reads its param three times in one expression. Converting two of them and
    missing the third produces a channel that is partly addressable, which is worse than
    either end state and would emit Groovy nobody could account for.
    """
    with pytest.raises(ValueError, match="MD0228"):
        TypeDeclaration(
            id="fastq.reads",
            entry_channel=(
                "( params.{param} instanceof List ? Channel.of(params.input) : "
                "Channel.fromFilePairs(params.{param}) )"
            ),
        )


def test_every_entry_channel_in_the_shipped_registry_is_a_template():
    """The registry side of §2.6, asserted here rather than trusted.

    The submodule is pinned, so this is a claim about the exact layer this build reads — and
    it is the check that would have caught a submodule bumped to a commit that predates the
    templates, which is a mistake with no other symptom until an emitted `.nf` is read.
    """
    loaded = layers.load(ROOT / "registry")
    assert loaded.vocabulary.entry_channels, "the registry declares entry channels"
    for type_id, expression in loaded.vocabulary.entry_channels.items():
        assert "{param}" in expression, f"{type_id} still names its param literally"


def test_substituting_every_type_yields_groovy_that_still_parses():
    """The plan's own check, made cheap: substitute a known param into every declared template
    and assert the result is balanced Groovy with no placeholder left in it.

    **Not `nextflow lint` on a generated stub**, which the plan suggests. `make check`'s lane
    installs neither Nextflow nor Docker — `CLAUDE.md` names that trap explicitly — so a test
    that shelled out to it would be green on a developer machine and red in CI. The spine's
    emitted `main.nf` IS run through the real linter, by `make static` and by the nightly stub
    gate, and that covers the same expressions with a tool that actually parses Groovy.
    """
    loaded = layers.load(ROOT / "registry")
    for type_id, expression in loaded.vocabulary.entry_channels.items():
        got = expression.replace("{param}", "a_known_param")
        assert "{param}" not in got, type_id
        assert "params.a_known_param" in got, f"{type_id} substituted nothing"
        for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
            assert got.count(opener) == got.count(closer), f"{type_id} unbalanced {opener}"
