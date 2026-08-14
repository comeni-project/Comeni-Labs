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
from comeni_core.tiers import Tier
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


def _published_pipeline(tmp_path, root, name="published"):
    """Build and certify a pipeline, and hand back the file that names it.

    `publish` stopped writing an artifact of its own in Plan 1.10 Task 10 — the directory is
    the artifact — so this is `build` then `publish`, and what comes back is `pipeline.yml`.
    """
    from mendel_compiler.cli import main

    out = tmp_path / name
    assert main(["build", "--goal", str(root / "examples" / "rnaseq-goal.yml"),
                 "--out", str(out), "--root", str(root)]) == 0
    assert main(["publish", str(out / "pipeline.yml"), "--root", str(root)]) == 0
    return out / "pipeline.yml"


def test_a2_upgrade_refuses_a_pipeline_carrying_an_undeclared_measurement(tmp_path):
    """The reachable route, end to end: a `pipeline.yml` is a *downloaded* artifact.

    `mendel upgrade` reads its goal from that file rather than from a `--goal`, so it was the
    one verb reading something a stranger wrote and the one verb with no check. Reproduced
    in the audit as exit 0 with `sample_name: PATIENT-00417` in the emitted IR, and
    re-published verbatim by any following `mendel publish`.
    """
    import yaml
    from mendel_compiler.cli import main

    root = Path(__file__).parent.parent
    published = _published_pipeline(tmp_path, root)

    doc = yaml.safe_load(published.read_text())
    doc["goal"]["profile"]["measurements"].append(
        {"measurement": "sample_name", "value": "PATIENT-00417", "source": "goal", "by": None}
    )
    published.write_text(yaml.safe_dump(doc, sort_keys=False))

    out = tmp_path / "upgraded"
    assert main(["upgrade", str(published), "--out", str(out), "--root", str(root)]) != 0
    assert not (out / "pipeline.yml").exists(), "a refused upgrade must emit nothing"


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


def test_a11_a_duplicate_binding_is_refused_before_it_can_reach_a_compare():
    """A11, one layer higher than it used to sit, and refusing instead of surviving.

    Task 1 made a tie unreachable *at the contract*, and this asserted the emitter would
    survive one anyway — because the next unorderable field on `ResolvedValue` must not
    resurrect a crash that is already fixed. A duplicate binding stayed representable, since
    an IR is deserialised from a bundle and `set_param` appends.

    Plan 1.10's `MD0212` closes it properly: two settings with one name cannot exist on a
    `Step` at all, so there is nothing left for the emitter to compare. **This test failed for
    real when that validator landed** — it constructs exactly the duplicate the validator now
    refuses, which is the guard being watched failing rather than argued about.

    Refusing beats surviving here, and by more than tidiness: `ext.args` composition sorts by
    name and *joins*, so two settings called `seq_platform` were never going to be a crash.
    They were going to be two fragments concatenated into one flag string, silently.
    """
    from comeni_core.ir import IRNode, PipelineIR, ResolvedValue, Tier
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

    with pytest.raises(ValidationError, match="MD0212"):
        _pipe(PipelineIR(nodes=[node]), loaded)


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
    the publication payload the guard reported 7 passed: `Mapping[MeasurementId, ParamValue]` is
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
    into a `DecisionRecord` and from there through door 4, the one with no undo.
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
    """`Gate` moves to comeni-core so the publication payload can name one. Not a copy.

    Same move `Goal` and `DataProfile` made, with the same shim: `comeni-core` must not
    depend on the compiler, and the *command lines* stay in the compiler because those are
    how a gate is run and the core has no business knowing.
    """
    from comeni_core.gates import Gate as CoreGate
    from mendel_compiler.gates import Gate as CompilerGate

    assert CoreGate is CompilerGate
    assert [g.value for g in CoreGate] == ["lint", "preview", "stub", "test"]


def test_a4_the_artifact_records_which_gate_it_passed():
    """A4 — only `--gate test` sees a contract pointing channels at the wrong inputs.

    nf-core stubs never read their inputs, so conformance, `nextflow lint` and `-stub-run`
    all pass a mis-wired pipeline. Requiring `--gate test` to publish was rejected as a
    floor (minutes, Docker and network per publish); recording what ran lets a curator
    refuse a pipeline that never ran the only gate that checks wiring. `PipelineIR.unverified`
    set the precedent. The field moved from `PublishBundle` to `Pipeline` with the door in
    Plan 1.10 Task 11; the claim did not move at all.
    """
    from comeni_core.gates import Gate
    from comeni_core.goal import Goal
    from comeni_core.pipeline import Pipeline

    assert Pipeline(goal=Goal()).gate is None
    passed = Pipeline(goal=Goal(), gate=Gate.TEST)
    assert passed.gate is Gate.TEST
    # `None` must be distinguishable from "passed lint" — an absent gate is not a weak
    # gate, it is no evidence at all, and a curator reads the two differently.
    assert json.loads(passed.model_dump_json())["gate"] == "test"
    assert json.loads(Pipeline(goal=Goal()).model_dump_json())["gate"] is None


def test_a4_publishing_records_the_gate_that_actually_ran(tmp_path, monkeypatch):
    import yaml
    from mendel_compiler import cli
    from mendel_compiler.gates import GateResult

    monkeypatch.setattr(
        cli, "run_gate", lambda gate, out: GateResult(gate=gate, passed=True)
    )
    out = tmp_path / "p"
    assert cli.main([
        "build", "--goal", str(Path("examples/rnaseq-goal.yml")),
        "--out", str(out), "--root", ".",
    ]) == 0
    assert cli.main([
        "publish", str(out / "pipeline.yml"), "--root", ".", "--gate", "lint",
    ]) == 0
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"


