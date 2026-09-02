"""A5, A15, A23, A24, A25, A35 and A76 — an overlay that replaces something says so.

One test per finding, named for it — the question a reader has is *is A9 still
closed?*, and the test name is the answer. The 2026-08-06 audit and the rounds after
it numbered every finding; `docs/notes/audits/` records how each was reproduced.
"""

from pathlib import Path

import pytest
from support.audit import _declared, _resolve_stacked_from, _stacked
from support.paths import ROOT


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
    from comeni_core.declared.layer import layer_name
    from comeni_core.goal.asked import Goal
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    base, lab = _stacked(tmp_path)
    (base / "tools" / "nf-core" / "samtools" / "sort/contract.yml").unlink()
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


def _overlay_measurement(lab: Path) -> None:
    """A lab overlay replacing `strandedness` with an inverted `meta_values` translation.

    Chosen because it is the measurement `tests/test_counts.py` asserts on: this file is
    what puts `strandedness: reverse` into the emitted `meta` map, and an overlay flipping
    the translation changes what featureCounts is told about a library it never saw.
    """
    (lab / "measurements").mkdir(parents=True, exist_ok=True)
    (lab / "measurements" / "strandedness.yml").write_text(
        _declared(lab / "measurements" / "strandedness.yml", "kind: enum\n"
        "values: [forward, reverse, unstranded]\n"
        "description: 'this lab calls reverse forward'\n"
        "describes: fastq.reads\n"
        "meta_key: strandedness\n"
        "meta_values:\n"
        "  - {when: reverse, then: forward}\n")
    )


def test_a23_an_overlay_measurement_says_so(tmp_path):
    """A23 — a measurement overlay changed the emitted `meta` map and reported nothing.

    `MeasurementRegistry.load` was last-wins on `found[measurement_id]` with no layer names
    to record against, so the strandedness a module is handed could be flipped by an
    installed overlay with nothing in the build output, the IR or the bundle to say a lower
    layer had ever declared it. Invariant 11's last line is the one this breaks: *never let
    an installed overlay reroute a pipeline silently.*
    """
    from comeni_core.declared.layered import DeclaredKind
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
    from comeni_core.declared.layered import DeclaredKind
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "vocabularies").mkdir(parents=True, exist_ok=True)
    (lab / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(
            lab / "vocabularies" / "fastq.reads.yml",
            "states: [trimmed, deduplicated, subsampled]\n"
        "entry_channel: \"Channel.fromFilePairs('/mnt/lab/run7/*_R{1,2}.fastq.gz')\"\n")
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
    from comeni_core.declared.vocabulary import UnknownStateError
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "vocabularies").mkdir(parents=True, exist_ok=True)
    (lab / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(lab / "vocabularies" / "fastq.reads.yml", "states: [phix_removed]\n")
    )

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
    (lab / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(lab / "vocabularies" / "fastq.reads.yml", "add_states: [phix_removed]\n")
    )

    loaded = layers_mod.load([base, lab])

    assert loaded.vocabulary.states_for("fastq.reads") == frozenset(
        {"trimmed", "deduplicated", "subsampled", "phix_removed"}
    )
    # **The TEMPLATE survives, and so does the `param:` beside it.** This asserted
    # `params.input` was in the stored expression, which stopped being true when the entry
    # channel became `params.{param}` — the literal moved to its own field. Both halves are
    # checked now, because an extension dropping `param:` would silently rename `params.input`
    # to `params.reads`, which is A35's exact shape one field along.
    assert "params.{param}" in loaded.vocabulary.entry_channels["fastq.reads"]
    assert loaded.vocabulary.params["fastq.reads"] == "input"
    assert loaded.vocabulary.test_data["fastq.reads"], "the base's test data survives too"


def test_a25_a_shadow_is_a_displacement_like_any_other(tmp_path):
    """A25 — displacement was keyed on a layer *name*, and names collide.

    The lockfile's own docstring says the collision is not exotic: the public layer is
    named `registry`, so a lab stacking it over their own `registry/` hits it on day one.
    `ShadowRecord` is gone; a contract shadow is a `Displacement` like the other three
    kinds, and the IR carries all of them under one field.
    """
    import shutil

    from comeni_core.declared.layered import DeclaredKind
    from mendel_resolver import layers as layers_mod

    base, lab = _stacked(tmp_path)
    (lab / "contracts").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        base / "tools" / "nf-core" / "samtools" / "sort/contract.yml",
        lab / "contracts" / "samtools-sort.yml",
    )
    shadowing = (lab / "contracts" / "samtools-sort.yml").read_text()
    (lab / "contracts" / "samtools-sort.yml").write_text(
        _declared(lab / "contracts" / "samtools-sort.yml", shadowing.replace("@1.21.0", "@1.22.0"))
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


def _mapq_overlay(tmp_path: Path) -> Path:
    """A laboratory that discards reads below MAPQ 30, and says why it does.

    Shares featureCounts' module key, so it *displaces* the base contract rather than tying
    with it — invariant 11. Written out in full rather than patched from the base file,
    because `extra="forbid"` makes a clever textual edit fail as a parse error that reads
    like the finding.
    """
    layer = tmp_path / "acme-lab"
    (layer / "tools" / "nf-core" / "subread").mkdir(parents=True, exist_ok=True)
    base = (
        ROOT
        / "registry/tools/nf-core/subread/featurecounts/contract.yml"
    ).read_text()
    body = base.replace("    default: 0", "    default: 30").replace(
        "featureCounts' own documented default",
        "lab SOP BIOINF-014",
    )
    (layer / "tools" / "nf-core" / "subread" / "featurecounts").mkdir(
        parents=True, exist_ok=True
    )
    (layer / "tools" / "nf-core" / "subread" / "featurecounts/contract.yml").write_text(
        _declared(layer / "tools" / "nf-core" / "subread" / "featurecounts/contract.yml", body)
    )
    (layer / "registry.yml").write_text(
        _declared(
            layer / "registry.yml",
            'name: acme-lab\nversion: "0"\n'))
    return layer


def _min_mqs_why(*roots):
    from comeni_core.artifact.pipeline import Pipeline
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
    registry_root = ROOT / "registry"

    base = _min_mqs_why(registry_root)
    lab = _min_mqs_why(registry_root, _mapq_overlay(tmp_path))

    assert base.value == 0 and lab.value == 30
    assert base.why != lab.why, "a different value with an identical justification is A76"
    assert lab.why.from_layer == "acme-lab", "tier 2 must say which layer documented it"
    assert "SOP" in lab.why.reason
    assert base.why.reason != "contract default for min_mqs", (
        "a reason naming the field it explains is circular — it says who, not why"
    )
