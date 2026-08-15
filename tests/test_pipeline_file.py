"""`pipeline.yml` — the one artifact, written by `build` and read back by `emit`.

Three files retire into it. What replaces them has to be stronger than what it replaced, and
the property that makes it so is the **round trip**: `build` writes the file, parses it back,
and emits from the parsed copy. `ResolvedValue._drop_computed` exists because the IR did not
round-trip at all and — in that field's own words — *"nothing noticed, because nothing read an
IR back until now"*. Now every build reads one back.
"""

import pathlib
import shutil

import pytest
import yaml
from comeni_core.pipeline import SCHEMA_VERSION, Pipeline, Setting, StepInput, Why
from comeni_core.routes import ExtKey, Via
from comeni_core.tiers import Tier, ValueSource
from mendel_compiler.cli import main
from mendel_compiler.emit import emit
from pydantic import ValidationError

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _build(tmp_path, name="p"):
    out = tmp_path / name
    assert main(["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    return out


def _emit(out, capsys, path=None):
    """`mendel emit`, with stderr. Returns `(code, stderr)`."""
    code = main(["emit", str(path or out / "pipeline.yml"), "--out", str(out)])
    return code, capsys.readouterr().err


def _load(out) -> Pipeline:
    return Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))


def test_build_writes_pipeline_yml_and_not_the_two_it_replaces(tmp_path):
    out = _build(tmp_path)
    assert (out / "pipeline.yml").exists()
    assert not (out / "pipeline.ir.json").exists()
    assert not (out / "mendel.lock.yml").exists()


def test_build_emits_from_the_round_tripped_file(tmp_path):
    """The round trip is load-bearing on every build, not a property asserted once here.

    `emit` is handed the reparsed object, so a field that does not survive YAML makes the
    generated Nextflow wrong immediately rather than the next time somebody reads the file.
    """
    out = _build(tmp_path)
    assert emit(_load(out)) == (out / "main.nf").read_text()


def test_emit_reproduces_both_generated_files_byte_for_byte(tmp_path, capsys):
    """A pipeline regenerates from its own file, with no registry and no vocabulary.

    This is what the whole materialisation was for: a laboratory archives a validated
    pipeline and rebuilds its Nextflow years later without the registry it was built
    against — the part that resolves differently as it changes.
    """
    out = _build(tmp_path)
    before = {name: (out / name).read_text() for name in ("main.nf", "nextflow.config")}
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert {name: (out / name).read_text() for name in before} == before


def test_answering_a_tier_four_question_in_the_file_reaches_the_tool(tmp_path, capsys):
    """The point of the whole file, in one test.

    `seq_platform` is tier 4 and nothing answered it, so the shipped spine emits STAR's
    `ext.args` without a read-group line. Answer it by editing `pipeline.yml`, re-emit, and
    the answer arrives on the command line — **with no registry, no vocabulary and no
    resolution.** Before this it was issue #10: the resolver ran, printed REVIEW, and the
    pipeline behaved identically whatever anyone answered.

    The plan had this as a refusal — `MD0213`, "you edited it". That is backwards: `emit` is
    the verb that *cures* staleness, and refusing here would mean the file a reader is told to
    edit can never be edited. Corrected during Task 6.
    """
    out = _build(tmp_path)
    assert "outSAMattrRGline" not in (out / "nextflow.config").read_text()
    _answer(out, "seq_platform", "nanopore")
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert "'PL:nanopore'" in (out / "nextflow.config").read_text()


def _answer(out, name, value):
    """Edit one setting's `value:`, the way a person would.

    Text, not a model round trip: the guards exist for the file as somebody types it, and
    rewriting it through Pydantic would launder exactly the mistakes they are watching for.
    """
    path = out / "pipeline.yml"
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    assert lines[at + 1].strip() == "value: null", lines[at + 1]
    lines[at + 1] = lines[at + 1].replace("value: null", f"value: {value}")
    path.write_text("".join(lines))