def test_a4_a_failed_gate_publishes_nothing(tmp_path, monkeypatch):
    """Publication is the door with no undo, so a *verdict* must not survive a failed gate.

    The bundle was written before the gate ran, so `publish --gate test` left a bundle on
    disk and returned 1 — an artifact claiming to be a pipeline that had just failed the only
    gate that checks wiring. The bundle is gone since Plan 1.10 and the claim survives it: a
    failed gate stamps `gate: null`, which is no evidence, and no evidence must never read as
    a gate that passed.
    """
    import yaml
    from mendel_compiler import cli
    from mendel_compiler.gates import GateResult

    monkeypatch.setattr(
        cli, "run_gate", lambda gate, out: GateResult(gate=gate, passed=False, stdout="no")
    )
    out = tmp_path / "p"
    assert cli.main([
        "build", "--goal", str(Path("examples/rnaseq-goal.yml")),
        "--out", str(out), "--root", ".",
    ]) == 0
    assert cli.main([
        "publish", str(out / "pipeline.yml"), "--root", ".", "--gate", "lint",
    ]) == 1
    # The claim moved with the artifact. There is no bundle to be absent any more, so what
    # must not survive a failed gate is the *verdict*: `gate: null` is no evidence, and it
    # must never read as a gate that passed.
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] is None


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


def test_a27_no_resolver_prose_reaches_main_nf_at_all():
    """Defence in depth, and the reason it is not redundant with `Line`.

    An IR is deserialised from a bundle a stranger wrote and `model_construct` skips
    validation entirely, so the emitter must not depend on its input being clean.

    Two rewrites, both forced and both by a guard catching this test rather than its subject.
    It asserted that a multi-line `reason` came out as a comment on *every* line rather than
    as Groovy; Plan 1.10 removed the comment, because reasons live in `pipeline.yml` now, so
    the assertion became the stronger one that replaced it. Then `MD0216` caught the fixture:
    it hung the smuggled value on a `samtools/sort` binding, and that contract declares
    `params: []`, so the value was dropped before anything looked at it. **The test was
    asserting nothing, twice over.**

    It now bypasses every type on the way in, which is what "the emitter does not trust its
    input" actually requires — materialisation refuses this input, as the test below asserts.
    """
    from comeni_core.pipeline import Pipeline, Setting, Step, Why
    from comeni_core.routes import Via
    from comeni_core.tiers import ValueSource
    from mendel_compiler.emit import emit

    why = Why.model_construct(
        tier=Tier.CONVENTION,
        source=ValueSource.RESOLVER,
        reason="looks fine\nprintln 'OWNED'",
    )
    pipeline = Pipeline.model_construct(
        version=1,
        steps=[
            Step.model_construct(
                id="samtools_sort",
                module=None,
                process="SAMTOOLS_SORT",
                include="modules/nf-core/samtools/sort/main",
                why=why,
                ext_args="",
                inputs=[],
                call=[],
                settings=[
                    Setting.model_construct(name="threads", value=1, via=Via.EXT, why=why)
                ],
            )
        ],
        channels=[],
    )

    text = emit(pipeline)
    assert "println 'OWNED'" not in text, text
    assert "looks fine" not in text, "no resolver prose reaches main.nf any more"


def test_a27_prose_reaching_the_pipeline_file_is_refused_at_materialisation():
    """A27 at its new address, which is the other half of Task 5's note.

    Reasons no longer reach `main.nf`; they reach `pipeline.yml`, verbatim and by design —
    that file exists to say *why*. So the surface moved rather than closed, and `Why.reason`
    is a `Line` for the same argument `ResolvedValue.reason` is: a value smuggled past one
    type must not be carried by the next one without complaint.
    """
    from comeni_core.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    # A contract that actually declares a param. `samtools/sort` declares none, so a binding
    # on it is dropped before `Why` ever sees the prose — which is how the first draft of this
    # test passed against a materialisation that carried the newline happily.
    contract = next(c for c in loaded.registry.all() if c.params)
    smuggled = ResolvedValue.model_construct(
        value="illumina",
        tier=Tier.CONVENTION,
        reason="looks fine\ngate: test",
        source=ResolvedValue.model_fields["source"].default,
    )
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="only one"),
        params=[ParamBinding(name=contract.params[0].name, value=smuggled)],
    )
    with pytest.raises(ValidationError):
        _pipe(PipelineIR(nodes=[node]), loaded)


def test_a27_prose_cannot_forge_a_key_even_with_every_type_bypassed():
    """Defence in depth, and the reason it is not redundant with the test above.

    Same argument as the `main.nf` version: the boundary must not depend on the writer being
    careful, and the writer must not depend on its input being clean. Different grammar,
    though — a `reason` that closed its own scalar and opened a key would rewrite the document
    that documents the pipeline, and **`gate:` is in that document**: forging a passed gate is
    forging the evidence a curator reads.

    `yaml.safe_dump` makes that structurally impossible, which is exactly what would have been
    said about `nextflow.config` right up until somebody assembled it with f-strings. A27 had
    two surfaces for that reason. This asserts the property instead of assuming the library.
    """
    import yaml as _yaml
    from comeni_core.pipeline import Pipeline, Setting, Step, Why
    from comeni_core.routes import Via
    from comeni_core.tiers import ValueSource
    from mendel_compiler import pipeline_file

    forged = "looks fine\ngate: test\nsteps: []"
    why = Why.model_construct(tier=Tier.CONVENTION, source=ValueSource.RESOLVER, reason=forged)
    pipeline = Pipeline.model_construct(
        version=1,
        steps=[
            Step.model_construct(
                id="samtools_sort",
                module=None,
                process="SAMTOOLS_SORT",
                include="modules/nf-core/samtools/sort/main",
                why=why,
                settings=[
                    Setting.model_construct(name="threads", value=1, via=Via.EXT, why=why)
                ],
            )
        ],
    )
    reparsed = _yaml.safe_load(pipeline_file.dump(pipeline))
    assert reparsed["gate"] is None, "prose forged the gate verdict"
    assert len(reparsed["steps"]) == 1, "prose rewrote the step list"
    assert reparsed["steps"][0]["why"]["reason"] == forged, "and it survives verbatim"


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
    reached the publication payload as a `type_id`.

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


