"""Who settled what, kept per decision rather than per session.

**§1.8, and the failure it exists to prevent is one word wide.** `ir_of` stamps every choice with
one author — the whole-draft `by` — so a spawned pipeline that a person later edits in one place
becomes, in `pipeline.yml`, a pipeline a person drew. The resolver's reasons are overwritten, the
tiers become 4, and the artifact's own claim (*nothing was guessed silently*) is inverted: it now
says a human decided things no human ever saw.

The test that matters is the mixed one. A pipeline with three steps settled three different ways
must come out of `Pipeline.of` saying so, step by step.
"""

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import (
    DraftEdge,
    DraftGraph,
    DraftNode,
    DraftParam,
    DraftProvenance,
    NodeSettled,
    ParamSettled,
    Settled,
)
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_resolver.materialise import goal_of, ir_of

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"

MODEL = "claude-opus-5"


def _graph() -> DraftGraph:
    """The spine, with a setting somebody typed on the aligner."""
    return DraftGraph(
        nodes=[
            DraftNode(id="index", contract_id=GENOME),
            DraftNode(id="align", contract_id=STAR),
            DraftNode(id="sort", contract_id=SORT),
            DraftNode(
                id="counts",
                contract_id=COUNTS,
                params=[DraftParam(name="min_mqs", value=10, why="low-MAPQ reads are noise here")],
            ),
        ],
        edges=[
            DraftEdge(from_node="index", from_port="index", to_node="align", to_port="index"),
            DraftEdge(from_node="align", from_port="bam", to_node="sort", to_port="bam"),
            DraftEdge(from_node="sort", from_port="bam", to_node="counts", to_port="bam"),
        ],
    )


def _mixed() -> DraftProvenance:
    """Three steps, three authors — the shape a Spawn session followed by one manual edit makes.

    `index` was settled by the resolver, structurally: nothing else produces a STAR index.
    `align` was chosen by a model from real candidates, at tier 4 and flagged.
    `sort` carries nothing, which is a person drawing it by hand — the default this file's whole
    argument is that it must stop being applied to everything.
    """
    return DraftProvenance(
        nodes=[
            NodeSettled(
                node="index",
                selection=Settled(
                    source=ValueSource.RESOLVER,
                    tier=Tier.STRUCTURAL,
                    reason="the only contract producing genome.index",
                    axis_reason="which contract fills this step",
                ),
                presence=Settled(
                    source=ValueSource.RESOLVER,
                    tier=Tier.STRUCTURAL,
                    reason="star/align.reads requires a genome index",
                    axis_reason="whether this step exists at all",
                ),
            ),
            NodeSettled(
                node="align",
                selection=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="STAR over HISAT2 for a splice-aware count matrix",
                    axis_reason="which contract fills this step",
                    by=MODEL,
                ),
            ),
        ],
        params=[
            ParamSettled(
                key="counts.min_mqs",
                settled=Settled(
                    source=ValueSource.HUMAN,
                    tier=Tier.AMBIGUOUS,
                    reason="low-MAPQ reads are noise here",
                    axis_reason="the minimum mapping quality to count",
                ),
            )
        ],
    )


# ── the mixed pipeline ────────────────────────────────────────────────────────────────────


def test_three_steps_settled_three_ways_say_so_in_the_artifact(stack):
    """**The test Task 4 asks for first.** One resolver-settled step, one model-selected, one
    drawn by a person, and all three sources, tiers and reasons survive into `pipeline.yml`."""
    ir = ir_of(_graph(), stack, provenance=_mixed())
    pipeline = Pipeline.of(
        ir, stack.registry, stack.vocabulary, stack.measurements, stack.paths,
        goal=goal_of(_graph(), stack),
    )
    steps = {step.id: step for step in pipeline.steps}

    assert steps["index"].why.source == ValueSource.RESOLVER
    assert steps["index"].why.tier == Tier.STRUCTURAL
    assert "only contract producing" in steps["index"].why.reason

    assert steps["align"].why.source == ValueSource.MODEL
    assert steps["align"].why.tier == Tier.AMBIGUOUS
    assert "STAR over HISAT2" in steps["align"].why.reason

    assert steps["sort"].why.source == ValueSource.HUMAN
    assert steps["sort"].why.tier == Tier.AMBIGUOUS


def test_the_model_that_chose_a_step_is_named(stack):
    """A130 from the third direction. `model_override_by` is what distinguishes a pipeline an
    agent assembled from one a person drew, and a sidecar that recorded *model* without recording
    *which* would make the record unauditable."""
    ir = ir_of(_graph(), stack, provenance=_mixed())
    producer = next(d for d in ir.decisions if d.key == "producer:align")
    assert producer.model_override == STAR
    assert producer.model_override_by == MODEL
    assert producer.human_override is None, "a model's choice must not read as a person's"


def test_a_resolver_settled_step_is_backed_by_no_override(stack):
    """The half that MD0220 cares about. A value claiming `source: human` must be backed by a
    person answering it; a value claiming `resolver` must be backed by **neither** override, or
    the artifact says a human cleared a review that nobody looked at."""
    ir = ir_of(_graph(), stack, provenance=_mixed())
    producer = next(d for d in ir.decisions if d.key == "producer:index")
    assert producer.human_override is None
    assert producer.model_override is None


def test_a_persons_setting_keeps_its_own_words(stack):
    """`counts.strandedness` was typed by a person with a reason, and the reason is theirs.
    A77 and A111: an empty reason is left empty rather than replaced with boilerplate, and a
    given one is never replaced at all."""
    ir = ir_of(_graph(), stack, provenance=_mixed())
    node = next(n for n in ir.nodes if n.id == "counts")
    value = node.param("min_mqs")
    assert value.source == ValueSource.HUMAN
    assert value.reason == "low-MAPQ reads are noise here"


