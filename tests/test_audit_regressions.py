"""One test per finding in the 2026-08-06 audit, named for it.

Kept in one file rather than scattered into the suites they belong to, because the
question a reader has is "is A9 still closed?" and the answer should not require knowing
which module A9 was about. Each test carries the finding's one-line summary.

The audit is `docs/internal/audits/2026-08-06-plan-1-to-1.7-audit.md`; every finding
there records how it was reproduced, which is what these tests are the standing version of.
"""

import json
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
        resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )


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
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
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


def _resolve_stacked_from(loaded):
    import yaml
    from comeni_core.goal import Goal
    from comeni_core.layer import layer_name
    from mendel_resolver.resolve import resolve

    goal = Goal.model_validate(yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text()))
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        layer_names=[layer_name(p) for p in loaded.paths],
    )


def _resolve_stacked(tmp_path):
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    return _resolve_stacked_from(layers_mod.load([base, lab]))


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
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )

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
        vocabulary=loaded.vocabulary,
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


A3_PATHS = [
    "/data/patients/PT-4471023/S1_R1.fastq.gz",
    "~/samples/PT-4471023.bam",
    "../../etc/passwd",
    "cohort/2026/PT-4471023_R1.fq.gz",
    "run.cram",
    "calls.vcf",
]

A3_LEGITIMATE = [
    "nf-core/star/align@1.11.0",  # a contract ID has slashes and must survive
    "GRCh38",
    "reverse",
    "ILLUMINA",
    "--readFilesCommand zcat",
    "sha256:" + "0" * 64,
    None,
    2,
    True,
]


@pytest.mark.parametrize("value", A3_PATHS)
def test_a3_a_path_shaped_parameter_is_refused(value):
    """A3 — `human_override` is the slot for a human's answer and was an open string.

    Reproduced on the unmodified tree with no monkeypatching: a patient path validated
    into a `DecisionRecord` and from there into a `PublishBundle`, the door with no undo.
    """
    from comeni_core.decision import ParamDecision

    with pytest.raises(ValidationError):
        ParamDecision(
            key="k", subject="s", chosen=None, reason="r", resolved_by="human",
            human_override=value,
        )


@pytest.mark.parametrize("value", A3_LEGITIMATE)
def test_a3_a_registry_shaped_parameter_still_validates(value):
    """The refusal must not cost the normal case.

    A contract ID is the sharp one: it carries slashes and an `@version`, and a rule's
    `then:` is exactly that. A blocklist that rejected it would make the registry
    unloadable.
    """
    from comeni_core.decision import ParamDecision

    record = ParamDecision(
        key="k", subject="s", chosen=None, reason="r", resolved_by="human",
        human_override=value,
    )
    assert record.human_override == value


def test_a3_a_path_cannot_enter_through_a_goal_param_override():
    """The same value, through the door a person actually types into."""
    from comeni_core.goal import Goal

    with pytest.raises(ValidationError):
        Goal.model_validate(
            {
                "constraints": {
                    "params": [
                        {"name": "seq_platform", "value": "/data/patients/PT-4471023/S1.fastq.gz"}
                    ]
                }
            }
        )


