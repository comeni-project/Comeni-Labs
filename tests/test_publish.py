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
import shutil

import yaml
from mendel_compiler.cli import artifact_verbs, main
from mendel_compiler.gates import GateResult

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def _gate_always_passes(monkeypatch):
    """Stub the gate so a `--gate` test runs without Nextflow (as CI's fast lane lacks it).

    The gate is incidental to what these tests assert — publish's re-resolution behaviour and
    the verdict round trip — so stubbing the tool keeps the real assertion running in CI rather
    than skipping it. The gates themselves are exercised for real by `-m slow` and `test_gates`.
    """
    monkeypatch.setattr(
        artifact_verbs, "run_gate", lambda gate, out: GateResult(gate=gate, passed=True))

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
        "ai",
        "steps",
        "channels",
        "input_form",
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
    from comeni_core.artifact.digest import digest_of_bytes

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


def test_conformance_guards_the_door_at_build_since_publish_no_longer_re_resolves(tmp_path):
    """Conformance guards the door with no undo — at build, which is where it can.

    Plan 1.6 made `build` refuse a contract that disagrees with its module. A50 makes `publish`
    certify the self-contained artifact without re-resolving, so it reads no registry and cannot
    re-run conformance — exactly as `emit` already trusted the artifact. The guarantee did not
    weaken, it relocated: a published artifact is a *built* one (`publish` refuses a directory
    that has diverged from its `pipeline.yml`), and `build` refuses a non-conformant contract
    before the artifact exists. Editing the registry after the fact cannot make a conformant
    artifact non-conformant — the contracts are pinned by digest and the files are already on
    disk. This test asserts the guarantee at its real home.
    """
    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    star = next(layer.rglob("align/contract.yml"))
    star.write_text(
        _declared(
            star,
            star.read_text().replace("nf_process: STAR_ALIGN", "nf_process: STAR_ALIGNN")))

    goal = ROOT / "examples" / "rnaseq-goal.yml"
    code = main(
        ["build", "--goal", str(goal), "--out", str(tmp_path / "b"),
         "--root", str(ROOT), "--registry", str(layer)]
    )
    assert code == 2  # the non-conformant contract never reaches a publishable artifact


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
    path.write_text(_declared(path, "".join(lines)))

    code = main(["publish", str(path), "--root", str(ROOT)])
    assert code == 2
    assert "MD0213" in capsys.readouterr().err


def test_publish_refuses_a_hand_edited_main_nf(tmp_path, capsys):
    """MD0214, same door. Certifying files somebody edited by hand certifies the edit."""
    out = _built(tmp_path)
    (out / "main.nf").write_text(
        _declared(
            out / "main.nf",
            (out / "main.nf").read_text() + "\n// touched\n"))
    code = main(["publish", str(out / "pipeline.yml"), "--root", str(ROOT)])
    assert code == 2
    assert "MD0214" in capsys.readouterr().err


# --- A50: publish certifies the on-disk artifact, without re-resolving ---


def test_publish_does_not_re_resolve_against_the_installed_registry(tmp_path, monkeypatch):
    """publish shared upgrade's path: it re-resolved against whatever --registry was installed,
    silently swapping the aligner and erasing a human override, then stamped a gate on the
    result — the door with no undo certifying a pipeline nobody read. It must certify what is
    on disk and change nothing else."""
    _gate_always_passes(monkeypatch)
    root = ROOT
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(root / "registry"),
                 "--out", str(out), "--root", str(root)]) == 0
    before = (out / "pipeline.yml").read_text()

    # An overlay that would reroute the aligner if publish re-resolved. Bump the priority
    # by hand, without regex — `comeni-core` bans `re`, and a test mirrors that discipline.
    ov = tmp_path / "ov"
    (ov / "contracts" / "nf-core").mkdir(parents=True)
    (ov / "registry.yml").write_text(_declared(ov / "registry.yml", "name: lab\n"))
    h = (root / "registry/tools/nf-core/hisat2/align/contract.yml").read_text()
    lines = [("priority: 99" if line.strip().startswith("priority:") else line)
             for line in h.splitlines()]
    (ov / "tools/nf-core/hisat2/align/contract.yml").parent.mkdir(parents=True, exist_ok=True)
    (ov / "tools/nf-core/hisat2/align/contract.yml").write_text(
        _declared(ov / "tools/nf-core/hisat2/align/contract.yml", "\n".join(lines) + "\n")
    )

    assert main(["publish", str(out / "pipeline.yml"), "--registry", str(root / "registry"),
                 "--registry", str(ov), "--gate", "lint", "--root", str(root)]) == 0
    after = (out / "pipeline.yml").read_text()
    assert yaml.safe_load(after)["gate"] == "lint"  # verdict stamped
    b, a = yaml.safe_load(before), yaml.safe_load(after)
    assert b["steps"] == a["steps"], "publish must not re-resolve and move the pipeline"
    assert b["decisions"] == a["decisions"], "publish must not touch the recorded decisions"