def test_a29_upgrade_refuses_a_pipeline_carrying_an_undeclared_type(tmp_path):
    """The reachable route: a `pipeline.yml` is a file a *stranger* wrote.

    `mendel build` reads a goal the operator wrote; `mendel upgrade` reads one out of a
    downloaded artifact. That asymmetry is exactly how A2 happened, one field over.
    """
    import yaml
    from mendel_compiler.cli import main

    published = _published_pipeline(tmp_path, Path("."))
    doc = yaml.safe_load(published.read_text())
    doc["goal"]["have"][0]["type_id"] = "PT-4471023 Jane Doe"
    published.write_text(yaml.safe_dump(doc, sort_keys=False))

    assert main(["upgrade", str(published), "--out", str(tmp_path / "up"),
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


def test_a16_the_artifact_round_trips_through_the_union(tmp_path):
    """`kind` reaches the artifact, so a published pipeline must read back as itself.

    The subject moved from `pipeline.bundle.json` to `pipeline.yml` and the property got
    stronger on the way: `build` now performs this round trip on **every** run and refuses
    with `MD0206` if it fails, so the discriminated union is exercised continuously rather
    than in this test alone.
    """
    from mendel_compiler import pipeline_file

    published = _published_pipeline(tmp_path, Path("."))
    text = published.read_text()

    pipeline = pipeline_file.load(published)
    assert pipeline.decisions, "the spine has a tier-4 parameter, so there is one to read"
    assert all(record.kind for record in pipeline.decisions)
    assert pipeline_file.dump(pipeline) == text, "byte-identical, not merely equivalent"


def test_a31_a_contract_cannot_be_read_two_ways(tmp_path):
    """A31 — `yaml.safe_load` takes the last value for a repeated key, silently.

    A contract with two `priority:` lines loaded at the second one. That is A10's argument
    one level down: the digest pins what survived parsing rather than what the file says, so
    a reviewer reading `priority: 0` at the top and a build routing on `priority: 999` from
    the bottom are both looking at a correctly signed layer.
    """
    from comeni_core.vocabulary import Vocabulary
    from comeni_core.yaml_strict import DuplicateKeyError

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "alignment.bam.yml").write_text("states: []\n")
    contract = tmp_path / "two-ways.yml"
    contract.write_text(
        "id: lab/two-ways@1.0.0\n"
        "nf_process: TWO_WAYS\n"
        "nf_include: modules/lab/two/main\n"
        "priority: 0\n"
        "produces: [{name: bam, type_id: alignment.bam, state: []}]\n"
        "provenance: {source: lab, drafted_by: l, approved_by: l, approved_at: '2026-08-07'}\n"
        "priority: 999\n"
    )

    from comeni_core.contract import ModuleContract

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
        *Path("vendor").rglob("meta.yml"),
        *Path("vendor").rglob("*.yaml"),
    ]
    assert len(owned) > 20, "this test is only meaningful if it reads something"
    for path in owned:
        yaml_strict.load(path)


def test_a32_the_seam_a_model_sits_behind_is_a_declared_type():
    """A32 — `Ambiguity` was the one door with no type discipline.

    `candidates: list[Any]`, `context: dict[str, Any]`, and **no `model_config` at all**, so
    `extra` defaulted to *ignore*: a field misspelled at the call site vanished silently. It
    projects to `AmbiguityRequest`, which is a closed payload — the closed half was
    downstream of the open half, which is no boundary at all.
    """
    from comeni_core.decision import ParamAsked, Resolution

    with pytest.raises(ValidationError):
        ParamAsked(node_id="n", subject="s", candidates=[], extra=1)

    # `context` is gone: its three uses are declared fields on the kinds that have them.
    with pytest.raises(ValidationError):
        ParamAsked(node_id="n", subject="s", context={"anything": object()})

    # And the answer coming back is a boundary too — `resolved_by` reaches every decision
    # record and therefore a publish bundle.
    with pytest.raises(ValidationError):
        Resolution(chosen=None, reason="r", resolved_by="a\nb")