def test_a_stale_pipeline_file_is_reported_and_then_cured(tmp_path, capsys):
    """Nextflow runs `main.nf`, not `pipeline.yml`.

    Edit the file you were told to edit, forget to re-emit, and the pipeline that runs is not
    the pipeline that is documented — with every file digest matching, because the bytes on
    disk are exactly the bytes that were written. `from_digest` is what notices, and `emit`
    restamps it, so the same command twice is silent the second time.
    """
    out = _build(tmp_path)
    _answer(out, "seq_platform", "nanopore")
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" in err
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" not in err, "re-emitting must restamp from_digest"


def test_hand_editing_main_nf_is_refused_and_the_fix_names_the_other_file(tmp_path, capsys):
    """Regenerating would destroy the edit silently, so this one really does refuse.

    And the fix says **edit `pipeline.yml`** rather than "revert your change": a person who
    hand-edited `main.nf` was trying to change the pipeline, and the file that does that is
    the other one. A diagnostic that only forbids is half a diagnostic.
    """
    out = _build(tmp_path)
    (out / "main.nf").write_text((out / "main.nf").read_text() + "\n// touched\n")
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0214" in err
    assert "pipeline.yml" in err, "the fix must say where to make the change"


def test_a_deleted_generated_file_is_rewritten_rather_than_refused(tmp_path, capsys):
    """The escape hatch `MD0214`'s fix names, and it has to work.

    Nothing is destroyed by regenerating a file that is not there, so refusing would leave a
    person with a hand-edited `main.nf` and no way forward except editing the digest by hand —
    which is teaching them to defeat the guard.
    """
    out = _build(tmp_path)
    (out / "main.nf").unlink()
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert (out / "main.nf").exists()


def test_emit_refuses_when_modules_are_absent(tmp_path, capsys):
    """`include` paths would point at nothing. Never emit a `main.nf` that cannot run."""
    out = _build(tmp_path)
    shutil.rmtree(out / "modules")
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0210" in err


def test_a_newer_version_is_refused(tmp_path, capsys):
    """Forward compatibility is a promise this format has not made.

    An older Mendel silently ignoring a section a newer one added is how a pipeline gets
    emitted without the thing that section carried.
    """
    out = _build(tmp_path)
    path = out / "pipeline.yml"
    # Relative to what this Mendel writes, never a literal: pinning `version: 2` here made
    # this test assert nothing the moment SCHEMA_VERSION reached 2, and it would have gone on
    # passing for a version that is no longer newer than anything. Plan 1.14 Task 0.
    path.write_text(
        path.read_text().replace(
            f"version: {SCHEMA_VERSION}", f"version: {SCHEMA_VERSION + 1}", 1
        )
    )
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0207" in err


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


def test_from_digest_is_computed_with_emitted_excluded(tmp_path):
    """The exclusion is load-bearing, exactly as `ResolvedValue._drop_computed`'s is: a
    derived field inside the thing it describes does not round-trip."""
    out = _build(tmp_path)
    pipeline = _load(out)
    assert pipeline.emitted is not None
    assert pipeline.emitted.from_digest == pipeline.content_digest()
    without = pipeline.model_copy(update={"emitted": None})
    assert pipeline.content_digest() == without.content_digest()


def test_the_file_carries_every_provenance_a_reader_needs(tmp_path):
    """One file answers "what settings does this pipeline use, and why".

    Four files answered it before, and one of the four mechanisms carried nothing at all.
    """
    raw = yaml.safe_load((_build(tmp_path) / "pipeline.yml").read_text())
    assert raw["version"] == SCHEMA_VERSION
    assert set(raw) == {
        "version",
        "goal",
        "registry",
        "steps",
        "channels",
        "decisions",
        "emitted",
        "gate",
    }
    star = next(s for s in raw["steps"] if s["id"] == "star_align")
    assert star["module"]["digest"].startswith("sha256:")
    assert star["module"]["container"].startswith("community.wave.seqera.io/")
    assert star["why"]["reason"]
    setting = next(s for s in star["settings"] if s["name"] == "seq_platform")
    assert setting["value"] is None, "nobody answered it, and the file must not pretend"
    assert setting["via"] == "ext" and setting["key"] == "args"
    assert setting["why"]["tier"] == 4


