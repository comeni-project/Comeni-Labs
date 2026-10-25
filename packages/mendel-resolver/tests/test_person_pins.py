"""Person-authored producer pins override rules and ambiguities with explicit evidence."""

from pathlib import Path

import pytest
from comeni_core.goal.asked import ProducerPin, Site
from comeni_core.plan.ir import Tier
from comeni_core.plan.tiers import ValueSource
from mendel_resolver.ports import FlagOnlyResolver
from mendel_resolver.resolve import UnknownTypeError, inert_pins

ROOT = Path(__file__).resolve().parents[3]
HISAT2_ALIGN = "nf-core/hisat2/align@2.2.2"


def _node(ir, node_id):
    return next(n for n in ir.nodes if n.id == node_id)


def test_every_step_knows_its_site(resolve_rnaseq):
    star = _node(resolve_rnaseq(), "star_align")
    assert star.site == Site(type_id="alignment.bam", states=star.site.states)


def test_a_pin_equal_to_the_engines_pick_changes_nothing(resolve_rnaseq):
    """Review Focus 2."""
    plain = resolve_rnaseq()
    star = _node(plain, "star_align")
    pinned = resolve_rnaseq(pins=[ProducerPin(site=star.site, contract=star.contract_id)])
    assert pinned.model_dump(mode="json") == plain.model_dump(mode="json")


def test_a_pin_against_the_rule_is_tier_four_and_yours(resolve_rnaseq):
    plain = resolve_rnaseq()
    star = _node(plain, "star_align")
    assert star.selection.tier is Tier.DATA_PROFILED
    ir = resolve_rnaseq(pins=[ProducerPin(site=star.site, contract=HISAT2_ALIGN)])
    ids = {n.id for n in ir.nodes}
    assert {"hisat2_align", "hisat2_build"} <= ids
    assert not ids & {"star_align", "star_genomegenerate"}
    aligner = _node(ir, "hisat2_align")
    assert aligner.selection.tier is Tier.AMBIGUOUS
    assert aligner.selection.source is ValueSource.HUMAN
    assert star.contract_id in aligner.selection.reason, "the engine's pick is kept beside it"
    [record] = [d for d in ir.decisions if getattr(d, "human_override", None) == HISAT2_ALIGN]
    assert record.chosen == HISAT2_ALIGN


def test_a_pin_at_an_open_site_asks_no_resolver(resolve_rnaseq):
    """Review Focus 3: without a read length the aligner site is a question; the pin answers
    it, the resolver is never asked about it, and exactly one record is written."""
    asked = []

    class Watching(FlagOnlyResolver):
        def resolve(self, ambiguity):
            asked.append(ambiguity.subject)
            return super().resolve(ambiguity)

    star = _node(resolve_rnaseq(read_length=False), "star_align")
    subject = f"producer:{star.site.type_id}"
    ir = resolve_rnaseq(
        read_length=False,
        resolver=Watching(),
        pins=[ProducerPin(site=star.site, contract=HISAT2_ALIGN)],
    )
    assert subject not in asked
    records = [d for d in ir.decisions if d.subject == subject]
    assert len(records) == 1 and records[0].human_override == HISAT2_ALIGN
    assert "read_length" in records[0].unknown


def test_a_pin_that_matches_no_site_changes_nothing_and_is_named(resolve_rnaseq):
    """Final review I1: a pin that applies nowhere leaves the pipeline as it was — and is
    reported by `inert_pins`, never dropped in silence (nothing was guessed silently)."""
    ghost = ProducerPin(site=Site(type_id="qc.report"), contract="x/y@1")
    ir = resolve_rnaseq(pins=[ghost])
    assert ir.nodes == resolve_rnaseq().nodes
    assert inert_pins(ir, [ghost]) == [ghost]


def test_a_pin_that_applies_is_not_inert(resolve_rnaseq):
    star = _node(resolve_rnaseq(), "star_align")
    for contract in (HISAT2_ALIGN, star.contract_id):     # against the engine, and agreeing
        pin = ProducerPin(site=star.site, contract=contract)
        assert inert_pins(resolve_rnaseq(pins=[pin]), [pin]) == []


def test_a_pin_must_name_a_declared_type_and_states(resolve_rnaseq):
    """Final review I1: a pin's site is held to the vocabulary like every type a goal names
    (A29, invariant 7)."""
    with pytest.raises(UnknownTypeError):
        resolve_rnaseq(pins=[ProducerPin(site=Site(type_id="made.up"), contract=HISAT2_ALIGN)])
    with pytest.raises(ValueError, match="no_such_state"):
        resolve_rnaseq(pins=[ProducerPin(
            site=Site(type_id="alignment.bam", states=frozenset({"no_such_state"})),
            contract=HISAT2_ALIGN,
        )])