def test_a33_a_tier_4_reason_says_what_happened(tmp_path):
    """A33 — `router._choose`'s tier-4 reason always read "chosen by id order".

    True when a tie is broken alphabetically and false when a resolver answered, which is
    the case a reviewer most needs described accurately: the record said the machine
    shrugged when a human had in fact decided.

    The first version of this test ran a goal with no tie in it and asserted over an empty
    loop — the same shape as the `_source_for` test the 2026-08-06 audit caught. The tie is
    built here, and asserted to exist before anything is asserted about it.
    """
    import shutil

    from comeni_core.decision import Resolution
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    class _PicksLast:
        def resolve(self, ambiguity):
            return Resolution(
                chosen=sorted(ambiguity.candidates)[-1],
                reason="a person read both modules and chose",
                resolved_by="human",
            )

    layer = tmp_path / "registry"
    shutil.copytree("registry", layer)
    original = (layer / "contracts" / "nf-core" / "trimgalore.yml").read_text()
    # Same priority, same output, different module key: nothing distinguishes them.
    (layer / "contracts" / "nf-core" / "fastp.yml").write_text(
        original.replace("nf-core/trimgalore@0.6.10", "nf-core/fastp@0.24.0").replace(
            "TRIMGALORE", "FASTP"
        )
    )

    loaded = layers_mod.load(layer)
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["fastq.reads"],
        constraints={"required_states": {"fastq.reads": ["trimmed"]}},
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=_PicksLast(),
    )

    ambiguous = [n for n in ir.nodes if n.selection.tier is Tier.AMBIGUOUS]
    assert ambiguous, "the tie must actually happen, or this asserts over an empty loop"
    for node in ambiguous:
        assert "chosen by id order" not in node.selection.reason, node.selection.reason
        assert "human" in node.selection.reason, node.selection.reason


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


def _pipe(ir, loaded):
    """Materialise an IR for the emitter.

    `emit` takes one argument since Plan 1.10 Task 5 — everything it used to look up in the
    registry, vocabulary and measurements now lives on the `Pipeline`.

    `goal` is keyword-only and required since Task 6. An empty one is honest here: these
    fixtures start from an IR and never had a goal to record.
    """
    from comeni_core.goal import Goal
    from comeni_core.pipeline import Pipeline

    return Pipeline.of(ir, loaded.registry, loaded.vocabulary, loaded.measurements, goal=Goal())


# --- Plan 1.10 Task 8: an override is a different act from a goal pin -----------------
#
# Issue #10's tail. Answering a tier-4 parameter must clear the flag without pretending the
# question was never asked — and, as it turned out, without the answer being thrown away.


def _override_record(value="illumina"):
    from comeni_core.decision import ParamDecision

    return ParamDecision(
        key="star_align.seq_platform",
        subject="seq_platform",
        candidates=[None],
        chosen=None,
        human_override=value,
        reason="our sequencer",
        resolved_by="human",
    )


def _loaded():
    from mendel_resolver import layers as layers_mod

    return layers_mod.load("registry")


def _resolved(resolver=None, mutate=None, prior=()):
    """The shipped goal, resolved. `mutate` edits the raw mapping before validation.

    `prior` is the recorded decisions behind a replayed human override. A56: `resolve()`
    honours `source: HUMAN` only where a record the *caller* supplied says a person answered
    that question with that value, so replaying an override needs both the resolver and the
    records — passing the resolver alone leaves the value flagged, which is the safe
    direction and the one `mendel upgrade` relies on.
    """
    from comeni_core import yaml_strict
    from mendel_resolver.goal import Goal
    from mendel_resolver.resolve import resolve

    loaded = _loaded()
    raw = yaml_strict.load(Path("examples/rnaseq-goal.yml"))
    if mutate is not None:
        mutate(raw)
    return resolve(
        Goal.model_validate(raw),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=resolver,
        prior=prior,
    )


def _ir_with_override(value="illumina"):
    from mendel_resolver.replay import ReplayResolver

    # The record goes to both: `ReplayResolver` answers from it, and `resolve()` verifies the
    # `HUMAN` claim against it. A56 — the claim and its evidence arrive through different
    # arguments on purpose, so one object cannot supply both.
    record = _override_record(value)
    return _resolved(resolver=ReplayResolver([record]), prior=[record])


def _binding(ir, name):
    return next(b.value for n in ir.nodes for b in n.params if b.name == name)


def test_a_human_override_on_a_parameter_is_replayed_at_all():
    """It was not, and nothing said so. Found while writing the test below.

    A parameter's candidate list is literally `[None]` — a placeholder, because a `Param` has
    no declared legal values until Plan 2 Task 11 — so `_still_applies` asked whether the
    human's answer was a member of `[None]`, and it never was. **Every** override on a
    parameter was discarded, counted as newly asked, and the recorded answer thrown away.

    That is issue #10's shape exactly: a mechanism that runs, records, and changes nothing.
    """
    from comeni_core.decision import ParamAsked
    from mendel_resolver.replay import ReplayResolver

    resolver = ReplayResolver([_override_record()])
    resolution = resolver.resolve(
        ParamAsked(node_id="star_align", subject="seq_platform", candidates=[None])
    )
    assert resolution.chosen == "illumina", "the human's answer must be the answer"
    assert resolver.replayed == ["star_align.seq_platform"]
    assert resolver.fresh == [], "an answered question is not a new one"


def test_an_override_keeps_the_tier_it_displaced():
    """Collapsing it to tier 1 would say "no choice existed", which is what a *goal pin*
    means and is precisely what did not happen here. Resolution met a real ambiguity and
    could not settle it; a person settled it afterwards, and a reviewer reading a curated
    pipeline needs to see that it contains a question rather than that it contains none."""
    from comeni_core.tiers import ValueSource

    value = _binding(_ir_with_override(), "seq_platform")
    assert value.value == "illumina"
    assert value.tier is Tier.AMBIGUOUS
    assert value.source is ValueSource.HUMAN