def test_the_file_records_the_goal_it_was_built_from(tmp_path):
    """`goal:` was written empty for the first hour of Task 6, and everything passed.

    `Pipeline.of` defaulted it to `Goal(profile=ir.profile)` — which type-checks, round-trips,
    and satisfies the totality test, because that test asks whether a field has a *home* and
    this one did. It is now keyword-only with no default. A field present and empty is worse
    than a field absent: the file claims to record what was asked for.
    """
    raw = yaml.safe_load((_build(tmp_path) / "pipeline.yml").read_text())
    declared = yaml.safe_load(GOAL.read_text())
    assert raw["goal"]["want"] == declared["want"]
    assert [item["type_id"] for item in raw["goal"]["have"]] == [
        item["type_id"] for item in declared["have"]
    ]
    measured = {m["measurement"]: m["value"] for m in raw["goal"]["profile"]["measurements"]}
    assert measured["strandedness"] == "reverse"


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
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0217" in err
    assert not pathlib.Path("/tmp/PWNED_A44").exists()


# --- A38: via: meta and via: directive are declared routes; they must emit ---


def _overlay_with(tmp_path, extra_params: str) -> pathlib.Path:
    """A registry overlay adding params to subread/featurecounts. Shared by A38–A42 tasks."""
    ov = tmp_path / "ov"
    (ov / "contracts" / "nf-core").mkdir(parents=True)
    (ov / "registry.yml").write_text("name: lab\n")
    src = (ROOT / "registry/contracts/nf-core/subread-featurecounts.yml").read_text()
    src = src.replace("params:", "params:\n" + extra_params, 1)
    (ov / "contracts/nf-core/subread-featurecounts.yml").write_text(src)
    return ov


def _build_with_overlay(tmp_path, ov) -> pathlib.Path:
    out = tmp_path / "b"
    assert (
        main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
              "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0
    )
    return out


def test_via_directive_reaches_nextflow_config(tmp_path):
    ov = _overlay_with(tmp_path, "  - {name: cpus, default: 7, via: directive}\n")
    out = _build_with_overlay(tmp_path, ov)
    assert "cpus = 7" in (out / "nextflow.config").read_text()


def test_via_meta_reaches_the_channel_meta_map(tmp_path):
    """A38, with a legal key since Plan 1.14.

    This used to route an invented `tag`, which `MD0108`'s meta arm now refuses — a param in
    `meta` that the module never reads is the deadness issue #10 was about, and is exactly
    where A91 hid. featureCounts reads `id`, `single_end` and `strandedness`, so the route
    has to name one of those; `single_end` is free only when the goal states no `paired`
    measurement, which is what this goal does.
    """
    goal = tmp_path / "goal.yml"
    goal.write_text(
        (ROOT / "examples" / "rnaseq-goal.yml").read_text().replace("  paired: true\n", "")
    )
    ov = _overlay_with(tmp_path, "  - {name: single_end, default: false, via: meta}\n")
    out = tmp_path / "b"
    assert (
        main(["build", "--goal", str(goal), "--registry", str(ROOT / "registry"),
              "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0
    )
    assert "single_end: false" in (out / "main.nf").read_text()


# --- A51: displacements of all four kinds reach the artifact, not just contracts+measurements ---


def _displaced_kinds(out) -> list[str]:
    reg = yaml.safe_load((out / "pipeline.yml").read_text())["registry"]
    return [d["kind"] for d in reg.get("displaced") or []]


def test_a_vocabulary_displacement_reaches_the_artifact(tmp_path):
    """A24 gave a vocabulary displacement somewhere to be recorded — `loaded.displaced` — but
    `resolve()` re-derived `PipelineIR.displaced` from measurements+contracts alone, so the one
    overlay that rewrites emitted Groovy verbatim reached the published file saying nothing. The
    artifact is what a reader audits; a silent reroute there is the whole of what invariant 11
    forbids."""
    ov = tmp_path / "ov"
    (ov / "vocabularies").mkdir(parents=True)
    (ov / "registry.yml").write_text("name: lab-vocab\n")
    # Replace fastq.reads' entry_channel — the base's states, a lab's own source path.
    (ov / "vocabularies" / "fastq.reads.yml").write_text(
        "states: [trimmed, deduplicated, subsampled]\n"
        "entry_channel: \"Channel.fromFilePairs('/mnt/lab/run7/*_R{1,2}.fastq.gz')\"\n"
    )
    out = _build_with_overlay(tmp_path, ov)
    assert "vocabularies" in _displaced_kinds(out)


def test_a_rules_displacement_reaches_the_artifact(tmp_path):
    """The same gap for the fourth kind: an overlay `rules/` block replacing a base decision
    was recorded on `RuleTable.displaced_layer` (per-node, A15) but never as a `Displacement`
    on the artifact's `registry.displaced`. Now all four kinds land in one list a reader reads
    once."""
    ov = tmp_path / "ov"
    (ov / "rules").mkdir(parents=True)
    (ov / "registry.yml").write_text("name: lab-rules\n")
    base_rule = (ROOT / "registry/rules/rnaseq.yml").read_text()
    (ov / "rules" / "rnaseq.yml").write_text(base_rule)
    out = _build_with_overlay(tmp_path, ov)
    assert "rules" in _displaced_kinds(out)


# --- A41: a contract that fails to load is blamed on the contract, not the goal ---


def test_a_contract_missing_via_emits_MD0200_and_blames_the_contract(tmp_path, capsys):
    """A `Param` with no `via:` raised a raw Pydantic `Field required` under 'this goal is not
    valid' — the one file the operator did not write, blamed for a contract author's omission.
    The refusal is a real one (MD0200: the value reaches no tool); the message just named the
    wrong file and buried the code."""
    ov = _overlay_with(tmp_path, "  - {name: x, default: 1}\n")  # no via:
    out = tmp_path / "b"
    code = main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)])
    err = capsys.readouterr().err
    assert code == 2
    assert "MD0200" in err
    assert "goal is not valid" not in err
    assert "subread" in err or "featurecounts" in err.lower(), "name the contract at fault"