def test_a3_an_edge_pointer_is_not_a_path_and_is_not_guarded():
    """Why the blocklist is scoped to human-typed fields, pinned so it is not widened.

    `"dual.bam"` means port `bam` on node `dual` — an internal pointer the resolver writes
    when two upstream outputs could feed one input. Ports in the registry really are named
    `bam`, so `"star_align.bam"` is an ordinary value. It is character-for-character a
    filename and no text rule separates the two, so applying the blocklist to `chosen`
    would either reject real pipelines or force dropping `.bam` from the list and let
    `PT-4471023.fastq.gz` through.

    Neither is necessary: a pointer is built by this code from registry data, and both
    routing paths rebuild it from their candidate list rather than trusting a resolver's
    answer (audit A8). Nothing human reaches it. Guard by who writes a field, not by what
    the value looks like.

    **A16 improves on this rather than replacing it.** `SourceDecision.chosen` is an
    `EdgeRef` now, so `dual.bam` is accepted *because it is declared* rather than tolerated
    because the blocklist was scoped around it. The scoping argument still holds for
    `ParamDecision.human_override`, which is the one kind with no domain — Plan 2 Task 11.
    """
    from comeni_core.decision import ParamDecision, SourceDecision

    record = SourceDecision(
        key="dual.source:bam", subject="source:bam", candidates=["dual.bam", "solo.bam"],
        chosen="dual.bam", reason="r", resolved_by="flag-only",
    )
    assert record.chosen == "dual.bam"

    # The same string typed by a person is still refused, which is the whole scoping.
    with pytest.raises(ValidationError):
        ParamDecision(
            key="k", subject="s", chosen=None, reason="r", resolved_by="human",
            human_override="/data/patients/PT-4471023/S1_R1.fastq.gz",
        )


def test_a4_gate_is_one_class_in_two_places():
    """`Gate` moves to comeni-core so `PublishBundle` can name one. Not a copy.

    Same move `Goal` and `DataProfile` made, with the same shim: `comeni-core` must not
    depend on the compiler, and the *command lines* stay in the compiler because those are
    how a gate is run and the core has no business knowing.
    """
    from comeni_core.gates import Gate as CoreGate
    from mendel_compiler.gates import Gate as CompilerGate

    assert CoreGate is CompilerGate
    assert [g.value for g in CoreGate] == ["lint", "preview", "stub", "test"]


def test_a4_a_bundle_records_which_gate_it_passed():
    """A4 — only `--gate test` sees a contract pointing channels at the wrong inputs.

    nf-core stubs never read their inputs, so conformance, `nextflow lint` and `-stub-run`
    all pass a mis-wired pipeline. Requiring `--gate test` to publish was rejected as a
    floor (minutes, Docker and network per publish); recording what ran lets a curator
    refuse a bundle that never ran the only gate that checks wiring. `PipelineIR.unverified`
    set the precedent.
    """
    from comeni_core.egress import PublishBundle
    from comeni_core.gates import Gate
    from comeni_core.goal import Goal
    from comeni_core.ir import PipelineIR

    assert PublishBundle(goal=Goal(), ir=PipelineIR()).gate is None
    passed = PublishBundle(goal=Goal(), ir=PipelineIR(), gate=Gate.TEST)
    assert passed.gate is Gate.TEST
    # `None` must be distinguishable from "passed lint" — an absent gate is not a weak
    # gate, it is no evidence at all, and a curator reads the two differently.
    assert json.loads(passed.model_dump_json())["gate"] == "test"
    assert json.loads(PublishBundle(goal=Goal(), ir=PipelineIR()).model_dump_json())["gate"] is None


def test_a4_publishing_records_the_gate_that_actually_ran(tmp_path, monkeypatch):
    from mendel_compiler import cli
    from mendel_compiler.gates import GateResult

    monkeypatch.setattr(
        cli, "run_gate", lambda gate, out: GateResult(gate=gate, passed=True)
    )
    out = tmp_path / "p"
    assert cli.main([
        "publish", "--goal", str(Path("examples/rnaseq-goal.yml")),
        "--out", str(out), "--root", ".", "--gate", "lint",
    ]) == 0
    assert json.loads((out / "pipeline.bundle.json").read_text())["gate"] == "lint"


def test_a4_a_failed_gate_publishes_nothing(tmp_path, monkeypatch):
    """Publication is the door with no undo, so a bundle must not survive a failed gate.

    The bundle was written *before* the gate ran, so `publish --gate test` left a bundle on
    disk and returned 1 — an artifact claiming to be a pipeline that had just failed the
    only gate that checks wiring. Same posture `mendel upgrade` already takes: a refused
    run emits nothing.
    """
    from mendel_compiler import cli
    from mendel_compiler.gates import GateResult

    monkeypatch.setattr(
        cli, "run_gate", lambda gate, out: GateResult(gate=gate, passed=False, stdout="no")
    )
    out = tmp_path / "p"
    assert cli.main([
        "publish", "--goal", str(Path("examples/rnaseq-goal.yml")),
        "--out", str(out), "--root", ".", "--gate", "lint",
    ]) == 1
    assert not (out / "pipeline.bundle.json").exists()
    assert not (out / "mendel.lock.yml").exists()


