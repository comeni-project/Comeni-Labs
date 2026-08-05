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
    layer = tmp_path / "examples"
    shutil.copytree(ROOT / "examples", layer)
    edit(layer)
    return layer


def test_upgrading_against_an_unchanged_registry_reports_nothing(tmp_path, capsys):
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
    assert "no changes" in capsys.readouterr().err


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
    ir = json.loads((tmp_path / "up" / "pipeline.ir.json").read_text())
    replayed = [d for d in ir["decisions"] if d["resolved_by"] == "replay"]
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