def test_a_goal_pin_is_still_tier_one_and_still_says_goal():
    """The regression guard for the split. `ValueSource`'s docstring argues that a
    goal-pinned param is legitimately tier 1 — the user removed the ambiguity before
    anything looked at it — and that argument stays true."""
    from comeni_core.tiers import ValueSource

    def pin(raw):
        raw["constraints"] = {"params": [{"name": "seq_platform", "value": "illumina"}]}

    ir = _resolved(mutate=pin)
    value = _binding(ir, "seq_platform")
    assert value.tier is Tier.STRUCTURAL
    assert value.source is ValueSource.GOAL
    assert ir.overrides() == [], "a pin is not an override; the two must not merge"


def test_an_answered_setting_leaves_needs_review_and_appears_in_overrides():
    """Otherwise the count never reaches zero and the CLI says REVIEW for ever on a question
    already answered. `lockfile.py` makes this argument about a different list and it is the
    sharper one: a list that cries wolf gets ignored, so the genuinely unanswered tier-4
    beside it goes unread too."""
    ir = _ir_with_override()
    assert "star_align.seq_platform" not in ir.needs_review()
    assert any("star_align.seq_platform" in item for item in ir.overrides())


def test_an_unanswered_tier_four_still_needs_review():
    """The other half, and the one that matters most: clearing the flag must depend on
    somebody having answered, not on the machinery having run."""
    ir = _resolved()
    assert "star_align.seq_platform" in ir.needs_review()
    assert ir.overrides() == []


def test_an_override_reaches_the_pipeline_file_as_source_human():
    """The artifact is where a reviewer meets this, so it has to survive materialisation.

    `Why.source` already carried a `ValueSource`; what changed is that there is now a value
    for it to carry. Without this the file would say `source: resolver` beside a value no
    resolver chose."""
    from comeni_core.tiers import ValueSource

    pipeline = _pipe(_ir_with_override(), _loaded())
    step = next(s for s in pipeline.steps if s.id == "star_align")
    setting = next(s for s in step.settings if s.name == "seq_platform")
    assert setting.value == "illumina"
    assert setting.why.source is ValueSource.HUMAN
    assert setting.why.tier is Tier.AMBIGUOUS


def test_a_binding_with_no_declared_param_refuses_instead_of_vanishing():
    """MD0216, and it exists because two A27 tests passed for the wrong reason.

    Both hung a smuggled value on a `nf-core/samtools/sort` binding, and that contract
    declares `params: []` — so `_settings` dropped the binding before anything looked at it,
    and neither test was asserting what its name said.

    The drop itself is the defect: a value resolution recorded, absent from the artifact that
    claims to record every value, with nothing said. It is the orphan case one level below
    `MD0203`, and it refuses for the same reason that one does.

    Resolution cannot produce this — it sets parameters *from* `contract.params` — so the
    input is a deserialised or hand-built IR, which is exactly the input `Pipeline.of` must
    not trust.

    **This test exists because reverting the refusal broke nothing.** The rule shipped first
    and the guard was written after a revert probe found it inert, which is A14's finding
    happening to the person who had just written A14's ledger row.
    """
    from comeni_core.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    # `samtools/sort` until Plan 1.14, which routed its `index_format` (A91). The assertion
    # below is what caught that, and it is why the fixture names its requirement rather than
    # assuming it.
    contract_id = "nf-core/fastqc@0.12.1"
    assert loaded.registry.get(contract_id).params == [], "the fixture needs a param-less one"

    node = IRNode(
        id="samtools_sort",
        contract_id=contract_id,
        selection=ResolvedValue(value=contract_id, tier=Tier.STRUCTURAL, reason="only one"),
        params=[
            ParamBinding(
                name="threads",
                value=ResolvedValue(value=4, tier=Tier.CONVENTION, reason="a default"),
            )
        ],
    )
    with pytest.raises(ValueError, match="MD0216"):
        _pipe(PipelineIR(nodes=[node]), loaded)


def test_a_binding_the_contract_does_declare_is_carried():
    """The regression guard for the refusal above: it must depend on the param being absent,
    not on a binding existing at all."""
    from comeni_core.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract = next(c for c in loaded.registry.all() if c.params)
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="only one"),
        params=[
            ParamBinding(
                name=contract.params[0].name,
                value=ResolvedValue(value="illumina", tier=Tier.CONVENTION, reason="d"),
            )
        ],
    )
    pipeline = _pipe(PipelineIR(nodes=[node]), loaded)
    assert [s.name for s in pipeline.steps[0].settings] == [contract.params[0].name]


MINIMAP2 = """id: nf-core/minimap2/align@2.28.0
nf_process: MINIMAP2_ALIGN
nf_include: modules/nf-core/minimap2/align/main
consumes:
  - {name: reads, type_id: fastq.reads, state_required: [trimmed]}
produces: [{name: bam, type_id: alignment.bam, state: []}]
priority: 10
nf_inputs:
  - {ports: [reads]}
container: community.wave.seqera.io/library/minimap2:2.28--audit
provenance: {source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-14"}
"""


def _tying_layer(tmp_path: Path) -> Path:
    """One aligner at STAR's priority, so `alignment.bam` has a genuine two-way tie.

    Inline rather than a committed fixture: the finding is entirely about *ranking*, so the
    only thing that has to be true of this contract is `priority: 10`, and a reader should
    not have to open a second file to see that. Audit A125.
    """
    layer = tmp_path / "tie-layer"
    (layer / "contracts" / "nf-core").mkdir(parents=True)
    (layer / "contracts" / "nf-core" / "minimap2-align.yml").write_text(MINIMAP2)
    (layer / "registry.yml").write_text('name: tie-layer\nversion: "0"\n')
    return layer