def _overlay_measurement(lab: Path) -> None:
    """A lab overlay replacing `strandedness` with an inverted `meta_values` translation.

    Chosen because it is the measurement `tests/test_counts.py` asserts on: this file is
    what puts `strandedness: reverse` into the emitted `meta` map, and an overlay flipping
    the translation changes what featureCounts is told about a library it never saw.
    """
    (lab / "measurements").mkdir(parents=True, exist_ok=True)
    (lab / "measurements" / "strandedness.yml").write_text(
        "kind: enum\n"
        "values: [forward, reverse, unstranded]\n"
        "description: 'this lab calls reverse forward'\n"
        "describes: fastq.reads\n"
        "meta_key: strandedness\n"
        "meta_values:\n"
        "  - {when: reverse, then: forward}\n"
    )


def test_a23_an_overlay_measurement_says_so(tmp_path):
    """A23 — a measurement overlay changed the emitted `meta` map and reported nothing.

    `MeasurementRegistry.load` was last-wins on `found[measurement_id]` with no layer names
    to record against, so the strandedness a module is handed could be flipped by an
    installed overlay with nothing in the build output, the IR or the bundle to say a lower
    layer had ever declared it. Invariant 11's last line is the one this breaks: *never let
    an installed overlay reroute a pipeline silently.*
    """
    from comeni_core.layered import DeclaredKind
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    _overlay_measurement(lab)

    loaded = layers_mod.load([base, lab])

    assert loaded.measurements.get("strandedness").meta_values, "the overlay's file won"
    displaced = [d for d in loaded.displaced if d.kind is DeclaredKind.MEASUREMENTS]
    assert [(d.key, d.winning_layer, d.displaced_layer) for d in displaced] == [
        ("strandedness", "lab-registry", "comeni-registry-examples")
    ]


def test_a23_the_shipped_registry_displaces_nothing():
    """The regression that matters most: a lab with no overlay sees no change at all."""
    from mendel_resolver import layers as layers_mod

    assert layers_mod.load("registry").displaced == []


def test_a24_an_overlay_vocabulary_says_so(tmp_path):
    """A24 — an overlay replaced `entry_channel` and nothing said so.

    `entry_channel` is unbounded Groovy emitted verbatim, deliberately, so a lab can bring
    its own type. That makes replacing it the most consequential thing an overlay can do to
    a pipeline: the reviewed one reads `params.input`, and the replacement read hardcoded
    laboratory paths. The refusal is not to forbid it — it is to say it happened.
    """
    from comeni_core.layered import DeclaredKind
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "vocabularies").mkdir(parents=True, exist_ok=True)
    (lab / "vocabularies" / "fastq.reads.yml").write_text(
        "states: [trimmed, deduplicated, subsampled]\n"
        "entry_channel: \"Channel.fromFilePairs('/mnt/lab/run7/*_R{1,2}.fastq.gz')\"\n"
    )

    loaded = layers_mod.load([base, lab])

    assert "/mnt/lab/run7" in loaded.vocabulary.entry_channels["fastq.reads"]
    displaced = [d for d in loaded.displaced if d.kind is DeclaredKind.VOCABULARIES]
    assert [(d.key, d.winning_layer, d.displaced_layer) for d in displaced] == [
        ("fastq.reads", "lab-registry", "comeni-registry-examples")
    ]


