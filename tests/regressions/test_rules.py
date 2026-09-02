"""A22, A78, A79, A107 and A118 — a rule row justifies itself, and cites the right paper.

One test per finding, named for it — the question a reader has is *is A9 still
closed?*, and the test name is the answer. The 2026-08-06 audit and the rounds after
it numbered every finding; `docs/notes/audits/` records how each was reproduced.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError
from support.audit import _declared, _resolve_stacked_from, _stacked
from support.paths import ROOT


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
        _declared(lab / "rules" / "aligner.yml", "version: 1\n"
        "decisions:\n"
        "  - decides: {effect: implementation, of: alignment}\n"
        "    because: 'this lab has a HISAT2 index and no STAR index'\n"
        "    rows:\n"
        "      - {when: {read_length: '>= 50'}, then: nf-core/hisat2/align@2.2.2}\n"
        "      - {when: {read_length: '< 50'}, then: nf-core/hisat2/align@2.2.2}\n")
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


def _rule_layer(tmp_path: Path, body: str) -> Path:
    layer = tmp_path / "rules-layer"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules" / "probe.yml").write_text(_declared(layer / "rules" / "probe.yml", body))
    (layer / "registry.yml").write_text(
        _declared(
            layer / "registry.yml",
            'name: rules-layer\nversion: "0"\n'))
    return layer


COMPUTED = """version: 1
decisions:
  - decides: {effect: param, of: alignment, name: seq_platform}
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

    registry_root = ROOT / "registry"
    with pytest.raises(RuleValidationError) as caught:
        layers.load([registry_root, _rule_layer(tmp_path, COMPUTED)])

    assert "MD0300" in str(caught.value)
    assert "read_length-1" in str(caught.value)


def test_a118_a_literal_then_still_loads(tmp_path):
    """The check must have real negatives. A check that can only pass is not a check."""
    from mendel_resolver import layers

    registry_root = ROOT / "registry"
    body = COMPUTED.replace('"read_length-1"', "illumina")
    assert layers.load([registry_root, _rule_layer(tmp_path, body)]) is not None


def test_a118_a_value_that_merely_contains_a_measurement_name_still_loads(tmp_path):
    """`paired-end` is not arithmetic, and `paired` is a declared measurement.

    A substring check would refuse this. The rule is that a measurement has to sit next to an
    operator *and a number* — that is what makes a value an expression rather than a word with
    a hyphen in it.
    """
    from mendel_resolver import layers

    registry_root = ROOT / "registry"
    body = COMPUTED.replace('"read_length-1"', '"paired-end"')
    assert layers.load([registry_root, _rule_layer(tmp_path, body)]) is not None


def _spine_with_read_length(read_length: int):
    """Build the shipped spine at a given read length, so the aligner rule picks a row."""
    from comeni_core.artifact.pipeline import Pipeline
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    loaded = layers.load(ROOT / "registry")
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

    # A row testing a premise **positively**, so `MD0313` — the tier-2 citation rule added
    # in Plan 1.15 Task 7 — does not fire first. `when: {}` exits at tier 2 and is refused
    # for a different and more specific reason; this row is genuinely tier 3 and genuinely
    # justifies nothing, which is what A78 was.
    body = """version: 1
decisions:
  - decides: {effect: param, of: alignment, name: seq_platform}
    rows:
      - {when: {read_length: ">= 70"}, then: illumina}
      - {when: {read_length: "< 70"}, then: illumina}
"""
    with pytest.raises(RuleValidationError) as caught:
        layers.load([ROOT / "registry", _rule_layer(tmp_path, body)])
    assert "MD0301" in str(caught.value)
