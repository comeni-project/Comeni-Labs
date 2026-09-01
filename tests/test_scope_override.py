"""A channel's scope may differ from its type's default, and saying so is a decision.

Plan 5B phase 4.1's third bullet, which `main`'s own migration note says phase 4 owes: *"a v5
file has no scope on any channel, taking the type's default is a genuinely new decision, and a
decision appearing in a pipeline nobody re-decided is what replay exists to prevent."*

**Whether two GTF ports are fed by one file or by two is not derivable from the drawing.** Both
are legal pipelines and they analyse different experiments — a shared reference annotation, or
one annotation per sample. So a person decides, and invariant 6 says a person's decision is
flagged however confident they were.

**Taking the default records nothing**, and that is the half worth guarding. A `Why` for a
choice nobody made would owe `mendel explain` an answer to a question that was never open, and
`upgrade` would replay it forever.
"""

import pathlib

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftChannel, DraftEdge, DraftGraph, DraftNode
from comeni_core.plan.tiers import Scope, Tier, ValueSource
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of

ROOT = pathlib.Path(__file__).parent.parent

STAR = "nf-core/star/align@1.11.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _graph(*channels: DraftChannel) -> DraftGraph:
    """STAR and featureCounts, which between them consume `annotation.gtf` twice — the pair
    spec §0 is about, and the only place an override is interesting."""
    return DraftGraph(
        nodes=[
            DraftNode(id="align", contract_id=STAR),
            DraftNode(id="counts", contract_id=COUNTS),
        ],
        edges=[DraftEdge(from_node="align", from_port="bam", to_node="counts", to_port="bam")],
        channels=list(channels),
    )


def _built(graph: DraftGraph, stack) -> Pipeline:
    return Pipeline.of(
        ir_of(graph, stack), stack.registry, stack.vocabulary, stack.measurements, stack.paths,
        goal=goal_of(graph, stack),
    )


def _gtf(pipeline: Pipeline):
    return next(c for c in pipeline.channels if c.type_id == "annotation.gtf")


def test_the_default_is_taken_and_recorded_as_nothing(stack):
    """**The half that is easy to get wrong.** `annotation.gtf` declares `scope: run`, so the
    channel is run-scoped — and no `Why` appears, because nobody decided anything.

    A `Why` here would put a decision nobody made into the artifact and make `upgrade` replay
    it forever, which is §12.2's failure mode arriving from the other side.
    """
    channel = _gtf(_built(_graph(), stack))
    assert channel.scope is Scope.RUN
    assert channel.why is None


def test_an_override_carries_the_person_s_reason_at_tier_four(stack):
    """The judgement, flagged. Per-sample annotations over a shared one is a different
    analysis, not a different spelling."""
    pipeline = _built(
        _graph(
            DraftChannel(
                ports=("align.gtf",),
                scope="sample",
                why="each biopsy has its own liver-specific annotation",
            )
        ),
        stack,
    )
    split = next(c for c in pipeline.channels if "liver" in (c.why.reason if c.why else ""))

    assert split.scope is Scope.SAMPLE
    assert split.why is not None
    assert split.why.tier is Tier.AMBIGUOUS, "invariant 6 — a person's decision is flagged"
    assert split.why.source is ValueSource.HUMAN
    assert split.why.reason == "each biopsy has its own liver-specific annotation"
    assert "judgement about the experiment" in split.why.axis_reason


def test_an_override_with_no_reason_says_so_rather_than_inventing_one(stack):
    """A77 and A111. Boilerplate would replace what somebody wrote with what the resolver would
    have said — which is how `upgrade` came to overwrite a reviewer's own words with *"selected
    the first of 1 candidates without judgement"*."""
    pipeline = _built(_graph(DraftChannel(ports=("align.gtf",), scope="sample")), stack)
    split = next(c for c in pipeline.channels if c.why is not None)
    assert split.why is not None
    assert split.why.reason == "no reason was given for this channel's scope"


def test_the_override_changes_what_is_emitted(stack):
    """A `Why` that did not reach the Groovy would be provenance for nothing.

    Run-scoped emits `.first()` — a value channel, consumable any number of times. Sample-scoped
    stays a queue, which is what makes the process run per sample.
    """
    shared = emit(_built(_graph(), stack))
    assert ".first()" in next(one for one in shared.splitlines() if "ch_gtf =" in one)

    split = emit(
        _built(_graph(DraftChannel(ports=("align.gtf",), scope="sample")), stack)
    )
    # Two gtf channels now — the override *split* it, which is phase 3's mechanism doing the
    # work: `ch_gtf` is the overridden one and stays a queue, `ch_gtf_2` keeps the type's
    # default and is a value channel. That both appear is the point: a person said these two
    # ports read different files, and the Groovy says so.
    lines = [one for one in split.splitlines() if one.strip().startswith("ch_gtf")]
    assert len(lines) == 2, f"expected the channel to split, got {lines}"
    assert not lines[0].rstrip().endswith(".first()"), (
        f"the overridden channel is still a value channel: {lines[0].strip()}"
    )
    assert lines[1].rstrip().endswith(".first()"), (
        f"the channel that kept its type's default stopped being one: {lines[1].strip()}"
    )


def test_the_override_reaches_the_artifact_on_disk(stack, tmp_path):
    """It has to survive YAML, or `mendel emit` years later reads a pipeline that lost the
    reason it was built the way it was."""
    pipeline = _built(
        _graph(DraftChannel(ports=("align.gtf",), scope="sample", why="per-biopsy")), stack
    )
    again = Pipeline.model_validate_json(pipeline.model_dump_json())
    reasons = [c.why.reason for c in again.channels if c.why is not None]
    assert reasons == ["per-biopsy"]


def test_the_egress_surface_did_not_widen():
    """**The design constraint, as a test.** A scope override is a value somebody settled at a
    tier for a reason — which is what `ResolvedValue` is — so it needed no field of its own.

    The first version gave `IRChannel` a `Scope` and a bare `Line`, and the egress guard refused
    both: a plain `str` on a payload is how a closed vocabulary stops being closed, and the
    `Line` would have been invariant 14's **fifteenth** free-text field.
    """
    from test_egress import FREE_TEXT_FIELDS

    assert len(FREE_TEXT_FIELDS) == 14
