"""Conformance at the command line: what `mendel build` refuses, and what it records."""

import pathlib
import shutil
import subprocess
import sys

from comeni_core.declared.module import Module
from mendel_compiler.cli import main

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

ROOT = pathlib.Path(__file__).parent.parent
MODULES = dict(Module.load(ROOT / "registry").entries)



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
    star = next(layer.rglob("align/contract.yml"))
    star.write_text(
        _declared(
            star,
            star.read_text().replace("nf_process: STAR_ALIGN", "nf_process: STAR_ALIGNN")))

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
    assert "MD0101" in err
    assert "nf_process: STAR_ALIGN" in err, "the diagnostic must say what to write"
    assert not (tmp_path / "p" / "main.nf").exists(), "a refused build emits nothing"


def _build_with_no_module_source(tmp_path) -> int:
    """A layer holding every declaration and **no `module/`** — a lab wrapping bare containers.

    This used to pass `--root` at an empty directory, because module source lived under
    `<root>/vendor` while the contracts came from `--registry`: two flags, because they were
    two things. Since Plan 5A they are one thing — the layer carries both — so the way to
    produce an unverified contract is to build a layer with the declarations and without the
    code, which is exactly the case the diagnostic is *for* and is closer to what a laboratory
    actually has.
    """
    layer = tmp_path / "bare"
    shutil.copytree(ROOT / "registry", layer, ignore=shutil.ignore_patterns("module*"))
    return main(
        [
            "build",
            "--goal",
            str(ROOT / "examples/rnaseq-goal.yml"),
            "--out",
            str(tmp_path / "p"),
            "--registry",
            str(layer),
        ]
    )


def test_an_unverified_contract_warns_and_builds(tmp_path, capsys):
    """A lab wrapping a bare container is legitimate. It is recorded, not refused."""
    assert _build_with_no_module_source(tmp_path) == 0
    assert "unverified" in capsys.readouterr().err


def test_unverified_contracts_reach_the_artifact(tmp_path):
    """Which contracts were never checked against module source, in the file a reader reads.

    Under `registry:` since Plan 1.10, beside the layers it belongs with, rather than at the
    top level of an IR that no longer reaches disk.
    """
    import yaml

    _build_with_no_module_source(tmp_path)
    pipeline = yaml.safe_load((tmp_path / "p" / "pipeline.yml").read_text())
    assert pipeline["registry"]["unverified"], "a shared pipeline must say what was unchecked"


def test_a_conformant_build_records_nothing_as_unverified(tmp_path):
    """The field is evidence, so it must be empty when there was evidence."""
    import yaml

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
    pipeline = yaml.safe_load((tmp_path / "p" / "pipeline.yml").read_text())
    assert pipeline["registry"]["unverified"] == []


def test_mendel_explain_prints_the_long_form():
    result = subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "explain", "MD0104"],
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
    assert "MD0104" in result.stdout


def _layer_with(tmp_path, edit):
    """A copy of the shipped registry with one contract edited."""
    import shutil

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    edit(layer)
    return layer


def test_md0108_a_prefix_route_on_a_module_that_ignores_it_is_refused(tmp_path):
    """`via:` made a route *declared*. It did not make it *true*.

    `star/genomegenerate` is one of three vendored modules whose script never mentions
    `task.ext.prefix`, so this has a real negative to find — a check that can only pass is
    not a check. `modulespec.py` already parses both keys as a substring of the source, which
    is why the check lands on day one rather than waiting for a Groovy parser.
    """
    from mendel_compiler.conformance import check
    from mendel_resolver import layers

    def add_a_dead_route(layer):
        path = next(layer.rglob("genomegenerate/contract.yml"))
        path.write_text(
            _declared(path, path.read_text().replace(
                "params: []",
                'params:\n  - name: label\n    via: ext\n    key: prefix\n',
            ))
        )

    registry = layers.load(_layer_with(tmp_path, add_a_dead_route)).registry
    found = check(registry, MODULES)
    dead = [d for d in found if d.code == "MD0108"]
    assert dead, [d.code for d in found]
    assert "label" in dead[0].where
    assert "ext.prefix" in dead[0].summary


def test_md0108_is_silent_on_a_module_that_does_read_the_key(tmp_path):
    """The regression guard: it must depend on the module's source, not on a route existing.

    `samtools/sort` reads `task.ext.prefix`, so the identical route there is honest.
    """
    from mendel_compiler.conformance import check
    from mendel_resolver import layers

    def add_a_live_route(layer):
        path = next(layer.rglob("sort/contract.yml"))
        path.write_text(
            _declared(path, path.read_text().replace(
                "params: []",
                'params:\n  - name: label\n    via: ext\n    key: prefix\n',
            ))
        )

    registry = layers.load(_layer_with(tmp_path, add_a_live_route)).registry
    assert not [d for d in check(registry, MODULES) if d.code == "MD0108"]


def test_the_shipped_registry_routes_nothing_to_a_key_its_module_ignores():
    """All ten vendored modules read `task.ext.args`, so every shipped route is live.

    Asserted rather than assumed: this is the property that makes `mendel build` green, and
    a contract added later that quietly breaks it should fail here with a name attached.
    """
    from mendel_compiler.conformance import check
    from mendel_resolver import layers

    registry = layers.load(ROOT / "registry").registry
    assert not [d for d in check(registry, MODULES) if d.code == "MD0108"]
