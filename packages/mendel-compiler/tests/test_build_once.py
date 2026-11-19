"""The build path's smaller repeats (#549)."""

from mendel_compiler.cli import main
from mendel_resolver import layers
from support.paths import ROOT


def test_the_cli_build_loads_the_registry_once(tmp_path, monkeypatch):
    """`mendel build` loaded the registry three times and checked conformance twice: once to
    print the diagnostics, once in the build, once for the profile. It loads once."""
    loads, real = [0], layers.load

    def counted(roots):
        loads[0] += 1
        return real(roots)

    monkeypatch.setattr(layers, "load", counted)
    assert main(["build", str(ROOT / "examples" / "rnaseq.yml"), "--out", str(tmp_path / "out"),
                 "--root", str(ROOT)]) == 0
    assert (tmp_path / "out" / "pipeline.yml").is_file()
    assert loads[0] == 1


def test_the_routing_registry_is_worked_out_once_per_load():
    """`Layers.routing` built a new `Registry` on every access, inside per-step loops."""
    loaded = layers.load([ROOT / "registry"])
    assert loaded.routing is loaded.routing
    assert list(loaded.routing.all()), "an empty routing registry would prove nothing"


def test_a_prepared_build_asks_git_only_what_can_change(monkeypatch):
    """#590. Each build ran five git commands per layer. Where a layer sits in its checkout is
    a fact about the path, worked out once in `prepare`; its remote, commit and uncommitted
    edits can change with no file changing, so each build still asks for those three."""
    from mendel_compiler import locate, orchestrate
    from mendel_resolver.goal import Goal

    prepared = orchestrate.prepare([ROOT / "registry"])
    asked, real = [], locate._git

    def counted(layer, *args):
        asked.append(args[:2])
        return real(layer, *args)

    monkeypatch.setattr(locate, "_git", counted)
    goal = Goal.model_validate({"have": [{"type_id": "fastq.reads"}], "want": ["qc.report"]})
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry"], prepared=prepared)
    assert built.pipeline.registry.layers[0].commit, "the commit is still read"
    assert ("rev-parse", "--show-toplevel") not in asked
    assert ("rev-parse", "--show-prefix") not in asked
    assert len(asked) == 3, asked