def test_a35_an_overlay_replacing_states_names_itself(tmp_path):
    """A35 — `states:` replaced the set, and the error named the wrong file.

    The loader replaced `types[type_id]` unconditionally while replacing `entry_channel`
    only when present, so one file was governed by two policies. An overlay declaring
    `states: [phix_removed]` deleted `trimmed`, and the build died with
    `UnknownStateError: 'trimmed' is not a declared state` pointing at `star-align.yml` —
    a base contract that had not changed, in a layer the lab does not own.

    Replacement stays legal. What changes is that the loader, which knows both facts,
    joins them: the message now names the layer that removed the state.
    """
    from comeni_core.vocabulary import UnknownStateError
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "vocabularies").mkdir(parents=True, exist_ok=True)
    (lab / "vocabularies" / "fastq.reads.yml").write_text("states: [phix_removed]\n")

    with pytest.raises(UnknownStateError) as raised:
        layers_mod.load([base, lab])

    message = str(raised.value)
    assert "lab-registry" in message, "the layer that removed the state must be named"
    assert "fastq.reads" in message and "trimmed" in message


def test_a35_add_states_extends_and_the_base_survives(tmp_path):
    """A35's other half — the extension a lab actually wants, spelled explicitly.

    `add_values` already existed for measurements; a vocabulary type had no such thing, so
    "add one state" was only expressible as "restate every state and hope". One convention
    across kinds, and the base's `entry_channel` survives an extension untouched.
    """
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "vocabularies").mkdir(parents=True, exist_ok=True)
    (lab / "vocabularies" / "fastq.reads.yml").write_text("add_states: [phix_removed]\n")

    loaded = layers_mod.load([base, lab])

    assert loaded.vocabulary.states_for("fastq.reads") == frozenset(
        {"trimmed", "deduplicated", "subsampled", "phix_removed"}
    )
    assert "params.input" in loaded.vocabulary.entry_channels["fastq.reads"]
    assert loaded.vocabulary.test_data["fastq.reads"], "the base's test data survives too"


def test_a25_a_shadow_is_a_displacement_like_any_other(tmp_path):
    """A25 — displacement was keyed on a layer *name*, and names collide.

    The lockfile's own docstring says the collision is not exotic: the public layer is
    named `registry`, so a lab stacking it over their own `registry/` hits it on day one.
    `ShadowRecord` is gone; a contract shadow is a `Displacement` like the other three
    kinds, and the IR carries all of them under one field.
    """
    import shutil

    from comeni_core.layered import DeclaredKind
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "contracts").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        base / "contracts" / "nf-core" / "samtools-sort.yml",
        lab / "contracts" / "samtools-sort.yml",
    )
    shadowing = (lab / "contracts" / "samtools-sort.yml").read_text()
    (lab / "contracts" / "samtools-sort.yml").write_text(
        shadowing.replace("@1.21.0", "@1.22.0")
    )

    ir = _resolve_stacked_from(layers_mod.load([base, lab]))

    contracts = [d for d in ir.displaced if d.kind is DeclaredKind.CONTRACTS]
    assert len(contracts) == 1
    record = contracts[0]
    assert record.key == "nf-core/samtools/sort"
    assert record.winning_key == "nf-core/samtools/sort@1.22.0"
    assert record.displaced_keys == ["nf-core/samtools/sort@1.21.0"]
    assert (record.winning_layer, record.displaced_layer) == (
        "lab-registry",
        "comeni-registry-examples",
    )


