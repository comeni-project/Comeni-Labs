"""`mendel upgrade` — re-resolve a locked pipeline and say what moved.

Federation §4.3: "re-resolves a locked pipeline against the current registry and reports
what moved, at which tier, and why. Nothing upgrades implicitly."
"""

import json
import pathlib
import shutil

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _published(tmp_path):
    out = tmp_path / "published"
    assert main(["publish", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    return out / "pipeline.bundle.json"


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
            "--bundle",
            str(bundle),
            "--out",
            str(tmp_path / "up"),
            "--root",
            str(ROOT),
        ]
    )
    assert code == 0
    err = capsys.readouterr().err
    assert "the generated pipeline is byte-identical to the bundle" in err
    assert "CHANGED" not in err


def test_upgrading_reproduces_byte_identical_nextflow(tmp_path):
    """Federation 4.1: loading a locked pipeline reproduces byte-identical Nextflow."""
    bundle = _published(tmp_path)
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
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
            "--bundle",
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
            "--bundle",
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
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    import yaml

    pipeline = yaml.safe_load((tmp_path / "up" / "pipeline.yml").read_text())
    replayed = [d for d in pipeline["decisions"] if d["resolved_by"] == "replay"]
    assert replayed, "a recorded decision should have replayed rather than been re-asked"


def test_upgrade_never_writes_over_the_bundle_it_read(tmp_path):
    """Nothing upgrades implicitly. The old bundle is evidence."""
    bundle = _published(tmp_path)
    before = bundle.read_text()
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    assert bundle.read_text() == before


def test_upgrade_says_how_many_decisions_replayed(tmp_path, capsys):
    """A count a person can sanity-check. "Only what you touched moved" is a claim, and
    this is the number that supports or refutes it."""
    bundle = _published(tmp_path)
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
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
            "--bundle", str(bundle),
            "--out", str(tmp_path / "up"),
            "--root", str(ROOT),
            "--registry", str(layer),
        ]
    )

    err = capsys.readouterr().err
    assert code == 0
    assert "the generated pipeline differs: nextflow.config" in err
    assert "no IR change explains it" in err, err


def test_a_bundle_predating_the_record_says_so_rather_than_claiming_identity(tmp_path, capsys):
    """`None` is no evidence, not a clean bill of health — the distinction `gate` makes."""
    bundle = _published(tmp_path)
    data = json.loads(bundle.read_text())
    data["emitted"] = None
    bundle.write_text(json.dumps(data))

    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])

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
        "publish", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT),
        "--registry", str(ROOT / "registry"), "--registry", str(lab),
    ]) == 0

    code = main([
        "upgrade", "--bundle", str(out / "pipeline.bundle.json"),
        "--out", str(tmp_path / "up"), "--root", str(ROOT),
    ])

    err = capsys.readouterr().err
    assert code == 0
    assert "DRIFT" in err and "no longer in the registry" in err
    assert "the generated pipeline differs" in err
    assert "samtools_sort" in err, "and the diff names what changed"


# --- Plan 1.10 Task 9: the five categories, at the command line -----------------------


def _with_override(bundle, key, subject, value, node_exists=True):
    """Answer a recorded flag in a published bundle, the way a reviewer would.

    **Fills in the existing record for that key rather than appending one.** Appending was
    the first draft and it silently did nothing: `ReplayResolver` takes the *first* record
    per key — two for one key is a corrupt bundle rather than a choice — so the duplicate
    override lost to the unanswered record already there. Answering a question means editing
    the question, which is also what a person handed this file would do.
    """
    data = json.loads(bundle.read_text())
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
    assert node_exists or key.split(".")[0] not in [n["id"] for n in data["ir"]["nodes"]]
    bundle.write_text(json.dumps(data, indent=2))
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
        ["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)]
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
        ["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)]
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
        ["upgrade", "--bundle", str(bundle), "--out", str(out), "--root", str(ROOT)]
    ) == 2
    assert not (out / "pipeline.bundle.json").exists()