# --- A42: guards that A42 found had no watched revert ---


def test_a_step_input_naming_both_a_source_and_a_channel_is_refused():
    """MD0215. A `StepInput` is one edge: it comes from an upstream step (`source`) or an entry
    channel (`channel`), never both. Both set is a wiring that reads two ways — root G's defect
    in a new type — so it is refused rather than resolved by field order."""
    with pytest.raises(ValueError, match="MD0215"):
        StepInput(port="reads", source="trimgalore.reads", channel="fastq.reads")


def test_a_step_input_naming_neither_a_source_nor_a_channel_is_refused():
    """MD0215, the other half: a port that names no origin at all wires to nothing."""
    with pytest.raises(ValueError, match="MD0215"):
        StepInput(port="reads")


def test_ext_args_fragments_emit_name_sorted_whatever_the_setting_order(tmp_path):
    """The property the emitter's own docstring predicted no test could see: `_ext_scope`
    composes `key: args` fragments in **name-sorted** order, so emission is byte-identical
    however the settings arrive. Materialisation already sorts them, which is why an end-to-end
    build cannot watch this — so the step's settings are reversed by hand and `_ext_scope` must
    still emit `--alpha` before `--zulu`. Reverting the sort in `_ext_scope` fails this."""
    from mendel_compiler.emit import _ext_scope

    ov = _overlay_with(
        tmp_path,
        '  - {name: zulu, default: 1, via: ext, key: args, template: "--zulu {value}"}\n'
        '  - {name: alpha, default: 2, via: ext, key: args, template: "--alpha {value}"}\n',
    )
    out = _build_with_overlay(tmp_path, ov)
    step = next(s for s in _load(out).steps if "FEATURECOUNTS" in s.process)
    reversed_step = step.model_copy(update={"settings": list(reversed(step.settings))})
    argline = next(line for line in _ext_scope(reversed_step) if "ext.args" in line)
    assert argline.index("--alpha") < argline.index("--zulu"), "name-sorted, not setting order"


# --- A40: two writers for one destination is a refusal, not a silent concatenation ---


def test_two_ext_settings_on_one_prefix_are_refused(tmp_path):
    """Different names (so MD0212 passes), one non-composing key — they collide in ext.prefix."""
    ov = _overlay_with(
        tmp_path,
        "  - {name: a, default: x, via: ext, key: prefix}\n"
        "  - {name: b, default: y, via: ext, key: prefix}\n",
    )
    out = tmp_path / "b"
    code = main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)])
    assert code == 2


