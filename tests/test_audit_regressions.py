"""One test per finding in the 2026-08-06 audit, named for it.

Kept in one file rather than scattered into the suites they belong to, because the
question a reader has is "is A9 still closed?" and the answer should not require knowing
which module A9 was about. Each test carries the finding's one-line summary.

The audit is `docs/internal/audits/2026-08-06-plan-1-to-1.7-audit.md`; every finding
there records how it was reproduced, which is what these tests are the standing version of.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

CONTRACT = {
    "id": "audit/x@1.0.0",
    "nf_process": "X",
    "nf_include": "./modules/x/main",
    "provenance": {
        "source": "audit",
        "drafted_by": "audit",
        "approved_by": "audit",
        "approved_at": "2026-08-06",
    },
}


def test_a13_a_profile_rejects_a_duplicate_measurement():
    """A13 — `get` was first-wins, so list order changed the pipeline."""
    from comeni_core.profile import DataProfile

    with pytest.raises(ValidationError, match="strandedness"):
        DataProfile.model_validate(
            {
                "measurements": [
                    {"measurement": "strandedness", "value": "reverse"},
                    {"measurement": "strandedness", "value": "unstranded"},
                ]
            }
        )


def test_a13_a_profile_sorts_so_the_same_facts_are_the_same_profile():
    """Order must not survive validation, or two equal profiles compare unequal."""
    from comeni_core.profile import DataProfile

    forward = DataProfile.model_validate(
        {"measurements": [{"measurement": "a", "value": 1}, {"measurement": "b", "value": 2}]}
    )
    backward = DataProfile.model_validate(
        {"measurements": [{"measurement": "b", "value": 2}, {"measurement": "a", "value": 1}]}
    )
    assert forward.model_dump_json() == backward.model_dump_json()


def test_a11_a_contract_rejects_a_duplicate_param_name():
    """A11 — two bindings of one name reached `sorted` and compared two ResolvedValues."""
    from comeni_core.contract import ModuleContract

    with pytest.raises(ValidationError, match="threads"):
        ModuleContract.model_validate(
            {
                **CONTRACT,
                "params": [{"name": "threads", "default": 4}, {"name": "threads", "default": 8}],
            }
        )


def test_a10_an_unknown_contract_key_is_refused():
    """A10 — dropped keys meant two different files pinned to one digest."""
    from comeni_core.contract import ModuleContract

    with pytest.raises(ValidationError, match="clinical_use"):
        ModuleContract.model_validate({**CONTRACT, "clinical_use": "approved"})
    with pytest.raises(ValidationError, match="ext_arg"):
        ModuleContract.model_validate({**CONTRACT, "ext_arg": "--misspelled"})


def test_a10_every_model_a_contract_is_built_from_forbids_extras():
    """The nested models too: a smuggled key on a Param is as invisible as one on the top."""
    from comeni_core import contract as contract_module

    for name in ("ModuleContract", "InputPort", "OutputPort", "Param", "NfInput", "Provenance"):
        model = getattr(contract_module, name)
        assert model.model_config.get("extra") == "forbid", (
            f"{name} ignores unknown keys, so `digest_of` pins what survived parsing "
            "rather than the file it came from (audit A10)"
        )


def test_a10_two_contract_files_cannot_share_a_digest():
    """The property the lockfile actually sells: 'built against exactly this contract'."""
    from comeni_core.contract import ModuleContract
    from comeni_core.digest import digest_of

    plain = ModuleContract.model_validate(CONTRACT)
    with pytest.raises(ValidationError):
        ModuleContract.model_validate({**CONTRACT, "validated_by": "Dr Nobody, 2019"})
    assert digest_of(plain).startswith("sha256:")


def test_a12_a_layer_is_named_by_its_manifest():
    """A12 — the basename is not an identity.

    `registry.yml` was added in Plan 1.7 for exactly this reason: "a layer that moves to
    its own repository cannot rely on the directory it happened to be checked out into."
    Nothing read it.
    """
    from comeni_core.layer import layer_name

    assert layer_name(Path("registry")) == "comeni-registry-examples"


def test_a12_a_layer_without_a_manifest_falls_back_to_its_basename(tmp_path):
    """An overlay a lab made by hand is ordinary, not broken."""
    from comeni_core.layer import layer_name

    (tmp_path / "lab-overlay" / "contracts").mkdir(parents=True)
    assert layer_name(tmp_path / "lab-overlay") == "lab-overlay"


def test_a12_a_renamed_checkout_is_not_drift(tmp_path):
    """The property: a `mv` must not read as a changed registry.

    A recipient who clones the public layer as `comeni-registry` rather than `registry`
    could not get a clean reproduction report, and a drift detector that cries wolf on a
    rename is one people learn to ignore.
    """
    import shutil

    from comeni_core.ir import PipelineIR
    from comeni_core.lockfile import Lockfile
    from comeni_core.registry import Registry

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

    from comeni_core.layer import layer_name

    shutil.copytree("registry", tmp_path / "here")
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path / "here")
        assert layer_name(Path(".")) == "comeni-registry-examples"
    finally:
        os.chdir(cwd)


def test_a2_resolve_refuses_an_unvalidated_profile():
    """A2 — invariant 15 lived in one CLI branch, and `upgrade` did not pass through it.

    `Goal.model_validate` builds a `DataProfile` without a registry, so it cannot check
    what is declared. `MeasurementRegistry.profile()` is the only validating constructor,
    and `resolve()` never routed through it — the check lived in `mendel build`'s own
    re-route, which `mendel upgrade` skips because it takes its goal from a bundle.
    """
    from comeni_core.goal import Goal
    from comeni_core.measurement import UnknownMeasurementError
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")
    goal = Goal.model_validate(
        {
            "have": [{"type_id": "fastq.reads"}],
            "want": ["counts.matrix"],
            "profile": {"measurements": [{"measurement": "sample_name", "value": "PT-4471023"}]},
        }
    )
    # `UnknownMeasurementError` is a KeyError, not a ValueError — the same distinction
    # `mendel build` already catches on, so the CLI's error handling needs no change.
    with pytest.raises(UnknownMeasurementError, match="sample_name"):
        resolve(goal, loaded.registry, loaded.rules, loaded.measurements)


def test_a2_upgrade_refuses_a_bundle_carrying_an_undeclared_measurement(tmp_path):
    """The reachable route, end to end: a bundle is a *downloaded* artifact.

    `mendel upgrade` reads its goal from the bundle rather than from a file, so it was the
    one verb reading something a stranger wrote and the one verb with no check. Reproduced
    in the audit as exit 0 with `sample_name: PATIENT-00417` in the emitted IR, and
    re-published verbatim by any following `mendel publish`.
    """
    import json

    from mendel_compiler.cli import main

    root = Path(__file__).parent.parent
    published = tmp_path / "published"
    assert main(
        ["publish", "--goal", str(root / "examples" / "rnaseq-goal.yml"),
         "--out", str(published), "--root", str(root)]
    ) == 0

    bundle_path = published / "pipeline.bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["goal"]["profile"]["measurements"].append(
        {"measurement": "sample_name", "value": "PATIENT-00417", "source": "goal", "by": None}
    )
    tainted = tmp_path / "tainted.bundle.json"
    tainted.write_text(json.dumps(bundle))

    out = tmp_path / "upgraded"
    assert main(["upgrade", "--bundle", str(tainted), "--out", str(out), "--root", str(root)]) != 0
    assert not (out / "pipeline.ir.json").exists(), "a refused upgrade must emit nothing"


def test_a2_a_declared_profile_still_resolves():
    """The refusal must not cost the normal case."""
    import yaml
    from comeni_core.goal import Goal
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")
    goal = Goal.model_validate(yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text()))
    ir = resolve(goal, loaded.registry, loaded.rules, loaded.measurements)
    assert ir.nodes


def test_a9_a_symlinked_contract_is_refused_by_the_digest(tmp_path):
    """A9 — the registry read through it; the digest hashed its target path."""
    from comeni_core.digest import digest_of_directory

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.yml").write_text("id: alpha\n")
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
    victim = next((layer / "contracts").rglob("*.yml"))
    (tmp_path / "elsewhere.yml").write_text(victim.read_text())
    victim.unlink()
    victim.symlink_to(tmp_path / "elsewhere.yml")

    with pytest.raises(ValueError, match="symlink"):
        layers_mod.load(layer)


def test_a9_an_ordinary_layer_still_digests(tmp_path):
    """The refusal must not cost the normal case."""
    import shutil

    from comeni_core.digest import digest_of_directory

    layer = tmp_path / "plain"
    shutil.copytree("registry", layer)
    assert digest_of_directory(layer) == digest_of_directory(Path("registry"))


def test_a11_the_emitter_never_compares_two_resolved_values():
    """Belt and braces: the sort key is the name, so a tie cannot reach the value.

    Task 1 makes a tie unreachable by rejecting it at the contract. This asserts the
    emitter would survive one anyway, because the next unorderable field on
    `ResolvedValue` must not resurrect a crash that is already fixed.
    """
    from comeni_core.ir import IRNode, PipelineIR, ResolvedValue, Tier
    from mendel_compiler.emit import emit
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract = next(c for c in loaded.registry.all() if c.params)
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="r"),
    )
    name = contract.params[0].name
    node.set_param(name, ResolvedValue(value=1, tier=Tier.CONVENTION, reason="a"))
    node.set_param(name, ResolvedValue(value=2, tier=Tier.CONVENTION, reason="b"))

    # An IR is deserialised from a bundle, so a duplicate binding stays *representable*
    # even once a contract cannot declare one. It must not reach an unorderable compare.
    emit(PipelineIR(nodes=[node]), loaded.registry, loaded.vocabulary, loaded.measurements)


def _stacked(tmp_path):
    """A base registry with a param rule, and a lab overlay that displaces two things.

    The base keeps its own `registry.yml`, so it is named `comeni-registry-examples`
    wherever it is copied to — A12's fix. The overlay has no manifest and falls back to
    its basename, which is what a lab building one by hand actually gets.
    """
    import shutil

    base = tmp_path / "base"
    shutil.copytree("registry", base)
    # The shipped registry has no param decision left to displace — the strandedness
    # block was deleted in Plan 1.5 — so the base gets one, and the overlay replaces it.
    (base / "rules" / "platform.yml").write_text(
        "version: 1\n"
        "decisions:\n"
        "  - decides: {param: seq_platform}\n"
        "    because: 'the base registry sequences on Illumina'\n"
        "    rows:\n"
        "      - {when: {read_length: '>= 70'}, then: ILLUMINA}\n"
    )

    lab = tmp_path / "lab-registry"
    (lab / "contracts").mkdir(parents=True)
    (lab / "rules").mkdir(parents=True)
    # A *different module key*, so this is not a shadow and no ShadowRecord is written.
    # Priority 99 beats nf-core/samtools/sort@1.21.0 at 0 outright, so it is not a tie
    # either and invariant 8 never fires. That is the whole of A5.
    (lab / "contracts" / "rival-sorter.yml").write_text(
        "id: lab/rival/sorter@9.9.9\n"
        "nf_process: RIVAL_SORT\n"
        "nf_include: modules/lab/rival/main\n"
        "consumes: [{name: bam, type_id: alignment.bam, state_required: []}]\n"
        "produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]\n"
        "params: []\n"
        "priority: 99\n"
        "nf_inputs: [{ports: [bam]}]\n"
        "container: example.invalid/rival:1\n"
        "provenance: {source: lab, drafted_by: lab, approved_by: lab, approved_at: '2026-08-06'}\n"
    )
    (lab / "rules" / "platform.yml").write_text(
        "version: 1\n"
        "decisions:\n"
        "  - decides: {param: seq_platform}\n"
        "    because: 'this lab runs BGI'\n"
        "    rows:\n"
        "      - {when: {read_length: '>= 70'}, then: BGI}\n"
    )
    return base, lab


def _resolve_stacked(tmp_path):
    import yaml
    from comeni_core.goal import Goal
    from comeni_core.layer import layer_name
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    base, lab = _stacked(tmp_path)
    loaded = layers_mod.load([base, lab])
    goal = Goal.model_validate(yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text()))
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        layer_names=[layer_name(p) for p in loaded.paths],
    )


def test_a5_an_overlay_contract_that_displaces_one_says_so(tmp_path):
    """A5 — a priority win is not a shadow and not a tie, so nothing reported it."""
    ir = _resolve_stacked(tmp_path)

    node = next(n for n in ir.nodes if n.contract_id == "lab/rival/sorter@9.9.9")
    assert node.selection.from_layer == "lab-registry"
    assert node.selection.displaced_layer == "comeni-registry-examples"


def test_a15_an_overlay_rule_that_displaces_one_says_so(tmp_path):
    """A15 — `by_target[key] = decision` overwrote a whole block and recorded nothing."""
    ir = _resolve_stacked(tmp_path)

    values = [b.value for n in ir.nodes for b in n.params if b.name == "seq_platform"]
    assert values, "the aligner declares seq_platform; the rule should have decided it"
    assert all(v.value == "BGI" for v in values)
    assert all(v.from_layer == "lab-registry" for v in values)
    assert all(v.displaced_layer == "comeni-registry-examples" for v in values)


def test_a5_overlay_reroutes_names_both_and_needs_review_names_neither(tmp_path):
    """Two questions, two lists.

    The plan's first draft asserted `needs_review()` would name these. It lists REQUIRED
    only, under a test named for that guarantee, and an overlay win is tier 2 review
    `none` — correctly, because the selection genuinely was a documented default. What
    was missing was visibility, not severity. Pinned here so nobody restores the claim.
    """
    ir = _resolve_stacked(tmp_path)

    reroutes = ir.overlay_reroutes()
    assert any("lab/rival/sorter@9.9.9" in line for line in reroutes)
    assert any("seq_platform" in line for line in reroutes)
    assert not any("rival" in line or "seq_platform" in line for line in ir.needs_review())


def test_a5_a_single_layer_build_reports_nothing(tmp_path):
    """The refusal must not cost the normal case — a lab with no overlay sees no change."""
    import yaml
    from comeni_core.goal import Goal
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")
    goal = Goal.model_validate(yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text()))
    ir = resolve(goal, loaded.registry, loaded.rules, loaded.measurements)

    assert ir.overlay_reroutes() == []
    assert all(n.selection.displaced_layer is None for n in ir.nodes)


def test_a5_an_overlay_that_displaces_nothing_is_not_reported(tmp_path):
    """The discriminator between displacement and origin.

    An implementation that flagged "came from an overlay" passes every other test in this
    group. Here the base has no sorter at all, so the lab's is the sole producer — it wins
    without beating anything, which is a lab using the system as designed and not a
    reroute. Flagging it is the failure the design exists to avoid: an advisory beside
    every module an overlay supplies, with the one that mattered buried among them.
    """
    import shutil

    import yaml
    from comeni_core.goal import Goal
    from comeni_core.layer import layer_name
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    base, lab = _stacked(tmp_path)
    (base / "contracts" / "nf-core" / "samtools-sort.yml").unlink()
    shutil.rmtree(lab / "rules")

    loaded = layers_mod.load([base, lab])
    goal = Goal.model_validate(yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text()))
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        layer_names=[layer_name(p) for p in loaded.paths],
    )

    node = next(n for n in ir.nodes if n.contract_id == "lab/rival/sorter@9.9.9")
    # Provenance is still recorded — a curator asks "where did this come from" of every
    # node. Only the *flag* is selective.
    assert node.selection.from_layer == "lab-registry"
    assert node.selection.displaced_layer is None
    assert ir.overlay_reroutes() == []


def test_a6_the_egress_guard_knows_mapping_and_bytes():
    """A6 — `Mapping` is a superclass of `dict`, so `issubclass(origin, dict)` missed it.

    The standing version of the reproduction. With those two shapes on the real
    `PublishBundle` the guard reported 7 passed: `Mapping[MeasurementId, ParamValue]` is
    an ordinary dict at runtime with arbitrary keys — the `{"patient_id": ...}` case the
    mapping rule's own docstring forbids — and `bytes` is not `str`, not a mapping, not
    `Any` and carries no marker, so nothing in the file could see it.

    Asserted against the helpers rather than by adding fields to a shipped payload,
    because a break-test that lives in the tree is a break-test somebody eventually
    commits.
    """
    from collections.abc import Mapping, MutableMapping
    from typing import Annotated

    from comeni_core.marks import MeasurementId, ParamValue
    from test_egress import _mentions_binary, _mentions_mapping

    assert _mentions_mapping(Mapping[MeasurementId, ParamValue])
    assert _mentions_mapping(MutableMapping[str, str])
    assert _mentions_mapping(dict[str, str]), "the original case must not regress"
    assert not _mentions_mapping(list[str])

    assert _mentions_binary(bytes)
    assert _mentions_binary(bytes | None)
    assert _mentions_binary(Annotated[bytes, "signature"]), "a label on a blob is a blob"
    assert _mentions_binary(bytearray)
    assert _mentions_binary(memoryview)
    assert not _mentions_binary(str)