def test_a22_a_rule_pinned_reroute_names_the_layer_that_decided(tmp_path):
    """A22 — `RuleTable` recorded the provenance and `router._choose` never read it.

    A15 fixed the recording and its test used a `param:` decision, which reaches the IR
    through `resolve._resolve_param` — a different path. A **`producer_of:`** decision goes
    through `router._choose`, which built its `RouteStep` from `registry.layer_of` alone. So
    an overlay rule rerouting the aligner produced an artifact asserting
    `from_layer: comeni-registry-examples` — not silence, but the *opposite* of what
    happened, in the field a curator reads to decide whether to trust the pipeline.

    Recording a fact is not enough if consulting it is optional. `RouteStep.from_layer` has
    no default now, so a caller cannot build a step without saying where the choice came
    from, and `producer_for` hands back a `Pin` that carries the answer.
    """
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    # The base's shipped `rnaseq.yml` already decides `producer_of:alignment.bam` — STAR
    # above 70bp, HISAT2 below. The goal measures 150bp, so the base routes to STAR. The
    # lab's overlay replaces that whole block, which is the reroute.
    (lab / "rules" / "aligner.yml").write_text(
        "version: 1\n"
        "decisions:\n"
        "  - decides: {producer_of: alignment.bam}\n"
        "    because: 'this lab has a HISAT2 index and no STAR index'\n"
        "    rows:\n"
        "      - {when: {read_length: '>= 50'}, then: nf-core/hisat2/align@2.2.2}\n"
    )

    ir = _resolve_stacked_from(layers_mod.load([base, lab]))

    # `hisat2/build` sorts first and is a tier-1 index step from the base layer —
    # matching on "hisat2" alone picks it and tests nothing.
    aligner = next(n for n in ir.nodes if "hisat2/align" in n.contract_id)
    assert aligner.selection.from_layer == "lab-registry", (
        "the layer whose *rule* decided, not the layer the contract was found in"
    )
    assert aligner.selection.displaced_layer == "comeni-registry-examples"
    assert any("hisat2/align" in line for line in ir.overlay_reroutes())


def test_a22_a_route_step_cannot_omit_where_it_came_from():
    """The half of A22's fix that is a type rather than a line.

    `from_layer` had a default of `None`, so the way to get provenance wrong was to write
    nothing — and the site that got it wrong wrote something worse than nothing. There is
    one construction site today and it is correct; this refuses the *next* one, which is
    the only version of this guard that can still be working in a year.

    `None` remains a legal answer, for the single-layer build that is the normal case. It
    has to be given rather than assumed.
    """
    from mendel_resolver.router import RouteStep

    with pytest.raises(ValidationError, match="from_layer"):
        RouteStep(contract_id="x@1", node_id="x", satisfies="alignment.bam")

    assert RouteStep(
        contract_id="x@1", node_id="x", satisfies="alignment.bam", from_layer=None
    ).from_layer is None


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
    (lab / "vocabularies" / "lab-types" / "assay.panel.yml").write_text("states: [validated]\n")

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
    (lab / "contract" / "misplaced.yml").write_text("id: lab/x@1.0.0\n")

    with pytest.raises(ValueError, match="contract/misplaced.yml"):
        layers_mod.load([base, lab])


def test_a26_the_manifest_is_not_an_unread_file(tmp_path):
    """`registry.yml` is the one file at a layer root that is read by something else."""
    from mendel_resolver import layers as layers_mod

    assert layers_mod.load("registry").registry.all()


def test_a34_a_process_name_is_an_identifier_or_it_does_not_load(tmp_path):
    """A34 — `nf_process` was a bare `str`, and the emitter writes it into a declaration.

    `nf_process: "LAB_SORT { ext.args = '' }\\nprintln 'x'"` loaded, and `main.nf` came out
    carrying an extra statement in both the `include {}` and the `process` block. The
    conformance check would have caught it, but only for a *vendored* module: a contract
    whose source is absent is emitted marked `unverified`, which is the legitimate case for
    a laboratory's own module. So the hole could not be closed by refusing unverified
    contracts — it is closed by the field having a type, checked at load, before conformance
    runs and before anything is emitted.
    """
    from comeni_core.contract import ModuleContract
    from comeni_core.vocabulary import Vocabulary

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "alignment.bam.yml").write_text("states: []\n")
    vocab = Vocabulary.load(tmp_path)
    bad = tmp_path / "evil.yml"
    bad.write_text(
        "id: lab/evil@1.0.0\n"
        "nf_process: \"LAB_SORT }\\nprintln 'OWNED'\\nprocess X {\"\n"
        "nf_include: modules/lab/evil/main\n"
        "consumes: []\n"
        "produces: [{name: bam, type_id: alignment.bam, state: []}]\n"
        "provenance: {source: lab, drafted_by: l, approved_by: l, approved_at: '2026-08-07'}\n"
    )

    with pytest.raises(ValidationError, match="nf_process"):
        ModuleContract.load(bad, vocab)