def _aligner_ir(*roots):
    """Resolve an aligner with no `read_length`, so the tier-3 rule cannot pin one."""
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    loaded = layers.load(list(roots))
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["alignment.bam"],
        profile=loaded.measurements.profile({"strandedness": "reverse"}),
    )
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )


def test_a125_a_tie_offers_only_the_candidates_that_tied(tmp_path):
    """A125 — adding one contract installed the aligner the registry ranked *last*.

    STAR and MINIMAP2 both sit at priority 10, so the tie is between those two. HISAT2 is at
    priority 0 and lost outright. `_choose` handed the resolver *every* candidate sorted by
    id and `FlagOnlyResolver` takes `candidates[0]`, so `hisat2` won on the letter h — and
    the artifact then reported that nothing distinguished three contracts that `priority`
    distinguishes deliberately.
    """
    registry_root = Path(__file__).parent.parent / "registry"
    ir = _aligner_ir(registry_root, _tying_layer(tmp_path))

    asked = [d for d in ir.decisions if d.subject == "producer:alignment.bam"]
    assert len(asked) == 1, [d.subject for d in ir.decisions]
    assert asked[0].candidates == [
        "nf-core/minimap2/align@2.28.0",
        "nf-core/star/align@1.11.0",
    ]
    assert "hisat2" not in asked[0].chosen


def test_a126_a_producer_decision_key_names_the_question_not_the_winner(tmp_path):
    """A126 — the key was `<winning module>.producer:<type>`, so it moved when the registry did.

    Installing one more contract renamed the question, `upgrade` found no record under the new
    name and reported the curator's recorded override as `ORPHANED — your edit no longer
    applies to anything`, while asking the identical question one line above.
    """
    registry_root = Path(__file__).parent.parent / "registry"
    ir = _aligner_ir(registry_root, _tying_layer(tmp_path))

    producer_keys = [d.key for d in ir.decisions if d.subject.startswith("producer:")]
    assert producer_keys == ["producer:alignment.bam"]


def _legacy_producer_record(candidates: list[str]):
    """A pre-1.13 producer record: the key carries the winning module's node id in front."""
    from comeni_core.decision import ProducerDecision

    return ProducerDecision(
        key="star_align.producer:alignment.bam",
        subject="producer:alignment.bam",
        reason="the lab standardised on STAR",
        resolved_by="human",
        candidates=candidates,
        chosen="nf-core/star/align@1.11.0",
        human_override="nf-core/star/align@1.11.0",
    )


def _asked_producer(candidates: list[str]):
    from comeni_core.decision import ProducerAsked

    return ProducerAsked(
        node_id="minimap2_align",
        subject="producer:alignment.bam",
        candidates=candidates,
    )


def test_a126_a_legacy_producer_key_still_replays():
    """A pre-1.13 artifact carries the node-prefixed key and must still replay.

    A126 is what made the prefix meaningless, not what made those files unreadable. Without
    the canonicalisation every archived pipeline reports its producer override orphaned on
    first upgrade — the exact bug, re-entering through the fix for it.
    """
    from mendel_resolver.replay import ReplayResolver

    same = ["nf-core/minimap2/align@2.28.0", "nf-core/star/align@1.11.0"]
    resolver = ReplayResolver([_legacy_producer_record(same)])

    resolution = resolver.resolve(_asked_producer(same))

    assert resolution.chosen == "nf-core/star/align@1.11.0"
    assert resolver.replayed == ["producer:alignment.bam"]
    assert resolver.orphaned == []


def test_a126_a_legacy_record_narrowed_by_a125_goes_stale_rather_than_orphaned():
    """Where A125 narrowed the offered set, the recorded answer is re-asked — and *said*.

    An interaction between this plan's own two fixes, found by testing it rather than by
    reasoning about it. Before A125 a producer record listed **every** candidate; after it,
    only those that tied. So a legacy record's candidate list genuinely differs and
    `_still_applies` rejects it.

    That rejection is correct: the question really did change, and replaying an answer
    chosen from a wider set would assert a decision between options that were never offered.
    What matters is that it lands in `stale_overrides` — "a person's answer was thrown away,
    here it is" — rather than in `orphaned`, which claims the edit applied to nothing. The
    honest report was the whole point of A126.
    """
    from mendel_resolver.replay import ReplayResolver

    before_a125 = [
        "nf-core/hisat2/align@2.2.2",
        "nf-core/minimap2/align@2.28.0",
        "nf-core/samtools/sort@1.21.0",
        "nf-core/star/align@1.11.0",
    ]
    after_a125 = ["nf-core/minimap2/align@2.28.0", "nf-core/star/align@1.11.0"]
    resolver = ReplayResolver([_legacy_producer_record(before_a125)])

    resolver.resolve(_asked_producer(after_a125))

    assert resolver.stale_overrides == ["producer:alignment.bam"]
    assert resolver.orphaned == []
    assert resolver.replayed == []


def _rule_layer(tmp_path: Path, body: str) -> Path:
    layer = tmp_path / "rules-layer"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules" / "probe.yml").write_text(body)
    (layer / "registry.yml").write_text('name: rules-layer\nversion: "0"\n')
    return layer


COMPUTED = """version: 1
decisions:
  - decides: {param: seq_platform}
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {}, then: "read_length-1"}
"""


