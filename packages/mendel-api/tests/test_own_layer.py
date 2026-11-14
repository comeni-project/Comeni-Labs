"""The installation's own registry layer, stacked above the release (#462).

Where an approved learned rule lives. Absent until something is written to it, so an
installation with none reads the release alone, exactly as before."""

import pytest
import yaml
from mendel_api.services import blueprint, registry
from mendel_api.settings import registry_roots, settings
from mendel_compiler import pipeline_file
from support.paths import REGISTRY

STAR, HISAT2 = "nf-core/star/align@2.7.11b", "nf-core/hisat2/align@2.2.2"


@pytest.fixture
def own(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "own_layer", tmp_path / "layer")
    return tmp_path / "layer"


def _learn(layer, rows):
    registry.ensure_own_layer()
    path = layer / "rules/learned/implementation-alignment.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"declares": "rule", "version": 1, "decisions": [
        {"decides": {"effect": "implementation", "of": "alignment"},
         "because": "learned from people's answers", "rows": rows}]}))
    return path


def _goal_without_read_length(tmp_path):
    starter = yaml.safe_load(settings.example_goal.read_text())
    starter["facts"]["measurements"] = [m for m in starter["facts"]["measurements"]
                                        if m["measurement"] != "read_length"]
    path = tmp_path / "goal.yml"
    path.write_text(yaml.safe_dump(starter))
    return pipeline_file.goal_from(path)


def test_no_own_layer_reads_the_release_alone(own):
    assert [p.resolve() for p in registry_roots()] == [REGISTRY.resolve()]
    assert not own.exists()
    assert len(registry.stack().paths) == 1


def test_an_own_layer_stacks_above_the_release(own, tmp_path):
    shipped = yaml.safe_load((REGISTRY / "rules/alignment.yml").read_text())
    shipped = shipped["decisions"][0]["rows"]
    _learn(own, [*shipped, {"when": {"paired": True, "read_length": "absent"},
                            "then": HISAT2, "because": "people chose it",
                            "cite": "kept pipelines a, b, c"}])
    assert (own / "registry.yml").is_file()
    assert [p.resolve() for p in registry_roots()] == [REGISTRY.resolve(), own.resolve()]
    stack = registry.stack()
    assert len(stack.paths) == 2
    assert any(d.key == "implementation:alignment" for d in stack.displaced), stack.displaced

    built, _ = blueprint.resolve(_goal_without_read_length(tmp_path))
    align = next(step for step in built.pipeline.steps if step.id.endswith("align"))
    assert align.module.contract_id == HISAT2
    assert built.registry == registry.digest()
    names = [layer.name for layer in built.pipeline.registry.layers]
    assert names[-1] == "installation" and len(names) == 2


def test_withdrawing_moves_the_digest(own):
    before = registry.digest()
    path = _learn(own, [{"when": {"paired": True}, "then": HISAT2}])
    learned = registry.digest()
    assert learned != before
    path.unlink()
    assert registry.digest() != learned, "a withdrawn rule must not be served from a cache"