def test_two_ext_args_settings_still_compose(tmp_path):
    """The exemption: args/args2/args3 are designed to concatenate, so two is not a collision."""
    ov = _overlay_with(
        tmp_path,
        '  - {name: a, default: 1, via: ext, key: args, template: "--a {value}"}\n'
        '  - {name: b, default: 2, via: ext, key: args, template: "--b {value}"}\n',
    )
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0


def test_a_meta_setting_shadowing_a_measurement_is_refused(tmp_path):
    """A via: meta setting named for a measurement would silently overwrite the measured fact.

    Conservative and global: any measurement key present in the pipeline collides with a meta
    setting of that name, without tracing which channel reaches which step — a measured fact and
    a resolved decision writing one meta key is refused wherever both appear.
    """
    ov = _overlay_with(tmp_path, "  - {name: strandedness, default: forward, via: meta}\n")
    out = tmp_path / "b"
    code = main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)])
    assert code == 2


# --- A39: a non-templated ext key is quoted once, not twice ---


def test_a_non_templated_ext_key_is_quoted_once(tmp_path):
    """`prefix` takes one value and has no template, so _render_literal must run once.

    It ran twice — per fragment and again on the join — so `alpha` emitted as `'\\'alpha\\''`,
    a Groovy string whose value includes the quote characters, corrupting every output filename.
    """
    ov = _overlay_with(tmp_path, "  - {name: tag, default: alpha, via: ext, key: prefix}\n")
    out = _build_with_overlay(tmp_path, ov)
    cfg = (out / "nextflow.config").read_text()
    assert "ext.prefix = 'alpha'" in cfg
    assert "\\'alpha\\'" not in cfg


# --- A46: a tier-4 answer has one writable home; the two must not disagree ---


def test_value_and_human_override_may_not_contradict(tmp_path, capsys):
    """settings[].value is the writable answer; a human_override that differs is one file, two
    answers, and emit and upgrade read different ones. Refuse rather than pick."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
    for d in doc["decisions"]:
        if d["key"].endswith("seq_platform"):
            d["human_override"] = "illumina"
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0218" in err


def test_editing_the_value_answers_for_emit_and_upgrade(tmp_path, capsys):
    """The A46 fix: editing settings[].value is honoured by both verbs, not just emit."""
    out = _build(tmp_path)
    _answer(out, "seq_platform", "nanopore")
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert "'PL:nanopore'" in (out / "nextflow.config").read_text()
    nxt = tmp_path / "next"
    assert main(["upgrade", str(out / "pipeline.yml"), "--out", str(nxt), "--root", str(ROOT)]) == 0
    assert "'PL:nanopore'" in (nxt / "nextflow.config").read_text()


# --- A54: `source: human` is a claim about evidence, not assertable through the port ---


def test_human_source_requires_a_matching_override(tmp_path, capsys):
    """`why.source: human` is what clears a tier-4 review — it says a person answered the
    ambiguity after resolution flagged it. Asserted through `settings[].why` with no decision
    recording that answer, it is a review cleared by claim: the exact dishonesty invariant 6
    forbids. A `human` source must have a matching non-null `human_override`."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
                setting["why"]["source"] = "human"
    # Deliberately leave decisions[].human_override null — the claim without the evidence.
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0220" in err