def test_a118_a_computed_then_is_refused_at_load(tmp_path):
    """A118 — it loaded, resolved at tier 3, carried a real citation, and was not flagged.

    `then: "read_length - 1"` was refused, but only by `MD0201` — a *shell-injection*
    character class that happens to exclude spaces. Removing them was enough to reach the
    tool: `ext.args2 = '--sjdbOverhang read_length-1'`, tier 3, cited to Dobin et al., absent
    from the review list. STAR received the literal string.
    """
    from mendel_resolver import layers
    from mendel_resolver.rules import RuleValidationError

    registry_root = Path(__file__).parent.parent / "registry"
    with pytest.raises(RuleValidationError) as caught:
        layers.load([registry_root, _rule_layer(tmp_path, COMPUTED)])

    assert "MD0300" in str(caught.value)
    assert "read_length-1" in str(caught.value)


def test_a118_a_literal_then_still_loads(tmp_path):
    """The check must have real negatives. A check that can only pass is not a check."""
    from mendel_resolver import layers

    registry_root = Path(__file__).parent.parent / "registry"
    body = COMPUTED.replace('"read_length-1"', "illumina")
    assert layers.load([registry_root, _rule_layer(tmp_path, body)]) is not None


def test_a118_a_value_that_merely_contains_a_measurement_name_still_loads(tmp_path):
    """`paired-end` is not arithmetic, and `paired` is a declared measurement.

    A substring check would refuse this. The rule is that a measurement has to sit next to an
    operator *and a number* — that is what makes a value an expression rather than a word with
    a hyphen in it.
    """
    from mendel_resolver import layers

    registry_root = Path(__file__).parent.parent / "registry"
    body = COMPUTED.replace('"read_length-1"', '"paired-end"')
    assert layers.load([registry_root, _rule_layer(tmp_path, body)]) is not None


def _spine_with_read_length(read_length: int):
    """Build the shipped spine at a given read length, so the aligner rule picks a row."""
    from comeni_core.pipeline import Pipeline
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    loaded = layers.load(Path(__file__).parent.parent / "registry")
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile(
            {"read_length": read_length, "strandedness": "reverse"}
        ),
    )
    ir = resolve(
        goal, loaded.registry, loaded.rules, loaded.measurements, vocabulary=loaded.vocabulary
    )
    return Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal
    )


def test_a79_the_shipped_registry_does_not_cite_the_wrong_paper():
    """A79 — reachable by changing one number in `examples/rnaseq-goal.yml`.

    `Pin.because()` was `row.cite or decision.cite or row.because or decision.because` under a
    docstring claiming *"row before block"*. Two bugs in one line: the precedence is
    cite-first, and a **block** `cite` justifies the decision *axis* — "read length determines
    which aligner is appropriate", for which Dobin et al. is fair — while being printed as the
    reason for a **row**. So the shipped registry said HISAT2 was chosen because of the paper
    describing STAR.
    """
    hisat2 = next(s for s in _spine_with_read_length(50).steps if s.id == "hisat2_align")

    assert "Dobin" not in hisat2.why.reason, hisat2.why.reason
    assert "Kim" in hisat2.why.reason, "HISAT2's own paper is Kim et al. 2019"


def test_a107_authoring_a_citation_does_not_delete_the_sentence():
    """A107 — the same function from the other end, found by a different reviewer.

    A `cite` shadowed a `because`, so the registry's only plain-English explanation of its
    only tier-3 decision never reached the artifact. A reader got a DOI where a sentence
    belonged.
    """
    star = next(s for s in _spine_with_read_length(150).steps if s.id == "star_align")

    assert "read length" in star.why.axis_reason.lower(), star.why.axis_reason
    assert star.why.reason and star.why.reason != star.why.axis_reason
    assert "seed" in star.why.reason.lower() or "long read" in star.why.reason.lower()


def test_a78_a_rule_row_that_justifies_nothing_is_refused(tmp_path):
    """A78 — it loaded, fired, and emitted a reason ending in a bare colon."""
    from mendel_resolver import layers
    from mendel_resolver.rules import RuleValidationError

    body = """version: 1
decisions:
  - decides: {param: seq_platform}
    rows:
      - {when: {}, then: illumina}
"""
    with pytest.raises(RuleValidationError) as caught:
        layers.load([Path(__file__).parent.parent / "registry", _rule_layer(tmp_path, body)])
    assert "MD0301" in str(caught.value)


def _mapq_overlay(tmp_path: Path) -> Path:
    """A laboratory that discards reads below MAPQ 30, and says why it does.

    Shares featureCounts' module key, so it *displaces* the base contract rather than tying
    with it — invariant 11. Written out in full rather than patched from the base file,
    because `extra="forbid"` makes a clever textual edit fail as a parse error that reads
    like the finding.
    """
    layer = tmp_path / "acme-lab"
    (layer / "contracts" / "nf-core").mkdir(parents=True)
    base = (Path(__file__).parent.parent / "registry" / "contracts" / "nf-core"
            / "subread-featurecounts.yml").read_text()
    body = base.replace("    default: 0", "    default: 30").replace(
        "featureCounts' own documented default",
        "lab SOP BIOINF-014",
    )
    (layer / "contracts" / "nf-core" / "subread-featurecounts.yml").write_text(body)
    (layer / "registry.yml").write_text('name: acme-lab\nversion: "0"\n')
    return layer


def _min_mqs_why(*roots):
    from comeni_core.pipeline import Pipeline
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    loaded = layers.load(list(roots))
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    ir = resolve(
        goal, loaded.registry, loaded.rules, loaded.measurements, vocabulary=loaded.vocabulary
    )
    pipeline = Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal
    )
    step = next(s for s in pipeline.steps if s.id == "subread_featurecounts")
    return next(s for s in step.settings if s.name == "min_mqs")


