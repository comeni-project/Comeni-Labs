"""A build parses each module's source once (#546)."""

from collections import Counter

from comeni_core.declared.layered import declared_entries
from mendel_compiler import conformance, orchestrate
from mendel_compiler.modulespec import ModuleSpec
from support.paths import ROOT

REGISTRY = ROOT / "registry"


def test_preparing_a_build_parses_each_module_once(monkeypatch):
    """`conformance.check`, its `_meta_keys` and `facts_read` each parsed every module: 3
    parses of every module per build. `prepare` parses them once and hands the same specs to
    all three."""
    parsed, real = Counter(), ModuleSpec.parse

    def counted(path, *args, **kwargs):
        parsed[path] += 1
        return real(path, *args, **kwargs)

    monkeypatch.setattr(ModuleSpec, "parse", staticmethod(counted))
    prepared = orchestrate.prepare([REGISTRY])
    assert parsed, "no module parsed: this would check nothing"
    assert set(parsed.values()) == {1}, parsed.most_common(3)
    assert prepared.facts_read, "facts_read read nothing"
    specs = conformance.specs_of(prepared.layers.registry, prepared.layers.modules)
    assert len({id(s) for s in specs.values()}) <= len(parsed)


def test_the_layer_walk_lists_what_it_listed(tmp_path):
    """`declared_entries` works out each path once now; what it lists is unchanged: declared
    YAML, owned module and piece source, symlinks; not bytecode or dot-files outside source."""
    (tmp_path / "registry.yml").write_text("name: t\n")
    (tmp_path / "a.yml").write_text("declares: rule\n")
    (tmp_path / ".hidden.yml").write_text("x: 1\n")
    (tmp_path / "tools" / "x" / "module" / ".conda-lock").mkdir(parents=True)
    (tmp_path / "tools" / "x" / "module" / ".conda-lock" / "lock.txt").write_text("pin\n")
    (tmp_path / "m" / "piece").mkdir(parents=True)
    (tmp_path / "m" / "measurer.yml").write_text("declares: measurer\n")
    (tmp_path / "m" / "piece" / "run.py").write_text("print(1)\n")
    (tmp_path / "m" / "piece" / "__pycache__").mkdir()
    (tmp_path / "m" / "piece" / "__pycache__" / "run.cpython-313.pyc").write_bytes(b"\0")
    (tmp_path / "n" / "piece").mkdir(parents=True)
    (tmp_path / "n" / "piece" / "loose.py").write_text("print(2)\n")
    (tmp_path / "link.yml").symlink_to(tmp_path / "a.yml")
    listed = sorted(str(p.relative_to(tmp_path)) for p in declared_entries(tmp_path))
    assert listed == ["a.yml", "link.yml", "m/measurer.yml", "m/piece/run.py", "registry.yml",
                      "tools/x/module/.conda-lock/lock.txt"]
