"""A2, A3, A6, A20, A27, A29 and A34 — what may not cross into an artifact or out of a door.

One test per finding, named for it — the question a reader has is *is A9 still
closed?*, and the test name is the answer. The 2026-08-06 audit and the rounds after
it numbered every finding; `docs/notes/audits/` records how each was reproduced.
"""

from pathlib import Path

import pytest
from comeni_core.plan.tiers import Tier
from pydantic import ValidationError
from support.audit import _declared, _pipe, _published_pipeline
from support.paths import ROOT


def test_a2_resolve_refuses_an_unvalidated_profile():
    """A2 — invariant 15 lived in one CLI branch, and `upgrade` did not pass through it.

    `Goal.model_validate` builds a `DataProfile` without a registry, so it cannot check
    what is declared. `MeasurementRegistry.profile()` is the only validating constructor,
    and `resolve()` never routed through it — the check lived in `mendel build`'s own
    re-route, which `mendel upgrade` skips because it takes its goal from a bundle.
    """
    from comeni_core.declared.measurement import UnknownMeasurementError
    from comeni_core.goal.asked import Goal
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


def test_a2_upgrade_refuses_a_pipeline_carrying_an_undeclared_measurement(tmp_path):
    """The reachable route, end to end: a `pipeline.yml` is a *downloaded* artifact.

    `mendel upgrade` reads its goal from that file rather than from a `--goal`, so it was the
    one verb reading something a stranger wrote and the one verb with no check. Reproduced
    in the audit as exit 0 with `sample_name: PATIENT-00417` in the emitted IR, and
    re-published verbatim by any following `mendel publish`.
    """
    import yaml
    from mendel_compiler.cli import main

    root = ROOT
    published = _published_pipeline(tmp_path, root)

    doc = yaml.safe_load(published.read_text())
    doc["goal"]["profile"]["measurements"].append(
        {"measurement": "sample_name", "value": "PATIENT-00417", "source": "goal", "by": None}
    )
    published.write_text(_declared(published, yaml.safe_dump(doc, sort_keys=False)))

    out = tmp_path / "upgraded"
    assert main(["upgrade", str(published), "--out", str(out), "--root", str(root)]) != 0
    assert not (out / "pipeline.yml").exists(), "a refused upgrade must emit nothing"


def test_a2_a_declared_profile_still_resolves():
    """The refusal must not cost the normal case."""
    import yaml
    from comeni_core.goal.asked import Goal
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

    from comeni_core.spell.marks import MeasurementId, ParamValue
    from guards.test_egress import _mentions_binary, _mentions_mapping

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
    from comeni_core.plan.decision import ParamDecision

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
    from comeni_core.plan.decision import ParamDecision

    record = ParamDecision(
        key="k", subject="s", chosen=None, reason="r", resolved_by="human",
        human_override=value,
    )
    assert record.human_override == value


def test_a3_a_path_cannot_enter_through_a_goal_param_override():
    """The same value, through the door a person actually types into."""
    from comeni_core.goal.asked import Goal

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
    from comeni_core.plan.decision import ParamDecision, SourceDecision

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
    from comeni_core.declared.contract import ModuleContract
    from comeni_core.declared.vocabulary import Vocabulary

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "alignment.bam.yml").write_text(
        _declared(tmp_path / "vocabularies" / "alignment.bam.yml", "states: []\n")
    )
    vocab = Vocabulary.load(tmp_path)
    bad = tmp_path / "evil.yml"
    bad.write_text(
        _declared(bad, "id: lab/evil@1.0.0\n"
        "nf_process: \"LAB_SORT }\\nprintln 'OWNED'\\nprocess X {\"\n"
        "nf_include: modules/lab/evil/main\n"
        "consumes: []\n"
        "produces: [{name: bam, type_id: alignment.bam, state: []}]\n"
        "provenance: {source: lab, drafted_by: l, approved_by: l, approved_at: '2026-08-07'}\n")
    )

    with pytest.raises(ValidationError, match="nf_process"):
        ModuleContract.load(bad, vocab)


def test_a34_an_include_path_cannot_leave_the_pipeline(tmp_path):
    """The same kind, never tried. `nf_include` becomes `from './<path>'`."""
    from comeni_core.declared.contract import ModuleContract
    from comeni_core.declared.vocabulary import Vocabulary

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "alignment.bam.yml").write_text(
        _declared(tmp_path / "vocabularies" / "alignment.bam.yml", "states: []\n")
    )
    vocab = Vocabulary.load(tmp_path)
    bad = tmp_path / "escape.yml"
    bad.write_text(
        _declared(bad, "id: lab/escape@1.0.0\n"
        "nf_process: LAB_ESCAPE\n"
        "nf_include: ../../../etc/passwd\n"
        "consumes: []\n"
        "produces: [{name: bam, type_id: alignment.bam, state: []}]\n"
        "provenance: {source: lab, drafted_by: l, approved_by: l, approved_at: '2026-08-07'}\n")
    )

    with pytest.raises(ValidationError, match="nf_include"):
        ModuleContract.load(bad, vocab)


def test_a34_a_vocabulary_type_id_is_a_filename_and_filenames_can_be_anything(tmp_path):
    """A type id is a filename stem, and Linux filenames may contain newlines.

    It feeds `_channel_name()`, which replaces `.` and `-` and nothing else, so the id
    reaches an assignment target in the emitted workflow.
    """
    from comeni_core.declared.vocabulary import Vocabulary

    (tmp_path / "vocabularies").mkdir()
    (tmp_path / "vocabularies" / "evil\nch_x = 1.yml").write_text(
        _declared(tmp_path / "vocabularies" / "evil\nch_x = 1.yml", "states: []\n")
    )

    with pytest.raises(ValueError, match="evil"):
        Vocabulary.load(tmp_path)


def test_a27_a_reason_that_reaches_a_generated_file_is_one_line():
    """A27 — prose was interpolated into `// <reason>` and the second line was Groovy."""
    from comeni_core.plan.ir import ResolvedValue, Tier

    with pytest.raises(ValidationError):
        ResolvedValue(value=1, tier=Tier.CONVENTION, reason="fine\nprintln 'OWNED'")


def test_a27_a_gate_message_may_still_be_many_lines():
    """The regression guard for the split: Nextflow's stderr is inherently multi-line."""
    from comeni_core.artifact.egress import GateFailure

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
    from comeni_core.artifact.pipeline import Pipeline, Setting, Step, Why
    from comeni_core.plan.tiers import ValueSource
    from comeni_core.spell.routes import Via
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
    from comeni_core.plan.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
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
    from comeni_core.artifact.pipeline import Pipeline, Setting, Step, Why
    from comeni_core.plan.tiers import ValueSource
    from comeni_core.spell.routes import Via
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
    from comeni_core.declared.vocabulary import UnknownTypeError
    from comeni_core.goal.asked import Goal
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
    from comeni_core.declared.vocabulary import UnknownTypeError
    from comeni_core.goal.asked import Goal
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
    from comeni_core.declared.vocabulary import UnknownStateError
    from comeni_core.goal.asked import Goal
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
    published.write_text(_declared(published, yaml.safe_dump(doc, sort_keys=False)))

    assert main(["upgrade", str(published), "--out", str(tmp_path / "up"),
                 "--root", "."]) == 2
