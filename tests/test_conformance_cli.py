"""Conformance at the command line: what `mendel build` refuses, and what it records."""

import pathlib
import subprocess
import sys

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_a_conformant_build_succeeds(tmp_path):
    assert (
        main(
            [
                "build",
                "--goal",
                str(ROOT / "examples/rnaseq-goal.yml"),
                "--out",
                str(tmp_path / "p"),
                "--root",
                str(ROOT),
            ]
        )
        == 0
    )


def test_a_nonconformant_contract_refuses_to_build(tmp_path, capsys):
    """The whole point: `mendel build` succeeding must mean something."""
    import shutil

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    star = next(layer.rglob("star-align.yml"))
    star.write_text(star.read_text().replace("nf_process: STAR_ALIGN", "nf_process: STAR_ALIGNN"))

    code = main(
        [
            "build",
            "--goal",
            str(ROOT / "examples/rnaseq-goal.yml"),
            "--out",
            str(tmp_path / "p"),
            "--root",
            str(ROOT),
            "--registry",
            str(layer),
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "M0101" in err
    assert "nf_process: STAR_ALIGN" in err, "the diagnostic must say what to write"
    assert not (tmp_path / "p" / "main.nf").exists(), "a refused build emits nothing"


def _build_with_no_module_source(tmp_path) -> int:
    """The real registry, and a --root holding no `vendor/`.

    `--root` is where module *source* lives; `--registry` is where contracts live. They
    are separate flags because they are separate things, and a lab wrapping bare
    containers has the second without the first.
    """
    return main(
        [
            "build",
            "--goal",
            str(ROOT / "examples/rnaseq-goal.yml"),
            "--out",
            str(tmp_path / "p"),
            "--registry",
            str(ROOT / "registry"),
            "--root",
            str(tmp_path),
        ]
    )


def test_an_unverified_contract_warns_and_builds(tmp_path, capsys):
    """A lab wrapping a bare container is legitimate. It is recorded, not refused."""
    assert _build_with_no_module_source(tmp_path) == 0
    assert "unverified" in capsys.readouterr().err


def test_unverified_contracts_reach_the_ir(tmp_path):
    import json

    _build_with_no_module_source(tmp_path)
    ir = json.loads((tmp_path / "p" / "pipeline.ir.json").read_text())
    assert ir["unverified"], "a publish bundle must carry which contracts were unchecked"


def test_a_conformant_build_records_nothing_as_unverified(tmp_path):
    """The field is evidence, so it must be empty when there was evidence."""
    import json

    main(
        [
            "build",
            "--goal",
            str(ROOT / "examples/rnaseq-goal.yml"),
            "--out",
            str(tmp_path / "p"),
            "--root",
            str(ROOT),
        ]
    )
    ir = json.loads((tmp_path / "p" / "pipeline.ir.json").read_text())
    assert ir["unverified"] == []


def test_mendel_explain_prints_the_long_form():
    result = subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "explain", "M0104"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert result.returncode == 0
    assert "path(" in result.stdout
    assert "because" in result.stdout


def test_mendel_explain_on_an_unknown_code_lists_the_known_ones():
    result = subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "explain", "M9999"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert "M0104" in result.stdout