def test_a76_an_overlay_default_is_distinguishable_from_the_base_default(tmp_path):
    """A76, critical — value 0 and value 30 produced a **byte-identical** `why:`.

    Raising featureCounts' `-Q` from 0 to 30 discards every read below mapping quality 30.
    That is a real change to which reads are counted, and the record said exactly the same
    thing before and after: `tier: 2 / source: resolver / reason: contract default for
    min_mqs`, `from_layer: null` — while the step above it correctly attributed its layer.

    Tier 2 is defined as *"a documented default exists"* and the design had nowhere to put
    the document: the overlay author's justification was a YAML comment, dropped at parse.
    """
    registry_root = Path(__file__).parent.parent / "registry"

    base = _min_mqs_why(registry_root)
    lab = _min_mqs_why(registry_root, _mapq_overlay(tmp_path))

    assert base.value == 0 and lab.value == 30
    assert base.why != lab.why, "a different value with an identical justification is A76"
    assert lab.why.from_layer == "acme-lab", "tier 2 must say which layer documented it"
    assert "SOP" in lab.why.reason
    assert base.why.reason != "contract default for min_mqs", (
        "a reason naming the field it explains is circular — it says who, not why"
    )


def test_a128_a_priority_win_says_why_the_registry_ranks_it_there(tmp_path):
    """A128 — `priority` is a bare integer and the selection said only what it did.

    *"registry priority 10, over nf-core/hisat2/align@2.2.2"* states the mechanism, not the
    reason. Tier 2 promises "a documented default exists", and the document was a YAML
    comment the loader discards — A76's exact shape, one field over.

    Reached by giving the goal no `read_length`, so the tier-3 rule cannot fire and priority
    is what decides.
    """
    ir = _aligner_ir(Path(__file__).parent.parent / "registry")
    node = next(n for n in ir.nodes if n.id == "star_align")

    assert node.selection.tier is Tier.CONVENTION
    assert "priority 10" in node.selection.reason, "the mechanism is still worth stating"
    assert "nf-core/rnaseq" in node.selection.axis_reason, (
        "and now the reason the registry ranks it there"
    )


def test_a91_a_positional_parameter_reaches_the_call_and_nothing_else(tmp_path):
    """A91, critical — one call carrying **two values of the same name, disagreeing**.

    `Via` had three members and none emitted into a call position, so three of ten vendored
    modules took a bare `val` that no route could reach. Routing STAR's own
    `star_ignore_sjdbgtf` the only way the design permitted — `via: meta` — produced:

        STAR_ALIGN((TRIMGALORE.out.reads).map { it -> [ it[0] + [star_ignore_sjdbgtf: true] ]
                   + it[1..-1] }, STAR_GENOMEGENERATE.out.index, ch_annotation_gtf, false)

    The documented, tier-4, human-answered value landed in `meta`, where `main.nf:47` never
    looks. The one STAR reads is the trailing `false`. `pipeline.yml` said the GTF was being
    ignored; the pipeline used it.
    """
    from comeni_core.pipeline import Pipeline
    from mendel_compiler.emit import emit
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput, ParamOverride
    from mendel_resolver.resolve import resolve

    root = Path(__file__).parent.parent
    loaded = layers.load(root / "registry")
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={
            "required_states": {"counts.matrix": ["gene_level"]},
            "params": [ParamOverride(name="star_ignore_sjdbgtf", value=True)],
        },
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    ir = resolve(
        goal, loaded.registry, loaded.rules, loaded.measurements, vocabulary=loaded.vocabulary
    )
    pipeline = Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal
    )
    call = next(
        line for line in emit(pipeline).splitlines() if "STAR_ALIGN(" in line
    )

    assert call.count("star_ignore_sjdbgtf") == 0, (
        "it is positional; the module reads it by position and no name is emitted"
    )
    assert call.rstrip().endswith("true)"), call


def test_a91_a_meta_route_to_a_key_the_module_never_reads_is_refused():
    """The other half of A91: the route that let it hide.

    `MD0108` exists to refuse a route the module does not read, and gated on
    `via is not Via.EXT` — its own docstring conceded meta and directive were unchecked. So
    routing a parameter to `meta` produced a value STAR never looks at, no diagnostic fired,
    and the artifact recorded a documented, human-answered decision that reached nothing.
    """
    from mendel_compiler import conformance
    from mendel_resolver import layers

    root = Path(__file__).parent.parent
    loaded = layers.load(root / "registry")
    contract = loaded.registry.get("nf-core/star/align@1.11.0")
    # Reroute the positional parameter to `meta`, which is exactly what the audit did and
    # what nothing refused.
    # `model_validate` rather than `model_copy`: the latter skips validation and leaves
    # `via` as the *string* "meta", which `is Via.META` then misses — A62's shape, and it
    # would have made this test pass for the wrong reason had the check used `==`.
    raw = contract.model_dump()
    for entry in raw["params"]:
        if entry["name"] == "star_ignore_sjdbgtf":
            entry.update(via="meta", key=None, template=None)
    rerouted = type(contract).model_validate(raw)
    registry = loaded.registry
    registry.contracts[contract.id] = rerouted

    # `module_root` is the vendor directory, not the repo root: `module_path` joins it with
    # `nf_include`, which is where a module lands in the *generated* pipeline.
    found = conformance.check(registry, root / "vendor")
    codes = {(d.code, d.where) for d in found}

    assert any(
        code == "MD0108" and "star_ignore_sjdbgtf" in where for code, where in codes
    ), codes
