"""`mendel publish` — the pipeline, certified.

It writes files and sends nothing. Transmitting them is a later, separate act, which is the
right shape: a person can read what they are about to publish. Publication is the door with
no undo, and this is the half of it that can be undone.

**The directory is the artifact.** `pipeline.bundle.json` and `mendel.lock.yml` both retired
in Plan 1.10 — everything they carried is in `pipeline.yml`, so `publish` writes no artifact
of its own. It re-resolves the file, refuses if the directory has diverged from it, runs the
gate you ask for, and stamps the verdict. What you hand somebody is `pipeline.yml` plus
`modules/`, which is what they already had to be handed.
"""

import pathlib

import yaml
from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _built(tmp_path, name="p", extra=()):
    out = tmp_path / name
    code = main(
        ["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT), *extra]
    )
    assert code == 0
    return out


def _publish(tmp_path, name="p", extra=()):
    out = _built(tmp_path, name, extra)
    assert main(["publish", str(out / "pipeline.yml"), "--root", str(ROOT)]) == 0
    return out


def test_publish_writes_no_artifact_of_its_own(tmp_path):
    """Three files retired into one, and `publish` stopped being a second writer.

    `pipeline.bundle.json` held goal + IR + decisions + lockfile. `pipeline.yml` holds the
    goal, every decision, every contract by digest and container, every layer, the gate that
    passed and the digests of what was emitted. A second file restating that is a second
    thing to keep in step.
    """
    out = _publish(tmp_path)
    assert (out / "pipeline.yml").exists()
    assert not (out / "pipeline.bundle.json").exists()
    assert not (out / "mendel.lock.yml").exists()
    assert not (out / "pipeline.ir.json").exists()


def test_publish_takes_no_out_because_it_certifies_rather_than_produces(tmp_path):
    """The shape of the verb, not an omission.

    `publish` does not make a new pipeline; it certifies the one you give it. `upgrade` is the
    opposite and must never write in place, and giving them the same flag with opposite
    meanings is how somebody loses the evidence they meant to keep.
    """
    import pytest

    out = _built(tmp_path)
    # A usage error, so argparse exits rather than returning — the same shape as
    # `mendel explain` with no code.
    with pytest.raises(SystemExit):
        main(["publish", str(out / "pipeline.yml"), "--out", str(tmp_path / "elsewhere")])


def test_the_pipeline_file_carries_every_part_a_recipient_needs(tmp_path):
    """Federation §4.1: what was asked for, what it resolved to, why each choice was made,
    and against exactly which registry. All four, or the recipient can neither reproduce it
    nor audit it.

    An exact set rather than a subset — a section appearing in the door with no undo should
    fail this test and be argued for, which is what happened to `gate` (A4) and `emitted`
    (A28) in the artifact this replaced.
    """
    doc = yaml.safe_load((_publish(tmp_path) / "pipeline.yml").read_text())
    assert set(doc) == {
        "version",
        "goal",
        "registry",
        "steps",
        "channels",
        "decisions",
        "emitted",
        "gate",
    }
    assert doc["goal"]["want"] == ["counts.matrix"]
    assert len(doc["steps"]) == 5
    assert doc["registry"]["layers"]
    assert doc["decisions"]
    # No gate was asked for, so the honest record is "no evidence", not a weak gate.
    assert doc["gate"] is None


def test_the_pipeline_file_records_the_artifact_it_produced(tmp_path):
    """A28 — an artifact carrying no record of what it emitted cannot say whether it moved.

    Recorded rather than reconstructed: re-emitting needs the registry as it was, and a
    contract removed from the registry is one of the two cases upgrade exists to report. It
    also makes the directory self-verifying — a recipient can check that the pipeline they
    were handed is the one it describes.
    """
    from comeni_core.digest import digest_of_bytes

    out = _publish(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    files = doc["emitted"]["files"]
    assert [f["name"] for f in files] == ["main.nf", "nextflow.config"], "sorted, read one way"
    for recorded in files:
        assert recorded["digest"] == digest_of_bytes((out / recorded["name"]).read_bytes())
    # Never the vendored tree: `modules/` is copied, not emitted.
    assert not any("modules" in f["name"] for f in files)
    assert doc["emitted"]["from_digest"].startswith("sha256:")


def test_the_pipeline_file_pins_every_module_used(tmp_path):
    """What `mendel.lock.yml` used to assert, against the file that replaced it.

    Per step rather than in a side list, which is the point: the pin sits beside the step it
    pins, so "which STAR is this" is answered where the question is asked.
    """
    doc = yaml.safe_load((_publish(tmp_path) / "pipeline.yml").read_text())
    assert all(step["module"]["digest"].startswith("sha256:") for step in doc["steps"])
    assert all(step["module"]["container"] for step in doc["steps"])


def test_the_pipeline_file_records_which_layers_built_it(tmp_path):
    """The name the layer declares, not the directory it was checked out into.

    This said `["registry"]` until audit A12. A recipient reading it needs a name that means
    the same thing on their machine, and a basename does not: whoever cloned the public layer
    as `comeni-registry` produced an artifact that disagreed with this one about a registry
    neither of them had changed.
    """
    doc = yaml.safe_load((_publish(tmp_path) / "pipeline.yml").read_text())
    assert [layer["name"] for layer in doc["registry"]["layers"]] == [
        "comeni-registry-examples"
    ]


def test_publishing_twice_produces_identical_bytes(tmp_path):
    """Determinism, applied to the artifact people share. No timestamps anywhere."""
    a, b = _publish(tmp_path, "a"), _publish(tmp_path, "b")
    assert (a / "pipeline.yml").read_text() == (b / "pipeline.yml").read_text()
    assert (a / "main.nf").read_text() == (b / "main.nf").read_text()


def test_publish_holds_no_filesystem_path(tmp_path):
    """No paths, no timestamps. A published artifact names a layer, never a directory."""
    out = _publish(tmp_path)
    for name in ("pipeline.yml", "main.nf", "nextflow.config"):
        assert str(ROOT) not in (out / name).read_text()


def test_publish_reports_what_still_needs_review(tmp_path, capsys):
    """Federation §5.3: a published pipeline still carries its tier-4 flags."""
    _publish(tmp_path)
    err = capsys.readouterr().err
    assert "requiring review" in err
    assert "star_align.seq_platform" in err


def test_publish_refuses_a_nonconformant_contract(tmp_path):
    """Conformance guards the door with no undo too.

    Plan 1.6 made `build` refuse a contract that disagrees with its module. Publishing is
    strictly worse to get wrong — a build you can rerun, a pipeline you have handed to
    someone you cannot — so it must not be the looser path.
    """
    import shutil

    out = _built(tmp_path)
    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    star = next(layer.rglob("star-align.yml"))
    star.write_text(star.read_text().replace("nf_process: STAR_ALIGN", "nf_process: STAR_ALIGNN"))

    code = main(
        ["publish", str(out / "pipeline.yml"), "--root", str(ROOT), "--registry", str(layer)]
    )
    assert code == 2


def test_publish_refuses_a_directory_that_has_diverged_from_its_file(tmp_path, capsys):
    """MD0213 on the door with no undo.

    `emit` reports staleness and cures it — it is the verb that regenerates. `publish` stamps
    a verdict onto files, so a `main.nf` generated from a different `pipeline.yml` than the
    one being read makes that verdict a statement about nothing.
    """
    out = _built(tmp_path)
    path = out / "pipeline.yml"
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if line.strip() == "- name: seq_platform")
    lines[at + 1] = lines[at + 1].replace("value: null", "value: nanopore")
    path.write_text("".join(lines))

    code = main(["publish", str(path), "--root", str(ROOT)])
    assert code == 2
    assert "MD0213" in capsys.readouterr().err


def test_publish_refuses_a_hand_edited_main_nf(tmp_path, capsys):
    """MD0214, same door. Certifying files somebody edited by hand certifies the edit."""
    out = _built(tmp_path)
    (out / "main.nf").write_text((out / "main.nf").read_text() + "\n// touched\n")
    code = main(["publish", str(out / "pipeline.yml"), "--root", str(ROOT)])
    assert code == 2
    assert "MD0214" in capsys.readouterr().err
