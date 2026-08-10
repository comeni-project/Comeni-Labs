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
from comeni_core.pipeline import Pipeline
from mendel_compiler.cli import main
from mendel_compiler.emit import emit

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
    path.write_text(path.read_text().replace("version: 1", "version: 2", 1))
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
    assert raw["version"] == 1
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
    ov = _overlay_with(tmp_path, "  - {name: tag, default: forward, via: meta}\n")
    out = _build_with_overlay(tmp_path, ov)
    assert "tag: 'forward'" in (out / "main.nf").read_text()
