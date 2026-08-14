"""`mendel upgrade` — re-resolve a locked pipeline and say what moved.

Federation §4.3: "re-resolves a locked pipeline against the current registry and reports
what moved, at which tier, and why. Nothing upgrades implicitly."
"""

import pathlib
import shutil

import yaml
from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _published(tmp_path, name="published"):
    """A published pipeline directory, and the file that names it.

    `pipeline.bundle.json` retired in Plan 1.10 Task 10: everything it held is in
    `pipeline.yml`, and the directory is the artifact. `publish` is now a check over a built
    directory rather than a second writer beside `build`.
    """
    out = tmp_path / name
    assert main(["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    assert main(["publish", str(out / "pipeline.yml"), "--root", str(ROOT)]) == 0
    return out / "pipeline.yml"


def _registry_with(tmp_path, edit):
    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    edit(layer)
    return layer


def test_upgrading_against_an_unchanged_registry_reports_nothing(tmp_path, capsys):
    """A28 — the verdict is about the artifact, so this is what "nothing changed" means.

    It said "no changes: this pipeline re-resolves identically", which was a claim about
    `diff_ir`'s field list rather than about the pipeline. The sentence is now about the
    bytes, and `diff_ir` explains rather than decides.
    """
    bundle = _published(tmp_path)
    code = main(
        [
            "upgrade",
            str(bundle),
            "--out",
            str(tmp_path / "up"),
            "--root",
            str(ROOT),
        ]
    )
    assert code == 0
    err = capsys.readouterr().err
    assert "the generated pipeline is byte-identical to the one recorded" in err
    assert "CHANGED" not in err


def test_upgrading_reproduces_byte_identical_nextflow(tmp_path):
    """Federation 4.1: loading a locked pipeline reproduces byte-identical Nextflow."""
    bundle = _published(tmp_path)
    main(["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    assert (tmp_path / "up" / "main.nf").read_text() == (
        tmp_path / "published" / "main.nf"
    ).read_text()


def test_a_changed_rule_is_reported_with_its_tier_and_reason(tmp_path, capsys):
    """The registry's one genuine rule chooses an aligner from the measured read length.

    The plan tested a `param: strandedness` rule here; Plan 1.5 deleted that rule, because
    `-s 2` was featureCounts' encoding of a fact rather than a decision. Swapping the
    aligner rows is the same test against the decision that actually exists — and a better
    one, since a module change is what a reader most needs to see.
    """

    def swap_aligners(layer):
        rules = layer / "rules" / "rnaseq.yml"
        rules.write_text(
            rules.read_text()
            .replace("then: nf-core/star/align@1.11.0", "then: PLACEHOLDER")
            .replace("then: nf-core/hisat2/align@2.2.2", "then: nf-core/star/align@1.11.0")
            .replace("then: PLACEHOLDER", "then: nf-core/hisat2/align@2.2.2")
        )

    bundle = _published(tmp_path)
    layer = _registry_with(tmp_path, swap_aligners)
    main(
        [
            "upgrade",
            str(bundle),
            "--out",
            str(tmp_path / "up"),
            "--root",
            str(ROOT),
            "--registry",
            str(layer),
        ]
    )
    err = capsys.readouterr().err
    assert "CHANGED" in err
    assert "star/align" in err and "hisat2/align" in err
    assert "tier 3" in err, "a rule-driven module change is data-profiled"
    assert "Dobin" in err, "the citation is the reason, and a reader needs it"


def test_drift_is_reported_even_when_nothing_resolved_differently(tmp_path, capsys):
    """A contract can be edited in ways that do not change this pipeline. Say so anyway —
    the lockfile no longer describes what is on disk, and that is worth knowing."""

    def touch(layer):
        sort = next(layer.rglob("samtools-sort.yml"))
        sort.write_text(sort.read_text().replace("priority: 0", "priority: 3"))

    bundle = _published(tmp_path)
    layer = _registry_with(tmp_path, touch)
    main(
        [
            "upgrade",
            str(bundle),
            "--out",
            str(tmp_path / "up"),
            "--root",
            str(ROOT),
            "--registry",
            str(layer),
        ]
    )
    err = capsys.readouterr().err
    assert "has been edited since it was locked" in err


def test_untouched_decisions_replay(tmp_path, capsys):
    """The curation property. A tier-4 decision recorded before must not be re-asked."""
    bundle = _published(tmp_path)
    main(["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    import yaml

    pipeline = yaml.safe_load((tmp_path / "up" / "pipeline.yml").read_text())
    replayed = [d for d in pipeline["decisions"] if d["resolved_by"] == "replay"]
    assert replayed, "a recorded decision should have replayed rather than been re-asked"


def test_upgrade_never_writes_over_the_pipeline_it_read(tmp_path):
    """Nothing upgrades implicitly. What you had is the evidence.

    Two subjects since Plan 1.10, and the second is why the rule got sharper rather than
    easier. With a bundle in and a report out there was nothing to collide; with one artifact
    the natural implementation updates `pipeline.yml` where it sits, destroying the only
    record of what you had — the replayed overrides, the previous digests, the gate evidence.
    """
    bundle = _published(tmp_path)
    before = bundle.read_text()
    main(["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    assert bundle.read_text() == before


def test_upgrade_refuses_to_write_into_the_directory_it_read(tmp_path, capsys):
    """The collision the sentence above describes, refused rather than trusted not to happen."""
    bundle = _published(tmp_path)
    code = main(["upgrade", str(bundle), "--out", str(bundle.parent), "--root", str(ROOT)])
    assert code == 2
    assert "must not write over the pipeline it read" in capsys.readouterr().err


def test_upgrade_says_how_many_decisions_replayed(tmp_path, capsys):
    """A count a person can sanity-check. "Only what you touched moved" is a claim, and
    this is the number that supports or refutes it."""
    bundle = _published(tmp_path)
    main(["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    err = capsys.readouterr().err
    assert "decisions replayed" in err
    assert "0 newly asked" in err


def test_a_change_the_diff_cannot_see_still_reports_that_the_pipeline_moved(tmp_path, capsys):
    """A28 — the verdict used to be a claim about `diff_ir`'s field list.

    `ext_args` is a contract field that reaches `nextflow.config` — it is how a flag gets
    to a tool at all — and `diff_ir` compares contract ids, parameter values, tiers and now
    edges. Not that. So editing it moves the artifact and leaves the diff with nothing to
    say, which is exactly the shape that printed *"no changes: this pipeline re-resolves
    identically"* over generated files that had visibly changed.

    Both halves are asserted: the verdict is right, and the tool says out loud that nothing
    explains it rather than leaving a reader to assume the diff is complete.
    """
    bundle = _published(tmp_path)
    layer = _registry_with(
        tmp_path,
        lambda root: (root / "contracts" / "nf-core" / "star-align.yml").write_text(
            (root / "contracts" / "nf-core" / "star-align.yml")
            .read_text()
            .replace(
                'ext_args: "--readFilesCommand zcat"',
                'ext_args: "--readFilesCommand zcat --outSAMattributes All"',
            )
        ),
    )

    code = main(
        [
            "upgrade",
            str(bundle),
            "--out", str(tmp_path / "up"),
            "--root", str(ROOT),
            "--registry", str(layer),
        ]
    )

    err = capsys.readouterr().err
    assert code == 0
    assert "the generated pipeline differs: nextflow.config" in err
    assert "no recorded change explains it" in err, err


def test_a_pipeline_predating_the_record_says_so_rather_than_claiming_identity(tmp_path, capsys):
    """`None` is no evidence, not a clean bill of health — the distinction `gate` makes."""
    bundle = _published(tmp_path)
    data = yaml.safe_load(bundle.read_text())
    data["emitted"] = None
    bundle.write_text(yaml.safe_dump(data, sort_keys=False))

    main(["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])

    err = capsys.readouterr().err
    assert "predates the emitted-artifact record" in err
    assert "byte-identical" not in err


def test_upgrading_without_the_overlay_that_built_it_reports_rather_than_crashes(tmp_path, capsys):
    """Why the digest is *recorded* rather than the old IR re-emitted.

    Re-emitting needs the registry as it was, and a contract that is no longer in the
    registry is one of the two cases upgrade exists to report — so the obvious
    implementation dies with `KeyError` on exactly the case it was written for.
    `drift_against` had this bug in Plan 1.7, for the same reason: do not reconstruct the
    past, record it.

    Published against two layers, upgraded against one. The overlay's sorter is locked and
    gone; the base's takes over, so the pipeline still routes and the report is a report
    rather than a crash.
    """
    lab = tmp_path / "lab-registry"
    (lab / "contracts").mkdir(parents=True)
    (lab / "contracts" / "rival-sorter.yml").write_text(
        (ROOT / "registry" / "contracts" / "nf-core" / "samtools-sort.yml")
        .read_text()
        .replace("nf-core/samtools/sort@1.21.0", "lab/rival/sorter@9.9.9")
        # A different module as well as a different id: conformance reads `nf_include`,
        # so pointing the process elsewhere makes it `unverified` rather than wrong.
        .replace("nf_process: SAMTOOLS_SORT", "nf_process: RIVAL_SORT")
        .replace(
            "nf_include: modules/nf-core/samtools/sort/main",
            "nf_include: modules/lab/rival/sort/main",
        )
        .replace("priority: 0", "priority: 99")
    )
    out = tmp_path / "published-with-overlay"
    assert main([
        "build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT),
        "--registry", str(ROOT / "registry"), "--registry", str(lab),
    ]) == 0

    code = main([
        "upgrade", str(out / "pipeline.yml"),
        "--out", str(tmp_path / "up"), "--root", str(ROOT),
    ])

    err = capsys.readouterr().err
    assert code == 0
    assert "DRIFT" in err and "no longer in the registry" in err
    assert "the generated pipeline differs" in err
    assert "samtools_sort" in err, "and the diff names what changed"


# --- Plan 1.10 Task 9: the five categories, at the command line -----------------------


def _with_override(bundle, key, subject, value, node_exists=True):
    """Answer a recorded flag in `pipeline.yml`, the way a reviewer would.

    **Fills in the existing record for that key rather than appending one.** Appending was
    the first draft and it silently did nothing: `ReplayResolver` takes the *first* record
    per key — two for one key is a corrupt bundle rather than a choice — so the duplicate
    override lost to the unanswered record already there. Answering a question means editing
    the question, which is also what a person handed this file would do.
    """
    data = yaml.safe_load(bundle.read_text())
    existing = next((d for d in data["decisions"] if d["key"] == key), None)
    if existing is not None:
        existing["human_override"] = value
    else:
        data["decisions"].append(
            {
                "kind": "param",
                "key": key,
                "subject": subject,
                "candidates": [None],
                "chosen": None,
                "human_override": value,
                "reason": "our sequencer",
                "confidence": 0.0,
                "resolved_by": "human",
                "tier": 4,
            }
        )
    assert node_exists or key.split(".")[0] not in [s["id"] for s in data["steps"]]
    bundle.write_text(yaml.safe_dump(data, sort_keys=False))
    # Editing the file leaves the generated Nextflow describing the version before the edit,
    # so `upgrade` refuses with MD0213 until it is re-emitted. That is the workflow, not a
    # detour: `mendel emit` is the verb that makes a directory describe itself again.
    assert main(["emit", str(bundle), "--out", str(bundle.parent)]) == 0
    return bundle


def test_an_orphaned_override_refuses_and_names_the_code(tmp_path, capsys):
    """`resolve()` is never called for a step that is gone, so nothing in the resolver could
    see this. It refuses rather than warns: a stale answer is re-asked and flagged, and an
    orphaned one has nothing left to be an answer to. Dropping it quietly is the same failure
    as a guard that silently stops guarding."""
    bundle = _with_override(
        _published(tmp_path), "hisat2_align.seq_platform", "seq_platform", "illumina",
        node_exists=False,
    )
    code = main(
        ["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)]
    )
    err = capsys.readouterr().err
    assert code == 2
    assert "MD0203" in err
    assert "ORPHANED hisat2_align.seq_platform" in err


def test_an_override_that_still_applies_is_replayed_rather_than_orphaned(tmp_path, capsys):
    """The regression guard for the refusal above: it must depend on the step being gone,
    not on an override existing."""
    bundle = _with_override(
        _published(tmp_path), "star_align.seq_platform", "seq_platform", "illumina"
    )
    code = main(
        ["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)]
    )
    err = capsys.readouterr().err
    assert code == 0, err
    assert "ORPHANED" not in err
    assert "ANSWERED star_align.seq_platform = 'illumina'" in err


def test_a_refused_upgrade_publishes_nothing(tmp_path):
    """A4's posture, applied to this refusal too. `upgrade` already took it for a failed
    gate; an orphaned override must not leave a directory behind that looks upgraded."""
    bundle = _with_override(
        _published(tmp_path), "hisat2_align.seq_platform", "seq_platform", "illumina",
        node_exists=False,
    )
    out = tmp_path / "up"
    assert main(
        ["upgrade", str(bundle), "--out", str(out), "--root", str(ROOT)]
    ) == 2
    assert not (out / "pipeline.yml").exists()


# --- Plan 1.10 Task 10: the four verbs -------------------------------------------------


def _snapshot(directory):
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_emit_needs_no_registry_and_no_network(tmp_path):
    """The verb that regenerates a pipeline from its own file, years later.

    `--registry` is not passed and none is loaded — `emit` is handled before the loader runs,
    so this would fail rather than quietly fall back to a default layer.
    """
    bundle = _published(tmp_path)
    assert main(["emit", str(bundle), "--out", str(bundle.parent)]) == 0


def test_dry_run_writes_nothing(tmp_path):
    """`verify` is this, and not a separate verb.

    A digest-only compare was the alternative and it answers a strictly weaker question: it
    can say a contract moved, but not whether the pipeline would resolve differently. Two
    comparisons of "is this still what it says it is" is root D's finding waiting to happen,
    so `--dry-run` differs from `upgrade` only in whether bytes are written.
    """
    bundle = _published(tmp_path)
    before = _snapshot(bundle.parent)
    code = main(["upgrade", str(bundle), "--dry-run", "--root", str(ROOT)])
    assert code == 0
    assert _snapshot(bundle.parent) == before


def test_dry_run_reports_the_same_categories_upgrade_does(tmp_path, capsys):
    """One code path, one answer. The flag decides whether bytes are written and nothing
    else, so a report that differed between the two would mean two implementations."""
    bundle = _published(tmp_path)
    main(["upgrade", str(bundle), "--dry-run", "--root", str(ROOT)])
    dry = capsys.readouterr().err
    main(["upgrade", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    wet = capsys.readouterr().err
    assert "byte-identical" in dry
    assert "decisions replayed" in dry
    for line in dry.splitlines():
        assert line in wet, line


def test_dry_run_is_refused_on_a_verb_with_nothing_to_compare(tmp_path):
    """A flag that silently means "do nothing" is worse than no flag."""
    import pytest

    with pytest.raises(SystemExit):
        main(["build", "--goal", str(GOAL), "--out", str(tmp_path / "b"), "--dry-run"])


def test_a_replayed_value_frozen_against_a_moved_contract_is_reported(tmp_path, capsys):
    """MD0202. `DRIFT` says a contract you pinned was edited; this says the consequence.

    Both are true and neither implies the other — a contract can be edited in ways that touch
    nothing here, and a value can be replayed from a contract that has not moved at all.
    Reporting only the first leaves a reader to work out the part that affects the numbers.
    """
    bundle = _published(tmp_path)

    def bump_a_default(layer):
        counts = next(layer.rglob("subread-featurecounts.yml"))
        counts.write_text(counts.read_text().replace("priority: 0", "priority: 4"))

    layer = _registry_with(tmp_path, bump_a_default)
    code = main([
        "upgrade", str(bundle), "--dry-run", "--root", str(ROOT), "--registry", str(layer),
    ])
    err = capsys.readouterr().err
    assert code == 0
    assert "MD0202" in err
    assert "min_mqs" in err, "it must name which values are frozen, not just that some are"
    assert "DRIFT" in err, "and drift stays its own statement"


def test_md0202_is_silent_when_nothing_moved(tmp_path, capsys):
    """The regression guard: it must depend on the contract having been edited."""
    bundle = _published(tmp_path)
    main(["upgrade", str(bundle), "--dry-run", "--root", str(ROOT)])
    assert "MD0202" not in capsys.readouterr().err


# --- A53: `upgrade --out` refuses another pipeline's directory ---


def _a_and_a_different_b(tmp_path):
    """A built from the base registry, B from an overlay that bumps a default — so B is a
    genuinely different pipeline, not a byte-identical rebuild the guard would (rightly) allow."""
    def bump(layer):
        counts = next(layer.rglob("subread-featurecounts.yml"))
        counts.write_text(counts.read_text().replace("priority: 0", "priority: 7"))

    a, b = tmp_path / "A", tmp_path / "B"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--out", str(a), "--root", str(ROOT)]) == 0
    layer = _registry_with(tmp_path, bump)
    assert main(["build", "--goal", str(GOAL), "--registry", str(layer),
                 "--out", str(b), "--root", str(ROOT)]) == 0
    return a, b


def test_upgrade_refuses_to_overwrite_another_pipeline(tmp_path):
    """`--out` is a fresh directory or the same one refused as in-place — but a *different*
    pipeline's directory is neither, and upgrading A into B silently destroyed B: the replayed
    overrides, the previous digests, the gate evidence, all of it. Refuse absent `--force`."""
    a, b = _a_and_a_different_b(tmp_path)
    before = (b / "pipeline.yml").read_text()
    code = main(["upgrade", str(a / "pipeline.yml"), "--registry", str(ROOT / "registry"),
                 "--out", str(b), "--root", str(ROOT)])
    assert code == 2, "B holds a different pipeline.yml — refused absent --force"
    assert (b / "pipeline.yml").read_text() == before, "the refusal must leave B untouched"


def test_upgrade_force_overwrites_another_pipeline(tmp_path):
    """`--force` is the escape hatch: a person who means to replace B says so."""
    a, b = _a_and_a_different_b(tmp_path)
    code = main(["upgrade", str(a / "pipeline.yml"), "--registry", str(ROOT / "registry"),
                 "--out", str(b), "--force", "--root", str(ROOT)])
    assert code == 0


def test_upgrade_into_a_fresh_directory_is_allowed(tmp_path):
    """The normal case must stay cheap — an empty `--out` is not another pipeline."""
    a = tmp_path / "A"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--out", str(a), "--root", str(ROOT)]) == 0
    code = main(["upgrade", str(a / "pipeline.yml"), "--registry", str(ROOT / "registry"),
                 "--out", str(tmp_path / "next"), "--root", str(ROOT)])
    assert code == 0


def test_upgrade_self_guard_sees_a_relative_out(tmp_path, monkeypatch):
    """The in-place refusal compared `out.resolve()` to `source.parent.resolve()` — the
    `.resolve()` A53 flagged as never watched. A relative `--out` that names the source
    directory must still be caught, which only works because both sides are resolved."""
    out = tmp_path / "p"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT / "registry"),
                 "--out", str(out), "--root", str(ROOT)]) == 0
    monkeypatch.chdir(tmp_path)
    code = main(["upgrade", str(out / "pipeline.yml"), "--registry", str(ROOT / "registry"),
                 "--out", "p", "--root", str(ROOT)])
    assert code == 2, "a relative --out onto the source is still in-place"


V1_FIXTURE = ROOT / "docs" / "internal" / "audits" / "fixtures" / "pipeline-v1"


def _archived(tmp_path):
    """A pipeline.yml written before Plan 1.13, with the files it emitted.

    Committed rather than built, and that is the whole point: a fixture produced by the code
    under test cannot demonstrate anything about reading what a laboratory archived. See the
    README beside it.
    """
    out = tmp_path / "archived"
    shutil.copytree(V1_FIXTURE, out)
    (out / "README.md").unlink()
    # A directory a laboratory archived has its vendored modules beside the artifact; the
    # fixture does not carry them because they are ~1 MB of nf-core source that is already in
    # the tree. `emit` refuses without them (`MD0210`), and rightly.
    build = tmp_path / "for-modules"
    assert main(["build", "--goal", str(GOAL), "--out", str(build), "--root", str(ROOT)]) == 0
    shutil.copytree(build / "modules", out / "modules")
    return out / "pipeline.yml"


def test_a_pipeline_written_before_a_schema_change_is_not_reported_as_edited(tmp_path, capsys):
    """The file did not change. The schema did. Say which.

    Found while executing Plan 1.13: `emitted.from_digest` hashes the model dump, so adding
    one field (`CallArg.join`) moved it for **every** archived pipeline and `MD0213` reported
    the file as edited by a human. A laboratory reading that goes looking for an edit nobody
    made — and this plan adds six more fields on top of it.

    The asymmetry is the test: the artifact's self-digest moves while the emitted files still
    hash exactly to their records, which is what says the pipeline did not change.
    """
    archived = _archived(tmp_path)

    code = main(["upgrade", str(archived), "--registry", str(ROOT / "registry"),
                 "--out", str(tmp_path / "up"), "--root", str(ROOT)])

    err = capsys.readouterr().err
    assert "MD0213" not in err, err
    assert "predates the current schema" in err
    assert code == 0


def test_a_genuinely_edited_pipeline_is_still_reported_as_edited(tmp_path, capsys):
    """The negative. A check that can only pass is not a check.

    A pipeline written under the **current** schema, edited by hand. `MD0213` must still fire:
    that is the case it exists for, and buying compatibility by going blind would be a worse
    bug than the one being fixed.
    """
    bundle = _published(tmp_path)
    data = yaml.safe_load(bundle.read_text())
    data["goal"]["want"] = ["counts.matrix", "counts.matrix"]
    bundle.write_text(yaml.safe_dump(data, sort_keys=False))

    main(["upgrade", str(bundle), "--registry", str(ROOT / "registry"),
          "--out", str(tmp_path / "up"), "--root", str(ROOT)])

    assert "MD0213" in capsys.readouterr().err


def test_an_edit_to_a_pre_schema_pipeline_is_not_detectable_and_that_is_stated(tmp_path, capsys):
    """The limitation, asserted rather than left to be discovered.

    For a file written under an older schema the content digest cannot match **either way**,
    so a hand edit and the schema moving are indistinguishable by that mechanism. Nothing can
    recover the distinction after the fact; pretending otherwise would be the dishonest half
    of this repair.

    What still holds is the half that matters: the generated files are checked against their
    own recorded digests (`MD0214`), so an edited `main.nf` is caught regardless of schema.
    And the note tells the reader to restamp, after which edits are detectable again.
    """
    archived = _archived(tmp_path)
    data = yaml.safe_load(archived.read_text())
    data["goal"]["want"] = ["counts.matrix", "counts.matrix"]
    archived.write_text(yaml.safe_dump(data, sort_keys=False))

    main(["upgrade", str(archived), "--registry", str(ROOT / "registry"),
          "--out", str(tmp_path / "up"), "--root", str(ROOT)])

    err = capsys.readouterr().err
    assert "predates the current schema" in err
    assert "to restamp it" in err


def test_emit_does_not_call_a_schema_change_an_edit_either(tmp_path, capsys):
    """The other half, and it was **inert** until this test existed.

    `is_stale` and `cli`'s `upgrade` branch both handle this case, and reverting the
    `is_stale` short-circuit changed nothing — the `upgrade` path never reaches it. `emit`
    does: it prints `MD0213` and then cures it, so without this an archived pipeline would be
    told it had been edited every time somebody regenerated it, by the one verb whose job is
    to fix exactly that.

    Found by reverting a guard written in the same session and watching nothing fail. A14.
    """
    archived = _archived(tmp_path)

    code = main(["emit", str(archived), "--out", str(tmp_path / "archived")])

    assert code == 0
    assert "MD0213" not in capsys.readouterr().err
