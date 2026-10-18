"""Saved-pipeline validation: observable CLI and artifact behavior."""

import pathlib

import pytest
import yaml
from comeni_core.artifact.pipeline import Pipeline, Setting, StepInput
from comeni_core.spell.routes import ExtKey, Via
from mendel_compiler.cli import main
from pydantic import ValidationError
from support.paths import ROOT
from support.pipeline import (
    _GOAL_MODELS,
    GOAL,
    _build,
    _declared,
    _emit,
    _overlay_with,
    _why,
)


def test_channel_params_disagreeing_with_its_expression_is_refused(tmp_path):
    """`MD0211`. `channels[].params` is stored *and* derivable, deliberately — taking a scan
    over arbitrary Groovy out of the emitter is much of what materialisation buys. The price
    of the duplication is that it must be checked, and here it is."""
    out = _build(tmp_path)
    raw = yaml.safe_load((out / "pipeline.yml").read_text())
    raw["channels"][0]["params"] = ["not_referenced"]
    with pytest.raises(ValueError, match="MD0211"):
        Pipeline.model_validate(raw)


def test_two_steps_sharing_an_id_are_refused(tmp_path):
    """`MD0212`, and it is A11 arriving in a new type: `ModuleContract` already rejects a
    duplicate `Param`, because the second silently wins and nothing says so."""
    out = _build(tmp_path)
    raw = yaml.safe_load((out / "pipeline.yml").read_text())
    raw["steps"].append(dict(raw["steps"][0]))
    with pytest.raises(ValueError, match="MD0212"):
        Pipeline.model_validate(raw)


def test_two_settings_sharing_a_name_are_refused(tmp_path):
    """The same code, one level down. `ext.args` composition sorts by name, so a duplicate
    is not merely ambiguous — it is two fragments the emitter would happily concatenate."""
    out = _build(tmp_path)
    raw = yaml.safe_load((out / "pipeline.yml").read_text())
    step = next(s for s in raw["steps"] if s["settings"])
    step["settings"].append(dict(step["settings"][0]))
    with pytest.raises(ValueError, match="MD0212"):
        Pipeline.model_validate(raw)


def test_test_data_injection_is_refused_at_load(tmp_path, capsys):
    """A44: a poisoned test_data in pipeline.yml is refused before it can be emitted.

    The audit's reproduction: a Groovy payload in a test_data list executed at `nextflow
    config` time. It now fails to load — the validator on `TestDataRef` fires — and even were
    it to reach the emitter, `_render_test_data` single-quotes and escapes it.
    """
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    payload = 'x"; new File("/tmp/PWNED_A44").text = "rce"; def z="'
    for ch in doc["channels"]:
        if ch["type_id"] == "annotation.gtf":
            ch["test_data"] = [payload]
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0217" in err
    assert not pathlib.Path("/tmp/PWNED_A44").exists()


# Regression evidence: A41
# --- A41: a contract that fails to load is blamed on the contract, not the goal ---
def test_a_contract_missing_via_emits_MD0200_and_blames_the_contract(tmp_path, capsys):
    """A `Param` with no `via:` raised a raw Pydantic `Field required` under 'this goal is not
    valid' — the one file the operator did not write, blamed for a contract author's omission.
    The refusal is a real one (MD0200: the value reaches no tool); the message just named the
    wrong file and buried the code."""
    ov = _overlay_with(tmp_path, "  - {name: x, default: 1}\n")  # no via:
    out = tmp_path / "b"
    code = main(
        [
            "build",
            "--goal",
            str(GOAL),
            "--registry",
            str(ROOT / "registry"),
            "--registry",
            str(ov),
            "--out",
            str(out),
            "--root",
            str(ROOT),
        ]
    )
    err = capsys.readouterr().err
    assert code == 2
    assert "MD0200" in err
    assert "goal is not valid" not in err
    assert "subread" in err or "featurecounts" in err.lower(), "name the contract at fault"


