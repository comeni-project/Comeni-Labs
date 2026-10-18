"""A built `pipeline.yml` names where each registry layer can be fetched, and the build says
when it cannot be rebuilt from the file alone (Plan B, spec §8.2, §9)."""

import shutil
import subprocess

import yaml
from mendel_compiler.cli import main
from support.paths import ROOT
from support.pipeline import GOAL


def _build(tmp_path, layer, capsys):
    out = tmp_path / "out"
    code = main(["build", "--goal", str(GOAL), "--registry", str(layer), "--out", str(out),
                 "--root", str(ROOT)])
    layers = yaml.safe_load((out / "pipeline.yml").read_text())["registry"]["layers"]
    return code, capsys.readouterr().err, layers


def test_build_warns_for_an_unversioned_layer(tmp_path, capsys):
    copy = tmp_path / "copy"
    shutil.copytree(ROOT / "registry", copy, ignore=shutil.ignore_patterns(".git"))
    code, err, [layer] = _build(tmp_path, copy, capsys)
    assert code == 0
    assert "MD0231" in err
    assert "commit" not in layer and "source" not in layer


def test_build_warns_for_a_dirty_local_clone_and_records_its_commit(tmp_path, capsys):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(ROOT / "registry"), str(clone)], check=True)
    (clone / "NOTES.txt").write_text("not committed\n")
    code, err, [layer] = _build(tmp_path, clone, capsys)
    assert code == 0
    # A clone of a folder on this machine: the commit is known, the source is not fetchable.
    assert "MD0232" in err and "MD0231" in err
    assert len(layer["commit"]) == 40 and layer["dirty"] is True
    assert "source" not in layer, "a clone of a local path names no network source"