# ── the compatibility promise ─────────────────────────────────────────────────────────────


def test_no_sidecar_is_byte_for_byte_what_it_always_was(stack):
    """§1.8: *`None` must preserve today's manual builder behaviour byte for byte.*

    The manual builder is shipped and its drafts have no sidecar. If an absent one changed one
    reason string, every existing draft would emit differently the next time somebody opened it —
    and determinism is a test in this repository, not an aspiration.
    """
    assert (
        ir_of(_graph(), stack).model_dump_json()
        == ir_of(_graph(), stack, provenance=None).model_dump_json()
    )


def test_an_empty_sidecar_is_the_same_as_no_sidecar(stack):
    """A draft that has been through the diff and retained nothing is not a different pipeline
    from one that was never authored. `DraftProvenance()` is the identity, and if it were not,
    every deletion would silently re-author the rest of the graph."""
    assert (
        ir_of(_graph(), stack).model_dump_json()
        == ir_of(_graph(), stack, provenance=DraftProvenance()).model_dump_json()
    )


def test_the_whole_draft_by_still_produces_the_old_bytes(stack):
    """Task 4 keeps `by` until every caller has moved, and this is the proof it still works.

    A model that drew the *whole* graph is what `by` has always meant, and expressing it through
    the sidecar must give the same artifact — otherwise the compatibility wrapper is a second
    behaviour wearing the old name.
    """
    every_node = DraftProvenance(
        nodes=[
            NodeSettled(
                node=node.id,
                selection=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="drawn by a model in the builder rather than resolved from a goal",
                    axis_reason="which contract fills this step",
                    by=MODEL,
                ),
                presence=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="this step exists because it was drawn by a model",
                    axis_reason="whether this step exists at all",
                    by=MODEL,
                ),
            )
            for node in _graph().nodes
        ],
        params=[
            ParamSettled(
                key="counts.min_mqs",
                settled=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="low-MAPQ reads are noise here",
                    axis_reason="min_mqs is a declared setting",
                    by=MODEL,
                ),
            )
        ],
    )
    through_by = ir_of(_graph(), stack, by=MODEL)
    through_sidecar = ir_of(_graph(), stack, provenance=every_node)

    assert [n.selection.source for n in through_by.nodes] == [
        n.selection.source for n in through_sidecar.nodes
    ]
    assert [n.selection.reason for n in through_by.nodes] == [
        n.selection.reason for n in through_sidecar.nodes
    ]
    producer_by = next(d for d in through_by.decisions if d.key == "producer:align")
    producer_side = next(d for d in through_sidecar.decisions if d.key == "producer:align")
    assert producer_by.model_override_by == producer_side.model_override_by == MODEL


def test_a_sidecar_entry_for_a_node_that_is_gone_is_ignored(stack):
    """A stale entry must not resurrect a step. The service drops them on edit, and this is the
    belt: `ir_of` iterates the *graph*, so an orphaned entry can only be ignored."""
    stale = DraftProvenance(
        nodes=[
            NodeSettled(
                node="trim",
                selection=Settled(
                    source=ValueSource.RESOLVER, tier=Tier.CONVENTION, reason="deleted step"
                ),
            )
        ]
    )
    ir = ir_of(_graph(), stack, provenance=stale)
    assert {n.id for n in ir.nodes} == {"index", "align", "sort", "counts"}


def test_a_model_answered_setting_is_not_attributed_to_a_person(stack):
    """**The discriminating test, and the reason it exists.**

    `test_a_persons_setting_keeps_its_own_words` passes whether or not the sidecar is read: the
    fallback for a typed value is already `HUMAN` with the typist's reason, so a param path that
    ignored provenance entirely would show green. That is a guard passing on the code it was
    written to reject, which is W2's lesson.

    This is the case the two answers differ on: a Spawn session where the **model** answered a
    tier-4 setting, on a draft nobody has drawn by hand. The whole-draft `by` is empty, so the
    fallback says a person typed it; only the sidecar can say otherwise.
    """
    settled = DraftProvenance(
        params=[
            ParamSettled(
                key="counts.min_mqs",
                settled=Settled(
                    source=ValueSource.MODEL,
                    tier=Tier.AMBIGUOUS,
                    reason="10 is nf-core's own default for this assay",
                    axis_reason="the minimum mapping quality to count",
                    by=MODEL,
                ),
            )
        ]
    )
    ir = ir_of(_graph(), stack, provenance=settled)

    value = next(n for n in ir.nodes if n.id == "counts").param("min_mqs")
    assert value.source == ValueSource.MODEL, "a model's answer read as a person's"
    assert value.reason == "10 is nf-core's own default for this assay"

    decision = next(d for d in ir.decisions if d.key == "counts.min_mqs")
    assert decision.model_override == 10
    assert decision.model_override_by == MODEL
    assert decision.human_override is None


def test_a_resolver_settled_setting_carries_no_override_either(stack):
    """MD0220's mirror on the setting axis: a value the resolver settled must not be handed a
    human override just because the builder stamps one on everything it can see."""
    settled = DraftProvenance(
        params=[
            ParamSettled(
                key="counts.min_mqs",
                settled=Settled(
                    source=ValueSource.RESOLVER,
                    tier=Tier.CONVENTION,
                    reason="the documented default",
                    axis_reason="the minimum mapping quality to count",
                ),
            )
        ]
    )
    ir = ir_of(_graph(), stack, provenance=settled)

    value = next(n for n in ir.nodes if n.id == "counts").param("min_mqs")
    assert value.source == ValueSource.RESOLVER
    assert value.tier == Tier.CONVENTION

    decision = next(d for d in ir.decisions if d.key == "counts.min_mqs")
    assert decision.human_override is None
    assert decision.model_override is None
