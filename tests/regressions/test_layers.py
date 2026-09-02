"""A9, A12, A26 and A31 — what a layer is, and what loading one refuses.

One test per finding, named for it — the question a reader has is *is A9 still
closed?*, and the test name is the answer. The 2026-08-06 audit and the rounds after
it numbered every finding; `docs/notes/audits/` records how each was reproduced.
"""

from pathlib import Path

import pytest
from support.audit import _declared, _stacked


def test_a12_a_layer_is_named_by_its_manifest():
    """A12 — the basename is not an identity.

    `registry.yml` was added in Plan 1.7 for exactly this reason: "a layer that moves to
    its own repository cannot rely on the directory it happened to be checked out into."
    Nothing read it.
    """
    from comeni_core.declared.layer import layer_name

    assert layer_name(Path("registry")) == "comeni-registry-examples"


def test_a12_a_layer_without_a_manifest_falls_back_to_its_basename(tmp_path):
    """An overlay a lab made by hand is ordinary, not broken."""
    from comeni_core.declared.layer import layer_name

    (tmp_path / "lab-overlay" / "contracts").mkdir(parents=True)
    assert layer_name(tmp_path / "lab-overlay") == "lab-overlay"


def test_a12_a_renamed_checkout_is_not_drift(tmp_path):
    """The property: a `mv` must not read as a changed registry.

    A recipient who clones the public layer as `comeni-registry` rather than `registry`
    could not get a clean reproduction report, and a drift detector that cries wolf on a
    rename is one people learn to ignore.
    """
    import shutil

    from comeni_core.artifact.lockfile import Lockfile
    from comeni_core.declared.registry import Registry
    from comeni_core.plan.ir import PipelineIR

    original = tmp_path / "registry"
    shutil.copytree("registry", original)
    empty = Registry(contracts={})
    locked = Lockfile.of(PipelineIR(), empty, [original])

    renamed = tmp_path / "cloned-under-another-name"
    original.rename(renamed)
    assert locked.drift_against(PipelineIR(), empty, [renamed]) == []


def test_a12_a_layer_never_records_an_empty_name(tmp_path):
    """`--registry .` recorded name: '' into a bundle and every ShadowRecord in it."""
    import os
    import shutil

    from comeni_core.declared.layer import layer_name

    shutil.copytree("registry", tmp_path / "here")
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path / "here")
        assert layer_name(Path(".")) == "comeni-registry-examples"
    finally:
        os.chdir(cwd)


def test_a9_a_symlinked_contract_is_refused_by_the_digest(tmp_path):
    """A9 — the registry read through it; the digest hashed its target path."""
    from comeni_core.artifact.digest import digest_of_directory

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.yml").write_text(_declared(outside / "real.yml", "id: alpha\n"))
    contracts = tmp_path / "layer" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "c.yml").symlink_to(outside / "real.yml")

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(tmp_path / "layer")


def test_a9_a_symlinked_layer_is_refused_at_load(tmp_path):
    """The message must arrive at load, not at publish.

    A digest that raises is a publish-time error, and publication is the door with no
    undo — by then the reroute has already happened and been emitted.
    """
    import shutil

    from mendel_resolver import layers as layers_mod

    layer = tmp_path / "lab"
    shutil.copytree("registry", layer)
    victim = next((layer / "tools").rglob("contract.yml"))
    (tmp_path / "elsewhere.yml").write_text(
        _declared(
            tmp_path / "elsewhere.yml",
            victim.read_text()))
    victim.unlink()
    victim.symlink_to(tmp_path / "elsewhere.yml")

    with pytest.raises(ValueError, match="symlink"):
        layers_mod.load(layer)


def test_a9_an_ordinary_layer_still_digests(tmp_path):
    """The refusal must not cost the normal case."""
    import shutil

    from comeni_core.artifact.digest import digest_of_directory

    layer = tmp_path / "plain"
    shutil.copytree("registry", layer)
    assert digest_of_directory(layer) == digest_of_directory(Path("registry"))