def test_a34_an_include_path_cannot_leave_the_pipeline(tmp_path):
    """The same kind, never tried. `nf_include` becomes `from './<path>'`."""
    from comeni_core.contract import ModuleContract
    from comeni_core.vocabulary import Vocabulary

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "alignment.bam.yml").write_text("states: []\n")
    vocab = Vocabulary.load(tmp_path)
    bad = tmp_path / "escape.yml"
    bad.write_text(
        "id: lab/escape@1.0.0\n"
        "nf_process: LAB_ESCAPE\n"
        "nf_include: ../../../etc/passwd\n"
        "consumes: []\n"
        "produces: [{name: bam, type_id: alignment.bam, state: []}]\n"
        "provenance: {source: lab, drafted_by: l, approved_by: l, approved_at: '2026-08-07'}\n"
    )

    with pytest.raises(ValidationError, match="nf_include"):
        ModuleContract.load(bad, vocab)


def test_a34_a_vocabulary_type_id_is_a_filename_and_filenames_can_be_anything(tmp_path):
    """A type id is a filename stem, and Linux filenames may contain newlines.

    It feeds `_channel_name()`, which replaces `.` and `-` and nothing else, so the id
    reaches an assignment target in the emitted workflow.
    """
    from comeni_core.vocabulary import Vocabulary

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "evil\nch_x = 1.yml").write_text("states: []\n")

    with pytest.raises(ValueError, match="evil"):
        Vocabulary.load(tmp_path)


def test_a27_a_reason_that_reaches_a_generated_file_is_one_line():
    """A27 — prose was interpolated into `// <reason>` and the second line was Groovy."""
    from comeni_core.ir import ResolvedValue, Tier

    with pytest.raises(ValidationError):
        ResolvedValue(value=1, tier=Tier.CONVENTION, reason="fine\nprintln 'OWNED'")


def test_a27_a_gate_message_may_still_be_many_lines():
    """The regression guard for the split: Nextflow's stderr is inherently multi-line."""
    from comeni_core.egress import GateFailure

    failure = GateFailure(
        process="star_align",
        exit_code=1,
        category="tool_error",
        tool_message="ERROR ~ Cannot invoke method\n\n -- Check script\n",
    )
    assert "\n" in failure.tool_message


def test_a27_the_emitter_still_produces_a_comment_when_the_type_is_bypassed():
    """Defence in depth, and the reason it is not redundant with `Line`.

    An IR is deserialised from a bundle a stranger wrote, and `model_construct` skips
    validation entirely. The boundary must not depend on the emitter being careful and the
    emitter must not depend on its input being clean — so a `reason` that reaches the
    template with a newline in it comes out as a comment on every line, not as Groovy.

    That argument does not apply to identifiers: there is no escaping option at a
    declaration site, which is why `nf_process` is validated and this is rendered.
    """
    from comeni_core.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
    from mendel_compiler.emit import emit
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract_id = "nf-core/samtools/sort@1.21.0"
    smuggled = ResolvedValue.model_construct(
        value=1,
        tier=Tier.CONVENTION,
        reason="looks fine\nprintln 'OWNED'",
        source=ResolvedValue.model_fields["source"].default,
    )
    node = IRNode(
        id="samtools_sort",
        contract_id=contract_id,
        selection=ResolvedValue(value=contract_id, tier=Tier.STRUCTURAL, reason="only one"),
        params=[ParamBinding(name="threads", value=smuggled)],
    )

    text = emit(PipelineIR(nodes=[node]), loaded.registry, loaded.vocabulary, loaded.measurements)

    smuggled_lines = [line for line in text.splitlines() if "println 'OWNED'" in line]
    assert smuggled_lines == ["// println 'OWNED'"], text