def test_human_source_with_a_matching_override_is_accepted(tmp_path, capsys):
    """The honest case: the value, the `human` source and the decision's override all agree —
    a person answered, and the record proves it. This must still emit."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
                setting["why"]["source"] = "human"
    for d in doc["decisions"]:
        if d["key"].endswith("seq_platform"):
            d["human_override"] = "nanopore"
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 0, err


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
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0219" in err


# --- A47: emit carries the gate verdict rather than erasing it ---


def test_emit_preserves_the_gate_verdict(tmp_path, capsys, monkeypatch):
    """A re-emit that changes nothing must not drop the certification. `gate:` is load-bearing —
    the evidence and the pipeline are one document, and the archive workflow regenerates later.

    `publish` stamps the verdict and the digests together, so the file is not stale; a no-op
    `emit` afterwards must carry it through. The gate itself is stubbed so this runs in CI's
    Nextflow-free lane — the property under test is the verdict round trip, not `nextflow lint`."""
    from mendel_compiler import cli
    from mendel_compiler.gates import GateResult

    monkeypatch.setattr(cli, "run_gate", lambda gate, out: GateResult(gate=gate, passed=True))
    out = _build(tmp_path)
    assert main(["publish", str(out / "pipeline.yml"), "--gate", "lint", "--root", str(ROOT)]) == 0
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" not in err, err  # not stale — a genuine no-op re-emit
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"


def test_emit_clears_the_gate_verdict_when_the_file_was_edited(tmp_path, capsys):
    """A stale file has changed since it was gated, so its verdict no longer describes this
    pipeline. Preserving it would certify content that never passed the gate."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    doc["gate"] = "lint"
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    _emit(out, capsys)  # settle emitted digests against the gate stamp
    _answer(out, "seq_platform", "nanopore")  # now edit — the pipeline changed
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" in err
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] is None


# --- A48: a pipeline.yml with no goal is refused, not upgraded to empty ---


def test_a_pipeline_with_no_goal_is_refused(tmp_path, capsys):
    """`goal` is what `upgrade` re-resolves. Missing, it defaulted to an empty Goal and upgrade
    produced `steps: []` at exit 0 — an empty pipeline from the likeliest hand-edit mistake."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    doc.pop("goal")
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2


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
    (out / "pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0201" in err
    assert (out / "main.nf").read_text() == before, "a refused emit must leave main.nf untouched"


def _why() -> Why:
    return Why(tier=Tier.AMBIGUOUS, source=ValueSource.HUMAN, reason="a round-four probe")


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


def test_an_unanswered_raw_ext_value_still_loads():
    """`value: null` is an unanswered tier-4 setting, and `_ext_scope` skips it — invariant 6
    says tier 4 is *flagged*, not fatal. MD0221 is for a value that exists and cannot be
    carried safely, so absence must stay legal or the shipped spine stops loading.
    """
    setting = Setting(
        name="seq_platform", value=None, via=Via.EXT, key=ExtKey.PREFIX, template=None,
        why=_why(),
    )
    assert setting.value is None


# --- Plan 1.14 Task 0: a schema change must announce itself -------------------------------

SERIALISED_SHAPE = {
    "Pipeline": ["version", "goal", "registry", "steps", "channels", "decisions",
                 "emitted", "gate"],
    "Step": ["id", "module", "process", "include", "why", "presence", "ext_args", "inputs",
             "call", "settings"],
    "ExtArgs": ["template", "why"],
    "Setting": ["name", "value", "via", "key", "template", "why"],
    "Why": ["tier", "source", "reason", "for_value", "axis_reason", "from_layer",
            "displaced_layer"],
    "CallArg": ["ports", "literal", "empty_width", "from_setting", "join", "why"],
    "MetaEntry": ["key", "value", "why"],
    "Emitted": ["schema_version", "files", "from_digest"],
    "ParamDecision": ["key", "subject", "reason", "confidence", "resolved_by", "tier",
                      "kind", "candidates", "chosen", "human_override", "override_reason"],
}
"""The artifact's serialised field order, as of `SCHEMA_VERSION = 3`.

**This is a fingerprint, not a specification.** It exists to fail when somebody adds a field
without bumping the version — which is exactly what happened in Plan 1.13 and is why Task 0
exists. `emitted.from_digest` hashes the model dump, so *any* addition moves the digest of
every pipeline ever archived, at once, with nobody having touched one. The version is what
lets `MD0213` tell that apart from a human edit, and a version nobody remembers to bump
cannot.