def test_a26_a_yaml_contract_is_loaded_like_any_other(tmp_path):
    """A26 — every loader matched `*.yml` only, so an overlay named `.yaml` vanished.

    The build then routed on the base layer and exited 0. An overlay that does nothing
    must not look exactly like an overlay that worked — and the layer digest hashed the
    file either way, so the lockfile said the overlay was there.
    """
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "contracts" / "rival-sorter.yml").rename(lab / "contracts" / "rival-sorter.yaml")

    loaded = layers_mod.load([base, lab])

    assert "lab/rival/sorter@9.9.9" in loaded.registry.contracts


def test_a26_a_nested_vocabulary_is_loaded(tmp_path):
    """Three of the four loaders globbed one level. Contracts nested; nothing else did."""
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "vocabularies" / "lab-types").mkdir(parents=True)
    (lab / "vocabularies" / "lab-types" / "assay.panel.yml").write_text(
        _declared(lab / "vocabularies" / "lab-types" / "assay.panel.yml", "states: [validated]\n")
    )

    loaded = layers_mod.load([base, lab])

    assert loaded.vocabulary.states_for("assay.panel") == frozenset({"validated"})


def test_a26_a_file_nothing_reads_is_an_error(tmp_path):
    """The load-bearing half: silence is what made the `.yaml` case expensive.

    A misspelled directory is the realistic mistake — `contract/`, `rule/`, a file dropped
    at the layer root. Every one of them used to load cleanly and change nothing.
    """
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "contract").mkdir()
    (lab / "contract" / "misplaced.yml").write_text(
        _declared(
            lab / "contract" / "misplaced.yml",
            "id: lab/x@1.0.0\n"))

    with pytest.raises(ValueError, match="contract/misplaced.yml"):
        layers_mod.load([base, lab])


def test_a26_the_manifest_is_not_an_unread_file(tmp_path):
    """`registry.yml` is the one file at a layer root that is read by something else."""
    from mendel_resolver import layers as layers_mod

    assert layers_mod.load("registry").registry.all()


def test_a31_a_contract_cannot_be_read_two_ways(tmp_path):
    """A31 — `yaml.safe_load` takes the last value for a repeated key, silently.

    A contract with two `priority:` lines loaded at the second one. That is A10's argument
    one level down: the digest pins what survived parsing rather than what the file says, so
    a reviewer reading `priority: 0` at the top and a build routing on `priority: 999` from
    the bottom are both looking at a correctly signed layer.
    """
    from comeni_core.declared.vocabulary import Vocabulary
    from comeni_core.yaml_strict import DuplicateKeyError

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "alignment.bam.yml").write_text(
        _declared(tmp_path / "vocabularies" / "alignment.bam.yml", "states: []\n")
    )
    contract = tmp_path / "two-ways.yml"
    contract.write_text(
        _declared(contract, "id: lab/two-ways@1.0.0\n"
        "nf_process: TWO_WAYS\n"
        "nf_include: modules/lab/two/main\n"
        "priority: 0\n"
        "produces: [{name: bam, type_id: alignment.bam, state: []}]\n"
        "provenance: {source: lab, drafted_by: l, approved_by: l, approved_at: '2026-08-07'}\n"
        "priority: 999\n")
    )

    from comeni_core.declared.contract import ModuleContract

    with pytest.raises(DuplicateKeyError) as raised:
        ModuleContract.load(contract, Vocabulary.load(tmp_path))

    message = str(raised.value)
    assert "priority" in message
    assert "two-ways.yml" in message, "name the file"
    assert "line 4" in message and "line 7" in message, f"name both lines: {message}"


def test_a31_every_file_this_project_owns_reads_one_way():
    """Run it against the shipped registry, the examples, and every vendored `meta.yml`.

    A vendored file that trips this is a finding about that module, recorded rather than
    exempted — the point of a strict loader is not to be satisfiable.
    """
    from comeni_core import yaml_strict

    owned = [
        *Path("registry").rglob("*.yml"),
        *Path("examples").rglob("*.yml"),
        # Upstream's own `meta.yml` and `environment.yml`, which live in the layer since
        # Plan 5A. They carry no `declares:` line and are not layer data — but a strict loader
        # still has to be able to *read* them, and a duplicate key in one is a finding about
        # that module rather than something to exempt.
        *Path("registry").rglob("module/**/*.yml"),
        *Path("registry").rglob("module/**/*.yaml"),
    ]
    assert len(owned) > 20, "this test is only meaningful if it reads something"
    for path in owned:
        yaml_strict.load(path)
