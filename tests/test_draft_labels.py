"""A label is what a person calls a socket, and it reaches nothing.

Plan 5B phase 1.2, spec §5. The operator's constraint was one sentence — *"yes it's a label,
does not change the actual keys"* — and this is that sentence as a test rather than as a
docstring on `DraftLabel`.

**Why it is a guard and not a unit test.** The tempting version of phase 1 is: let the canvas
draw several inputs, label them, and leave the resolver alone. That produces a screen saying
*liver annotation* and *reference annotation* above an emitted pipeline that feeds both from
one `params.gtf` — an interface asserting something the artifact cannot back up, which is the
exact failure this product exists to prevent. `CLAUDE.md`: *a person reading a value with no
reason sees a blank and asks; a model sees a blank and fills it.* A label over a merged channel
is worse than a blank; it is a filled-in blank that is wrong.

So the resolver is changed in phases 2–5, and the label is held off it here — permanently,
because the moment a label reaches a channel name it has become a `params.*` in a laboratory's
command line, and the worst case for a field a person types an input's name into is invariant
15's: `/data/patients/PT-4471023/`.

**Watched failing.** Threading `graph.labels` into `goal_of`'s `GoalInput` — the smallest
change that makes a label matter — fails
`test_two_drafts_differing_only_in_labels_emit_the_same_nextflow` with a diff on the
`ch_gtf` line, and `test_the_artifact_is_byte_identical_too` on `goal.have`. The
revert is in `docs/notes/audits/guard-ledger.md`.

**This file lives at the root rather than in `mendel-resolver/tests`** because it spans three
packages: `comeni-core` declares the field, `mendel-resolver` is what must not read it, and
`mendel-compiler` is where a leak would become visible. A guard held inside the package it
polices can only see half the path.
"""

import pathlib

import pytest
import yaml
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftLabel, DraftNode
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of

ROOT = pathlib.Path(__file__).parent.parent
REGISTRY = ROOT / "registry"

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"

#: Real sockets on the graph below — `<node>.<port>`, the keys the canvas puts a field on.
#: Deliberately the two `annotation.gtf` consumers, because they are the pair spec §0 is about:
#: today they are one channel, and the whole risk of a label is that naming them differently
#: makes a screen claim they are two.
LABELS = [
    DraftLabel(key="align.gtf", label="liver annotation"),
    DraftLabel(key="counts.annotation", label="reference annotation"),
    DraftLabel(key="counts.counts", label="the matrix we are after"),
]


@pytest.fixture(scope="module")
def stack():
    return layers.load(REGISTRY)


def _spine(labels: list[DraftLabel] | None = None) -> DraftGraph:
    """The RNA-seq spine, drawn by hand. The same graph either way but for `labels`."""
    return DraftGraph(
        nodes=[
            DraftNode(id="index", contract_id=GENOME),
            DraftNode(id="align", contract_id=STAR),
            DraftNode(id="sort", contract_id=SORT),
            DraftNode(id="counts", contract_id=COUNTS),
        ],
        edges=[
            DraftEdge(from_node="index", from_port="index", to_node="align", to_port="index"),
            DraftEdge(from_node="align", from_port="bam", to_node="sort", to_port="bam"),
            DraftEdge(from_node="sort", from_port="bam", to_node="counts", to_port="bam"),
        ],
        labels=labels or [],
    )


def _artifact(graph: DraftGraph, stack) -> Pipeline:
    return Pipeline.of(
        ir_of(graph, stack),
        stack.registry,
        stack.vocabulary,
        stack.measurements,
        stack.paths,
        goal=goal_of(graph, stack),
    )


def test_two_drafts_differing_only_in_labels_emit_the_same_nextflow(stack):
    """**The whole claim, in bytes.** Invariant 10 is *same `Goal` in → byte-identical `.nf`*,
    and a label that changed one character of the emitted workflow would have changed the goal
    — which is what makes this the honest check rather than an assertion about a field."""
    assert emit(_artifact(_spine(), stack)) == emit(_artifact(_spine(LABELS), stack))


def test_the_artifact_is_byte_identical_too(stack):
    """The `.nf` is downstream of `pipeline.yml`, so a leak could in principle reach the
    artifact and be dropped again before emission. Compare the serialised file, which is what
    a laboratory archives and what `mendel emit` reads back years later."""
    plain = yaml.safe_dump(_artifact(_spine(), stack).model_dump(mode="json"), sort_keys=True)
    named = yaml.safe_dump(_artifact(_spine(LABELS), stack).model_dump(mode="json"), sort_keys=True)
    assert plain == named


def test_no_label_text_appears_anywhere_in_either_output(stack):
    """A stronger reading of the same rule, and the one that catches a leak into a **comment**.

    The two tests above compare a labelled build against an unlabelled one, so a change that
    writes every label into both — a header line naming the drawing, say — passes them both.
    This one looks for the words themselves.
    """
    artifact = _artifact(_spine(LABELS), stack)
    text = emit(artifact) + yaml.safe_dump(artifact.model_dump(mode="json"))
    for label in LABELS:
        assert label.label not in text


def test_the_label_is_not_on_the_artifact_s_type_at_all(stack):
    """`DraftGraph` carries it; `Pipeline` has no field it could land in.

    Checked against the *schema* rather than against one instance, because an optional field
    that happens to be empty in this fixture is exactly the shape that starts holding data
    later without anybody deciding it should.

    **Field names, not the dumped text.** The first version searched the serialised schema for
    the word and failed on `AiPoint`'s prose — a guard firing on a docstring rather than on a
    field, which is the same shape as the failure banner scan that fired on the record it
    existed to show (Plan 4 phase 5).
    """
    schema = Pipeline.model_json_schema()
    named = {
        f"{name}.{field}"
        for name, definition in schema.get("$defs", {}).items()
        for field in definition.get("properties", {})
        if field in ("label", "labels")
    } | {f"Pipeline.{f}" for f in schema.get("properties", {}) if f in ("label", "labels")}
    assert named == set()


def test_a_socket_key_is_a_port_and_not_a_node():
    """`key` is `<node>.<port>`, and the type says so.

    A label keyed on a `NodeId` would survive its port being rewired, which is the one thing it
    must not do: rewire `counts.annotation` to a step's output and the socket is gone, so the
    name a person gave *the socket* has nothing left to name.
    """
    with pytest.raises(ValueError):
        DraftLabel(key="counts annotation", label="x")
    with pytest.raises(ValueError):
        # `:` is a `Subject`'s separator and a socket has no use for one, so it is refused
        # rather than tolerated — `SocketKey` is narrower than `DecisionKey` on purpose.
        DraftLabel(key="counts:annotation", label="x")


def test_a_label_is_one_line():
    """`Line`, not `str` — the same validator every free-text field on a door carries.

    A `DraftGraph` is not a door payload and this adds nothing to invariant 14's fourteen
    fields. It gets the validator anyway: the field is reachable by a person over HTTP, and a
    multi-line value in it is a paragraph pasted into a name.
    """
    with pytest.raises(ValueError):
        DraftLabel(key="align.gtf", label="liver\nannotation")