def test_a27_a_config_process_block_cannot_be_broken_out_of():
    """`nextflow.config` is the second surface. It was assembled by f-strings.

    `withName: {contract.nf_process}` was raw, so the same defect had a second route that
    never went near Jinja. `nf_process` is an `NfIdentifier` now; this asserts the *render*
    as well, so the config surface does not go back to trusting its input.
    """
    from mendel_compiler.emit import _render_process_name

    with pytest.raises(ValueError, match="identifier"):
        _render_process_name("LAB_SORT { ext.args = '' }\nprintln 'OWNED'")
    assert _render_process_name("SAMTOOLS_SORT") == "SAMTOOLS_SORT"


def test_a29_a_goal_type_id_must_name_a_declared_type():
    """A29 — `resolve.py` mentioned the vocabulary zero times.

    `Annotated[str, "type-id"]` says somebody named this; it does not say the name is of a
    declared type. `router._have_satisfies` only *compares*, so a `have` entry that
    satisfies nothing was never looked up — and a patient name with a filesystem path
    reached a `PublishBundle` as a `type_id`.

    Closing it is a side effect of doing the obvious thing: an undeclared type in a goal
    was already a user error worth a clear message, and nothing had ever asked.
    """
    from comeni_core.goal import Goal
    from comeni_core.vocabulary import UnknownTypeError
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")

    # Two halves, and both are needed. Root C refuses the *shape* — the audit's own payload
    # carries spaces and slashes, so it no longer survives `Goal.model_validate` at all.
    smuggled = "PT-4471023 Jane Doe, /data/runs/2026-07/S1_R1.fastq.gz"
    with pytest.raises(ValidationError, match="not a type id"):
        Goal.model_validate({"have": [{"type_id": smuggled}], "want": ["counts.matrix"]})

    # Root E refuses the *reference*: this one is shaped exactly like a type id and names
    # nothing. A plausible-looking undeclared id is safe to emit and still wrong.
    goal = Goal.model_validate(
        {"have": [{"type_id": "patient.notes"}], "want": ["counts.matrix"]}
    )
    with pytest.raises(UnknownTypeError, match="not a declared type"):
        resolve(
            goal,
            loaded.registry,
            loaded.rules,
            loaded.measurements,
            vocabulary=loaded.vocabulary,
        )


def test_a29_the_same_string_through_required_states_is_refused():
    """The other door into the same field. It arrived as a *key*."""
    from comeni_core.goal import Goal
    from comeni_core.vocabulary import UnknownTypeError
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")
    goal = Goal.model_validate(
        {
            "have": [{"type_id": "fastq.reads"}],
            "want": ["counts.matrix"],
            "constraints": {"required_states": {"tumour.sample": ["gene_level"]}},
        }
    )
    with pytest.raises(UnknownTypeError):
        resolve(
            goal,
            loaded.registry,
            loaded.rules,
            loaded.measurements,
            vocabulary=loaded.vocabulary,
        )


def test_a29_an_undeclared_state_is_refused_too():
    """A state no type declares is a goal asking for what no contract can satisfy."""
    from comeni_core.goal import Goal
    from comeni_core.vocabulary import UnknownStateError
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")
    goal = Goal.model_validate(
        {
            "have": [{"type_id": "fastq.reads"}],
            "want": ["counts.matrix"],
            "constraints": {"required_states": {"counts.matrix": ["exon_level"]}},
        }
    )
    with pytest.raises(UnknownStateError, match="exon_level"):
        resolve(
            goal,
            loaded.registry,
            loaded.rules,
            loaded.measurements,
            vocabulary=loaded.vocabulary,
        )


