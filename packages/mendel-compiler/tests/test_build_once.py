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
