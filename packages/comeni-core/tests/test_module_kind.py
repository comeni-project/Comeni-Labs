"""Behavioral checks for module declarations, source ownership, and layer replacement."""

import pathlib

import pytest
from comeni_core.declared.layered import DeclaredKind, bucket, declared_kind, layers_of, stack
from comeni_core.declared.module import Module

MODULE = """\
declares: module
id: nf-core/star/align
licence: MIT
upstream:
  repo: https://github.com/nf-core/modules.git
  sha: 6d46786420b4d7bc88eba026eb389c0c5535d120
  path: modules/nf-core/star/align
excluded: [tests]
"""


def _layer(root: pathlib.Path, body: str = MODULE, *, name: str = "base") -> pathlib.Path:
    """A layer holding one tool: its declaration, and upstream's directory beside it."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "registry.yml").write_text(f"name: {name}\n")
    tool = root / "tools" / "nf-core" / "star" / "align"
    (tool / "module").mkdir(parents=True)
    (tool / "module.yml").write_text(body)
    (tool / "module" / "main.nf").write_text("process STAR_ALIGN {}\n")
    # **Upstream's own meta.yml, with no `declares:` line.** This is the file that makes the
    # `module/` exclusion in `_files` load-bearing rather than tidy.
    (tool / "module" / "meta.yml").write_text("name: star_align\ntools:\n  - star: {}\n")
    return root


def test_a_module_yml_declares_its_kind(tmp_path):
    layer = _layer(tmp_path / "base")
    where = layer / "tools" / "nf-core" / "star" / "align" / "module.yml"
    assert declared_kind(where) is DeclaredKind.MODULES


def test_upstream_s_own_meta_yml_is_not_read_as_declared_data(tmp_path):
    """Upstream metadata inside ``module/`` is source content, not declared layer data."""
    layer = _layer(tmp_path / "base")
    found = bucket(layers_of([layer]))[0]
    read = {p.name for paths in found.values() for p in paths}
    assert "module.yml" in read
    assert "meta.yml" not in read, (
        "upstream's meta.yml was read as layer data — it has no `declares:` line, so the "
        "next thing that happens is MD0010 on every vendored module in the registry"
    )


def test_a_module_stacks_on_the_module_key(tmp_path):
    """The public loader replaces a lower-layer module with the same module key."""
    base = _layer(tmp_path / "base")
    over = _layer(
        tmp_path / "over", MODULE.replace("licence: MIT", "licence: GPL-3.0-only"), name="lab"
    )

    stacked = Module.load([base, over])
    assert stacked.entries["nf-core/star/align"].licence == "GPL-3.0-only"
    assert [d.key for d in stacked.displaced] == ["nf-core/star/align"]
    assert stacked.displaced[0].winning_layer == "lab"


def test_a_module_nobody_vendored_is_legal(tmp_path):
    """`upstream: None` means a laboratory's own process, written here rather than copied.

    The absence is the honest statement that there is nothing to check the directory
    against — a different thing from a check that has not been run.
    """
    body = "declares: module\nid: in-house/tidy\nlicence: Apache-2.0\n"
    layer = tmp_path / "base"
    layer.mkdir()
    (layer / "registry.yml").write_text("name: base\n")
    tool = layer / "tools" / "in-house" / "tidy"
    (tool / "module").mkdir(parents=True)
    (tool / "module.yml").write_text(body)
    (tool / "module" / "main.nf").write_text("process TIDY {}\n")

    stacked = stack(layers_of([layer]), Module.kind())
    assert stacked.entries["in-house/tidy"].upstream is None


def test_a_licence_expression_is_refused():
    """`LICENSES/<id>.txt` names one file, and `MIT OR Apache-2.0` names none.

    Refusing it here rather than silently pointing at a file that does not exist is the
    same trade `_digest` makes: a field whose shape is fully determined gets a validator.
    """
    with pytest.raises(ValueError, match="expression"):
        Module(id="nf-core/star/align", licence="MIT OR Apache-2.0")


def test_the_layer_that_wins_the_contract_wins_the_module(tmp_path):
    """A winning declaration and its adjacent source remain owned by the same layer."""
    base = _layer(tmp_path / "base")
    over = _layer(
        tmp_path / "over",
        MODULE.replace("sha: 6d46786420b4d7bc88eba026eb389c0c5535d120", "sha: " + "a" * 40),
        name="lab",
    )
    (over / "tools" / "nf-core" / "star" / "align" / "module" / "main.nf").write_text(
        "process STAR_ALIGN { /* the lab's patched copy */ }\n"
    )

    stacked = stack(layers_of([base, over]), Module.kind())
    won = stacked.entries["nf-core/star/align"]

    assert won.upstream is not None and won.upstream.sha == "a" * 40
    assert won.source is not None
    assert "patched" in (won.source / "main.nf").read_text(), (
        "the overlay won the declaration and lost the source — a lab's contract would run "
        "against the public layer's module, which is MD0104's drift between layers"
    )
    assert [(d.kind, d.key, d.winning_layer) for d in stacked.displaced] == [
        (DeclaredKind.MODULES, "nf-core/star/align", "lab")
    ]