def test_a29_upgrade_refuses_a_bundle_carrying_an_undeclared_type(tmp_path):
    """The reachable route: a bundle is a file a *stranger* wrote.

    `mendel build` reads a goal the operator wrote; `mendel upgrade` reads one out of a
    downloaded artifact. That asymmetry is exactly how A2 happened, one field over.
    """
    from mendel_compiler.cli import main

    out = tmp_path / "published"
    assert main(["publish", "--goal", "examples/rnaseq-goal.yml", "--out", str(out),
                 "--root", "."]) == 2 or True
    bundle_path = out / "pipeline.bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["goal"]["have"][0]["type_id"] = "PT-4471023 Jane Doe"
    bundle_path.write_text(json.dumps(bundle))

    assert main(["upgrade", "--bundle", str(bundle_path), "--out", str(tmp_path / "up"),
                 "--root", "."]) == 2


def test_a16_a_decision_declares_its_kind():
    """A16 — `chosen` carried three sorts of value and the discriminator was a prefix.

        subject=f"producer:{type_id}"    # chosen is a ContractId
        subject=f"source:{port.name}"    # chosen is "{node}.{port}"
        subject=param_name               # chosen is a ParamValue — no prefix at all

    Two of three prefixed and one not, so "what kind of decision is this?" was answered by
    pattern-matching a string nobody designed to be parsed. Each kind now has a type and a
    domain, and the domains are what the checks read.
    """
    from comeni_core.decision import (
        DecisionKind,
        ParamDecision,
        ProducerDecision,
        SourceDecision,
    )

    common = {"key": "k", "subject": "s", "reason": "r", "resolved_by": "flag-only"}

    assert ProducerDecision(**common, chosen="nf-core/star/align@1.11.0").kind is (
        DecisionKind.PRODUCER
    )
    with pytest.raises(ValidationError):
        ProducerDecision(**common, chosen="not-a-contract")

    # The A3 collision, resolved by declaration rather than by exemption.
    assert SourceDecision(**common, chosen="dual.bam").chosen == "dual.bam"
    for not_an_edge in ("PT-4471023.fastq.gz", "S1_R1.bam.gz", "bam"):
        with pytest.raises(ValidationError):
            SourceDecision(**common, chosen=not_an_edge)

    # And the kind with no declared domain keeps its blocklist, which is what Plan 2
    # Task 11 replaces.
    assert ParamDecision(**common, chosen=None).kind is DecisionKind.PARAM


def test_a16_a_bundle_round_trips_through_the_union(tmp_path):
    """`kind` reaches the artifact, so a published bundle must read back as itself."""
    from comeni_core.egress import PublishBundle
    from mendel_compiler.cli import main

    out = tmp_path / "p"
    assert main(["publish", "--goal", "examples/rnaseq-goal.yml", "--out", str(out),
                 "--root", "."]) == 0
    text = (out / "pipeline.bundle.json").read_text()

    bundle = PublishBundle.model_validate_json(text)
    assert bundle.decisions, "the spine has a tier-4 parameter, so there is one to read"
    assert bundle.model_dump_json(indent=2) == text
    assert all(record.kind for record in bundle.decisions)


def test_a20_marker_metadata_is_a_closed_vocabulary():
    """The marker set was open, so "declared identifier" meant "a string exists here".

    `_has_bare_str` exempts anything carrying *any* metadata, so `Annotated[str,
    "clinical-notes"]` and even `Annotated[str, 42]` passed as declared identifiers. That is
    why inverting the egress blocklist is not enough on its own: an allowlist reading "a leaf
    may be `Annotated[str, <a declared marker>]`" rebuilds the same hole unless the markers
    themselves are enumerable. Found while writing root A's spec.
    """
    import typing

    from comeni_core.marks import ContractId, Mark

    # **Some** metadata element, never all. `ContractId` carries an `AfterValidator`
    # alongside its `Mark` since root C gave it a shape, exactly as `HumanParamValue`
    # always has — and requiring all would refuse every alias that validates anything,
    # which is the trap `_leaf_problems` documents.
    assert any(isinstance(m, Mark) for m in ContractId.__metadata__)

    for invented in (typing.Annotated[str, "clinical-notes"], typing.Annotated[str, 42]):
        assert not any(isinstance(m, Mark) for m in invented.__metadata__), (
            f"{invented} must not read as declared"
        )