# Regression evidence: A42, A42
# --- A42: guards that A42 found had no watched revert ---
def test_a_step_input_naming_both_a_source_and_a_channel_is_refused():
    """MD0215. A `StepInput` is one edge: it comes from an upstream step (`source`) or an entry
    channel (`channel`), never both. Both set is a wiring that reads two ways — root G's defect
    in a new type — so it is refused rather than resolved by field order.

    **`channel="reads"`, not `"fastq.reads"`.** Since schema 6 a port names a channel by name
    rather than by type, and `ChannelName` is a plain identifier — so the old spelling now fails
    on the field before MD0215 is reached. Updating the fixture is the type having actually
    narrowed rather than merely being renamed."""
    with pytest.raises(ValueError, match="MD0215"):
        StepInput(port="reads", source="trimgalore.reads", channel="reads")


# Regression evidence: A42, A42
def test_a_step_input_naming_neither_a_source_nor_a_channel_is_refused():
    """MD0215, the other half: a port that names no origin at all wires to nothing."""
    with pytest.raises(ValueError, match="MD0215"):
        StepInput(port="reads")


# Regression evidence: A40
# --- A40: two writers for one destination is a refusal, not a silent concatenation ---
def test_two_ext_settings_on_one_prefix_are_refused(tmp_path):
    """Different names (so MD0212 passes), one non-composing key — they collide in ext.prefix."""
    ov = _overlay_with(
        tmp_path,
        "  - {name: a, default: x, via: ext, key: prefix}\n"
        "  - {name: b, default: y, via: ext, key: prefix}\n",
    )
    out = tmp_path / "b"
    code = main(
        [
            "build",
            "--goal",
            str(GOAL),
            "--registry",
            str(ROOT / "registry"),
            "--registry",
            str(ov),
            "--out",
            str(out),
            "--root",
            str(ROOT),
        ]
    )
    assert code == 2


# Regression evidence: A40
def test_a_meta_setting_shadowing_a_measurement_is_refused(tmp_path):
    """A via: meta setting named for a measurement would silently overwrite the measured fact.

    Conservative and global: any measurement key present in the pipeline collides with a meta
    setting of that name, without tracing which channel reaches which step — a measured fact and
    a resolved decision writing one meta key is refused wherever both appear.
    """
    ov = _overlay_with(tmp_path, "  - {name: strandedness, default: forward, via: meta}\n")
    out = tmp_path / "b"
    code = main(
        [
            "build",
            "--goal",
            str(GOAL),
            "--registry",
            str(ROOT / "registry"),
            "--registry",
            str(ov),
            "--out",
            str(out),
            "--root",
            str(ROOT),
        ]
    )
    assert code == 2


