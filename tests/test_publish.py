"""`mendel publish` — the artifact, written to disk.

It writes files and sends nothing. Transmitting them is a later, separate act, which is
the right shape: a person can read what they are about to publish. Publication is the door
with no undo, and this is the half of it that can be undone.
"""

import json
import pathlib

import yaml
from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _publish(tmp_path, name="p"):
    out = tmp_path / name
    code = main(["publish", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)])
    assert code == 0
    return out


def test_publish_writes_a_bundle_and_a_lockfile(tmp_path):
    out = _publish(tmp_path)
    assert (out / "pipeline.bundle.json").exists()
    assert (out / "mendel.lock.yml").exists()


def test_the_bundle_carries_all_four_parts(tmp_path):
    """Federation 4.1: goal, IR, decisions, lockfile. Fewer than four is not reproducible."""
    bundle = json.loads((_publish(tmp_path) / "pipeline.bundle.json").read_text())
    assert set(bundle) == {"goal", "ir", "decisions", "lockfile"}
    assert bundle["goal"]["want"] == ["counts.matrix"]
    assert len(bundle["ir"]["nodes"]) == 5


def test_the_lockfile_pins_every_module_used(tmp_path):
    out = _publish(tmp_path)
    lock = yaml.safe_load((out / "mendel.lock.yml").read_text())
    ir = json.loads((out / "pipeline.bundle.json").read_text())["ir"]
    assert {c["id"] for c in lock["contracts"]} == {n["contract_id"] for n in ir["nodes"]}


def test_the_bundle_records_which_layers_built_it(tmp_path):
    bundle = json.loads((_publish(tmp_path) / "pipeline.bundle.json").read_text())
    assert bundle["ir"]["registry_layers"] == ["registry"]


def test_publishing_twice_produces_identical_bytes(tmp_path):
    """Determinism, applied to the artifact people share. No timestamps anywhere."""
    a, b = _publish(tmp_path, "a"), _publish(tmp_path, "b")
    assert (a / "pipeline.bundle.json").read_text() == (b / "pipeline.bundle.json").read_text()
    assert (a / "mendel.lock.yml").read_text() == (b / "mendel.lock.yml").read_text()


def test_publish_holds_no_filesystem_path(tmp_path):
    out = _publish(tmp_path)
    for name in ("pipeline.bundle.json", "mendel.lock.yml"):
        assert str(ROOT) not in (out / name).read_text()


def test_publish_reports_what_still_needs_review(tmp_path, capsys):
    """Federation 5.3: a published pipeline still carries its tier-4 flags."""
    _publish(tmp_path)
    err = capsys.readouterr().err
    assert "requiring review" in err
    assert "star_align.seq_platform" in err


def test_publish_refuses_a_nonconformant_contract(tmp_path):
    """Conformance guards the door with no undo too.

    Plan 1.6 made `build` refuse a contract that disagrees with its module. Publishing is
    strictly worse to get wrong — a build you can rerun, a bundle you have handed to
    someone you cannot — so it must not be the looser path.
    """
    import shutil

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    star = next(layer.rglob("star-align.yml"))
    star.write_text(star.read_text().replace("nf_process: STAR_ALIGN", "nf_process: STAR_ALIGNN"))

    code = main(
        [
            "publish",
            "--goal",
            str(GOAL),
            "--out",
            str(tmp_path / "p"),
            "--root",
            str(ROOT),
            "--registry",
            str(layer),
        ]
    )
    assert code == 2
    assert not (tmp_path / "p" / "pipeline.bundle.json").exists()


def test_a_published_bundle_reads_back(tmp_path):
    """`mendel upgrade` reads one off disk in Task 7. A bundle that only serialises is
    half an artifact — and this is exactly how `review_level` broke in Plan 1.5."""
    from comeni_core.egress import PublishBundle

    text = (_publish(tmp_path) / "pipeline.bundle.json").read_text()
    bundle = PublishBundle.model_validate_json(text)
    assert bundle.goal.want == ["counts.matrix"]
    assert bundle.lockfile.contracts
    assert bundle.model_dump_json(indent=2) == text