When this test fails: add your field here, and make sure `SCHEMA_VERSION` is ahead of
`RELEASED_SCHEMA_VERSION`. Within one unreleased bump that is already true and the fingerprint
is all that changes — version 2 covers every field Plan 1.14 adds. What must never happen is
the shape moving while the version stays at what a laboratory already has on disk.
"""

RELEASED_SCHEMA_VERSION = 1
"""The highest version any archived pipeline can be carrying. Raised when a version ships."""


def test_a_schema_change_bumps_the_version():
    """Adding a field to the artifact moves every archived pipeline's digest. Announce it."""
    from comeni_core.decision import ParamDecision
    from comeni_core.egress import Emitted
    from comeni_core.pipeline import (
        SCHEMA_VERSION,
        CallArg,
        ExtArgs,
        MetaEntry,
        Pipeline,
        Step,
    )

    actual = {
        "Pipeline": list(Pipeline.model_fields),
        "Step": list(Step.model_fields),
        "ExtArgs": list(ExtArgs.model_fields),
        "Setting": list(Setting.model_fields),
        "Why": list(Why.model_fields),
        "CallArg": list(CallArg.model_fields),
        "MetaEntry": list(MetaEntry.model_fields),
        "Emitted": list(Emitted.model_fields),
        "ParamDecision": list(ParamDecision.model_fields),
    }
    assert actual == SERIALISED_SHAPE, (
        "the artifact's shape moved. Every archived pipeline's `emitted.from_digest` just "
        "moved with it, so bump SCHEMA_VERSION and update SERIALISED_SHAPE together — "
        "updating either alone is the defect Plan 1.14 Task 0 fixed."
    )
    assert SCHEMA_VERSION > RELEASED_SCHEMA_VERSION, (
        "the shape moved, so SCHEMA_VERSION must be ahead of the last released one. Within a "
        "single unreleased bump, adding fields and updating SERIALISED_SHAPE is enough — "
        "version 2 covers everything Plan 1.14 adds. What must never happen is the shape "
        "moving while the version stays at what a laboratory already has on disk."
    )


# --- Plan 1.14 Task 1: a reason cannot outlive its value (A104, A105) ---------------------


def _edit_setting_value(out, name, value):
    """Change a resolved setting's `value:` by hand, the way the file's own header invites.

    Text rather than a model round trip, for the same reason `_answer` is: the guard exists
    for the file as somebody types it, and rewriting through Pydantic would launder the
    mistake being watched for.
    """
    path = out / "pipeline.yml"
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    lines[at + 1] = f"    value: {value}\n"
    path.write_text("".join(lines))


def test_editing_a_value_and_leaving_its_reason_is_refused(tmp_path, capsys):
    """A104, critical. The edit reached the tool; the reason beside it described the old value.

    Reproduced by the design audit: `min_mqs` edited 0 → 30 emits `-Q 30` — reads below
    mapping quality 30 are now discarded, a real analysis change — while the record still
    reads `tier: 2 / source: resolver / reason: contract default for min_mqs`, all three
    false. `mendel publish --gate lint` certified it at exit 0.

    A diagnostic rather than a parse error, deliberately: the file says *"Read it; edit it"*,
    so a person who changes a number must be **told to update the reason**, not handed a
    stack trace for doing what the header invited.
    """
    out = _build(tmp_path)
    _edit_setting_value(out, "min_mqs", 30)

    code, err = _emit(out, capsys)

    assert code != 0
    assert "MD0223" in err
    assert "0" in err and "30" in err, "name both values, or the reader cannot act"


def test_editing_a_value_and_its_reason_together_is_accepted(tmp_path, capsys):
    """The negative. A check that can only refuse is not a check — it is an obstacle."""
    out = _build(tmp_path)
    _edit_setting_value(out, "min_mqs", 30)
    path = out / "pipeline.yml"
    path.write_text(
        path.read_text()
        .replace("reason: contract default for min_mqs",
                 "reason: lab SOP BIOINF-014 requires MAPQ >= 30")
        .replace("for_value: 0", "for_value: 30")
    )

    code, err = _emit(out, capsys)

    assert code == 0, err
    assert "-Q 30" in (out / "nextflow.config").read_text()


def test_a_file_written_before_for_value_still_emits(tmp_path, capsys):
    """`for_value: null` means "written before 1.14", not "explains nothing".

    An archived pipeline has no such field and must still regenerate its Nextflow. The check
    fires only where the field is set and disagrees, which is also what gives it real
    negatives.
    """
    out = _build(tmp_path)
    path = out / "pipeline.yml"
    path.write_text(
        "\n".join(
            line for line in path.read_text().splitlines() if "for_value:" not in line
        )
        + "\n"
    )

    code, err = _emit(out, capsys)

    assert code == 0, err