# Regression evidence: A52
# --- A52: a duplicate decision key is corruption, and is refused ---
def test_a_duplicate_decision_key_is_refused(tmp_path, capsys):
    """Two records for one key: ReplayResolver's setdefault kept the first and dropped the
    second's override in silence. A duplicate is a corrupt file, not a choice — refuse it."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    dec = [d for d in doc["decisions"] if d["key"].endswith("seq_platform")][0]
    dup = dict(dec)
    dup["human_override"] = "illumina"
    doc["decisions"].append(dup)
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0219" in err


# Regression evidence: A48
# --- A48: a pipeline.yml with no goal is refused, not upgraded to empty ---
def test_a_pipeline_with_no_goal_is_refused(tmp_path, capsys):
    """`intent` and `facts` (version 6's `goal`) are what `upgrade` re-resolves. Missing, the
    goal defaulted to an empty one and upgrade produced `steps: []` at exit 0 — an empty
    pipeline from the likeliest hand-edit mistake."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    doc.pop("intent")
    doc.pop("facts")
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code == 2


# Regression evidence: A49
# --- A49: a refused emit leaves the directory untouched ---
def test_a_refused_emit_writes_nothing(tmp_path, capsys):
    """emit wrote main.nf, then emit_config raised MD0201 — so main.nf was rewritten though the
    emit refused, and the retry then blamed the user with MD0214 for Mendel's own damage."""
    out = _build(tmp_path)
    before = (out / "main.nf").read_text()
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        if s["id"] == "trimgalore":
            s["process"] = "TRIMGALORE2"  # a valid rename → main.nf would change
        for setting in s.get("settings", []):
            if setting["name"] == "min_mqs":
                setting["value"] = "0 bad"  # non-substitutable → emit_config raises MD0201
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0201" in err
    assert (out / "main.nf").read_text() == before, "a refused emit must leave main.nf untouched"


# Regression evidence: A49
def test_a_raw_ext_value_cannot_smuggle_groovy():
    """A55. `key: prefix` takes no template — `MD0204` refuses one — so its value rides the
    raw branch of `_ext_scope`, and a `${…}` there becomes a closure Nextflow evaluates per
    task. The value is the field this file's own header tells a human to edit, and the file
    is meant to be shared, so it is refused at load rather than at emit.
    """
    with pytest.raises(ValidationError) as caught:
        Setting(
            name="seq_platform",
            value="${['sh','-c','id'].execute().text}",
            via=Via.EXT,
            key=ExtKey.PREFIX,
            template=None,
            why=_why(),
        )
    assert "MD0221" in str(caught.value)


# Regression evidence: A49
def test_an_ordinary_raw_ext_value_still_loads():
    """The refusal is the substitutable class, not a ban on the raw route: A39 added that
    branch for a reason, and a `prefix` value is an ordinary identifier."""
    setting = Setting(
        name="seq_platform",
        value="illumina",
        via=Via.EXT,
        key=ExtKey.PREFIX,
        template=None,
        why=_why(),
    )
    assert setting.value == "illumina"


# Regression evidence: A49
def test_an_unanswered_raw_ext_value_still_loads():
    """`value: null` is an unanswered tier-4 setting, and `_ext_scope` skips it — invariant 6
    says tier 4 is *flagged*, not fatal. MD0221 is for a value that exists and cannot be
    carried safely, so absence must stay legal or the shipped spine stops loading.
    """
    setting = Setting(
        name="seq_platform",
        value=None,
        via=Via.EXT,
        key=ExtKey.PREFIX,
        template=None,
        why=_why(),
    )
    assert setting.value is None


# Regression evidence: A108, A127
def test_a_pipeline_defect_blames_the_pipeline_file(tmp_path, capsys):
    """A74, issue #35. `emit` and `upgrade` take a `pipeline.yml`, not a goal — the artifact's
    own header says `goal:` is inert to `emit` — and a `Pipeline`-family validation failure
    was reported as *"this goal is not valid"*.

    Exit 2 was right and the sentence was not: a reader who had just edited `steps:` was sent
    to the one section that could not have caused it. That is the exact shape the round-four
    brief named — a real failure reported as a bad goal when the goal was fine.
    """
    out = _build(tmp_path)
    path = out / "pipeline.yml"
    raw = yaml.safe_load(path.read_text())
    raw["steps"].append(raw["steps"][0])
    path.write_text(_declared(path, yaml.safe_dump(raw)))
    code, err = _emit(out, capsys)
    assert code == 2
    assert "this pipeline file is not valid" in err, err
    assert "this goal" not in err


# Regression evidence: A108, A127
def test_every_pipeline_model_blames_the_pipeline_file():
    """The set is derived-checked, not trusted. A model added to the artifact tomorrow gets
    the right blame or this fails — which is what makes it not a third special case."""
    from comeni_core.artifact.pipeline import Pipeline
    from mendel_compiler.cli import _PIPELINE_MODELS, _blame
    from support.walk import reachable

    unlisted = sorted(
        model.__name__
        for model in reachable(Pipeline)
        if model.__name__ not in _PIPELINE_MODELS and model.__name__ not in _GOAL_MODELS
    )
    assert unlisted == [], (
        "these models are part of `pipeline.yml` and would be blamed on the goal:\n  "
        + "\n  ".join(unlisted)
    )
    assert _blame("Step") == "this pipeline file"
    assert _blame("Goal") == "this goal"
    assert _blame("ModuleContract") == "contract"