def test_edit_then_emit_then_publish_certifies_the_edited_pipeline(tmp_path, monkeypatch):
    """The legitimate 'I changed my mind and want to publish the result' flow. publish does not
    re-resolve, so the edit is surfaced by emit (MD0213) and the published pipeline is the
    emitted one — nothing hidden."""
    import yaml as _yaml
    from mendel_compiler.cli import main

    _gate_always_passes(monkeypatch)
    root = pathlib.Path(__file__).parent.parent
    goal = root / "examples" / "rnaseq-goal.yml"
    out = tmp_path / "b"
    assert main(["build", "--goal", str(goal), "--out", str(out), "--root", str(root)]) == 0
    # Answer a tier-4 question by editing the file, then emit, then publish.
    doc = _yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
    (out / "pipeline.yml").write_text(
        _declared(
            out / "pipeline.yml",
            _yaml.safe_dump(doc, sort_keys=False)))
    assert main(["emit", str(out / "pipeline.yml"), "--out", str(out)]) == 0
    assert main(["publish", str(out / "pipeline.yml"), "--gate", "lint", "--root", str(root)]) == 0
    assert "'PL:nanopore'" in (out / "nextflow.config").read_text()
    assert _yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"


def test_publish_refuses_a_pipeline_with_no_emitted_record(tmp_path, capsys):
    """A70. `hand_edited` (MD0214) and `is_stale` (MD0213) both return "nothing to compare"
    when `pipeline.emitted is None` — a supported state, since an archived or hand-authored
    file has no `emitted:` block. That is correct for those two functions and wrong for a
    *certifying* verb: publish's only tie between `main.nf` and `pipeline.yml` goes silent,
    so it gates whatever is on disk and stamps the verdict onto an artifact that then
    permanently claims it emitted that file.

    Round four published an RNA-seq pipeline whose recorded `main.nf` digest belonged to an
    unrelated workflow, at exit 0. Publish is the door with no undo.
    """
    out = _built(tmp_path)
    source = out / "pipeline.yml"
    doc = yaml.safe_load(source.read_text())
    del doc["emitted"]
    source.write_text(_declared(source, yaml.safe_dump(doc, sort_keys=False)))
    (out / "main.nf").write_text(_declared(out / "main.nf", "workflow { }\n"))

    code = main(["publish", str(source), "--root", str(ROOT)])

    assert code == 2, "publish certified a main.nf with nothing tying it to pipeline.yml"
    assert "MD0222" in capsys.readouterr().err


def test_emit_still_works_on_a_pipeline_with_no_emitted_record(tmp_path):
    """The other half. `emit` is the *cure* for a missing `emitted:` block — it regenerates
    the files and stamps the record, after which MD0213 and MD0214 mean something again — so
    the refusal must sit on the certifying verbs and not on this one. Refusing here would
    leave an archived pipeline with no way forward at all.
    """
    out = _built(tmp_path)
    source = out / "pipeline.yml"
    doc = yaml.safe_load(source.read_text())
    del doc["emitted"]
    source.write_text(_declared(source, yaml.safe_dump(doc, sort_keys=False)))

    assert main(["emit", str(source), "--out", str(out)]) == 0
    assert yaml.safe_load(source.read_text()).get("emitted"), "emit did not restamp the record"


def test_upgrade_reports_a_missing_emitted_record_rather_than_refusing(tmp_path, capsys):
    """A70's scope, asserted so the asymmetry is a decision rather than an oversight.

    `MD0222` is on `publish` alone. `upgrade` meets the same missing evidence and already
    answers it honestly — "predates the emitted-artifact record", never "byte-identical" —
    and the difference is what each verb does with the answer: upgrade produces a report a
    person reads, publish stamps a verdict onto the artifact. Only one is a claim about files
    nobody checked, and only one has no undo.
    """
    out = _built(tmp_path)
    source = out / "pipeline.yml"
    doc = yaml.safe_load(source.read_text())
    del doc["emitted"]
    source.write_text(_declared(source, yaml.safe_dump(doc, sort_keys=False)))

    code = main(["upgrade", str(source), "--out", str(tmp_path / "up"), "--root", str(ROOT)])

    err = capsys.readouterr().err
    assert code == 0, "upgrade refused where it should report"
    assert "MD0222" not in err
    assert "predates the emitted-artifact record" in err


def test_publish_refuses_to_certify_a_value_whose_reason_is_false(tmp_path, capsys):
    """A104's sharp end. `publish` is the door with no undo, and it stamped this at exit 0.

    The audit edited `min_mqs` 0 → 30, emitted `-Q 30`, and `mendel publish --gate lint`
    certified a pipeline whose record said `tier: 2 / source: resolver / reason: contract
    default for min_mqs` — all three false about the value that reached the tool.
    """
    out = tmp_path / "p"
    assert main(["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0

    path = out / "pipeline.yml"
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if line.strip() == "- name: min_mqs")
    lines[at + 1] = "    value: 30\n"
    path.write_text(_declared(path, "".join(lines)))

    code = main(["publish", str(path), "--root", str(ROOT)])

    assert code != 0
    assert "MD0223" in capsys.readouterr().err
