"""A label is for a reader and never for the pipeline. Plan 5B phase 1, spec §5.

The operator's constraint, in their own words: *"yes it's a label, does not change the actual
keys."*

A pipeline can legitimately take several inputs of one type, and `fastq.reads` twice tells a
person nothing about which is which — naming them *tumour* and *normal* is a reading aid over a
graph whose identity is unchanged.

**The temptation is to thread the label into the channel name.** It is right there, it is a
`NfIdentifier` away, and it would make the emitted Groovy read beautifully. It would also make
what somebody typed into a browser decide what a pipeline *is*, which is A130's shape: a client
claiming something about the artifact that nothing downstream could catch.

**Tested against `materialise` rather than against the API**, because the API's draft tests need
Postgres and skip in CI — a guard that does not run is not a guard. This is where the claim
actually lives: *nothing in `materialise` reads it*.
"""

import pathlib

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftLabel, DraftNode
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of

ROOT = pathlib.Path(__file__).parent.parent

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"


def _graph(*labels: DraftLabel) -> DraftGraph:
    """Two wired steps, with whatever labels the caller wants on them."""
    return DraftGraph(
        nodes=[
            DraftNode(id="star_align", contract_id=STAR),
            DraftNode(id="samtools_sort", contract_id=SORT),
        ],
        edges=[
            DraftEdge(
                from_node="star_align", from_port="bam", to_node="samtools_sort", to_port="bam"
            )
        ],
        labels=list(labels),
    )


def _built(graph: DraftGraph):
    stack = layers.load(ROOT / "registry")
    ir = ir_of(graph, stack, by="a test")
    pipeline = Pipeline.of(
        ir, stack.registry, stack.vocabulary, stack.measurements, stack.paths,
        goal=goal_of(graph, stack),
    )
    return emit(pipeline), pipeline.model_dump_json()


def test_a_label_reaches_neither_the_nextflow_nor_the_artifact():
    """**The assertion phase 1 rests on.** Watched failing against a version that threads the
    label into the channel name."""
    plain_nf, plain_doc = _built(_graph())
    named_nf, named_doc = _built(
        _graph(
            DraftLabel(key="star_align.reads", label="tumour biopsy"),
            DraftLabel(key="star_align.index", label="GRCh38 primary"),
        )
    )

    assert named_nf == plain_nf, "a label reached the emitted Nextflow"
    assert named_doc == plain_doc, "a label reached pipeline.yml"
    for word in ("tumour", "biopsy", "GRCh38"):
        assert word not in named_nf and word not in named_doc, (
            f"{word!r} was typed into a browser and came out in the artifact"
        )


def test_the_comparison_is_not_vacuous():
    """Both halves of the test above would pass if `_built` returned constants."""
    nf, doc = _built(_graph())
    assert "STAR_ALIGN" in nf and "SAMTOOLS_SORT" in nf
    assert "samtools" in doc


def test_a_label_survives_a_round_trip_through_the_draft():
    """It is stored and read back, or the browser has nowhere to keep it — which is the whole
    reason it is a field on `DraftGraph` rather than browser-local state."""
    graph = _graph(DraftLabel(key="star_align.reads", label="tumour biopsy"))
    again = DraftGraph.model_validate_json(graph.model_dump_json())
    assert [(one.key, one.label) for one in again.labels] == [
        ("star_align.reads", "tumour biopsy")
    ]


def test_a_label_key_is_a_port_and_not_a_node():
    """`<node>.<port>`, validated. A label should survive its node being dragged — which changes
    no key — and not survive its port being rewired, which changes what the label was about.

    Validated rather than merely marked, because a draft is stored and read back: an unvalidated
    key is where a path or a newline enters something this repository persists.
    """
    import pytest

    with pytest.raises(ValueError):
        DraftLabel(key="star_align", label="just a node")
    with pytest.raises(ValueError):
        DraftLabel(key="../../etc/passwd", label="a path")
