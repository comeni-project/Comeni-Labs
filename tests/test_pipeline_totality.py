"""Every field of every type `Pipeline` replaces has a declared home in it.

Root D's finding applied to consolidation rather than to diffing. `diff_ir` enumerated the
fields it knew about, so every field added to the IR became a silent blind spot, and Plan 1.8
added four.

A hand-written mapping from three types into one has exactly that shape, and **reviewing it by
eye already failed five times**: three drafts of the spec's schema between them dropped
`LockedContract.container` (whose docstring says the `sealed` profile's digests-required rule
depends on it), `ResolvedValue.displaced_layer` (A5, A15), and `DecisionRecord`'s `candidates`,
`chosen` and `confidence`. Losing `container` would have been a consolidation sold as
strengthening reproducibility that quietly dropped the field the clinical profile needs.

So the mapping is checked mechanically, and anything deliberately not carried is named with a
reason rather than allowed by silence.
"""

from _walk import nested_models, reachable
from comeni_core.decision import ParamDecision, ProducerDecision, SourceDecision
from comeni_core.egress import Emitted, EmittedFile
from comeni_core.goal import Goal
from comeni_core.ir import IREdge, IRNode, ParamBinding, PipelineIR, ResolvedValue
from comeni_core.layered import Displacement
from comeni_core.lockfile import LockedContract, LockedLayer, Lockfile
from comeni_core.pipeline import Pipeline
from comeni_core.profile import DataProfile

REPLACED = [
    PipelineIR,
    IRNode,
    IREdge,
    ParamBinding,
    ResolvedValue,
    ParamDecision,
    ProducerDecision,
    SourceDecision,
    Lockfile,
    LockedContract,
    LockedLayer,
    Displacement,
    Emitted,
    EmittedFile,
    Goal,
    DataProfile,
]

NOT_CARRIED: dict[str, str] = {
    "PipelineIR.nodes": "renamed `steps` — a reader opening this file is not reading a graph.",
    "PipelineIR.edges": (
        "collapsed into `Step.inputs`, keyed under the consuming step. Lossless, since an edge "
        "has exactly one consumer, and it makes provenance readable in place."
    ),
    "IREdge.from_node": "carried as the node half of `StepInput.source`, an `EdgeRef`.",
    "IREdge.from_port": "carried as the port half of `StepInput.source`.",
    "IREdge.to_node": "carried by position — the `Step` this input is listed under.",
    "IREdge.to_port": "carried as `StepInput.port`.",
    "PipelineIR.registry_layers": (
        "carried as `registry.layers`, which pins each layer by digest as well as naming it."
    ),
    "IRNode.selection": (
        "renamed `Step.why`, the same shape a `Setting` carries. One word for one idea: why is "
        "this what it is."
    ),
    "Lockfile.contracts": (
        "carried per step as `Step.module`, so the pin sits beside the thing it pins rather "
        "than in a side file a reader has to join by hand."
    ),
}
"""Fields deliberately left behind, each with the reason.

An entry here is a decision. An absence from both this and `Pipeline` is an oversight, and the
test cannot tell them apart — which is why adding an entry has to cost a sentence.
"""


def _homes() -> set[str]:
    """Every field name reachable from `Pipeline`, at any depth."""
    return {name for model in reachable(Pipeline) for name in model.model_fields}


def test_every_replaced_field_has_a_home():
    homes = _homes()
    missing = [
        f"{model.__name__}.{name}"
        for model in REPLACED
        for name in model.model_fields
        if name not in homes and f"{model.__name__}.{name}" not in NOT_CARRIED
    ]
    assert missing == [], (
        "these fields have nowhere to go in Pipeline — carry them, or add an entry to "
        "NOT_CARRIED saying why not:\n  " + "\n  ".join(missing)
    )


def test_nothing_is_excused_that_is_actually_carried():
    """A stale `NOT_CARRIED` entry is worse than none: it reads as a decision that was made and
    reviewed, while the field is carried after all."""
    homes = _homes()
    stale = [key for key in NOT_CARRIED if key.split(".", 1)[1] in homes]
    assert stale == [], f"NOT_CARRIED names fields Pipeline does carry: {stale}"


def test_no_field_of_pipeline_is_a_frozenset():
    """`digest_of` hashes `model_dump_json()`, and a set has no stable order.

    `digest.py` says it outright: anything new that serialises a set silently breaks that
    function and every lockfile made with it. `Pipeline` is what publish ships, so this is the
    CLAUDE.md gotcha arriving in a type designed after the lesson and still able to miss it.
    """
    offenders = []
    for model in reachable(Pipeline):
        sorted_fields = {
            field
            for decorator in model.__pydantic_decorators__.field_serializers.values()
            for field in decorator.info.fields
        }
        offenders += [
            f"{model.__name__}.{name}"
            for name, field in model.model_fields.items()
            if "frozenset" in str(field.annotation) and name not in sorted_fields
        ]
    assert offenders == [], (
        "a set with no `field_serializer` that sorts:\n  " + "\n  ".join(offenders)
    )


def test_pipeline_holds_no_registry():
    """`registry.py` carries a mapping and says it is legal *because* `Registry` is not
    reachable from a payload — "a mapping is legal here in a way it is not on the IR".

    Materialisation must copy values into `Step`, never hold a `Registry`, `ModuleContract` or
    `Vocabulary`. `Pipeline.of()` takes a registry as an argument; `Pipeline` must not have a
    field for one, or that premise silently stops holding and the egress guard is reporting on
    something that is no longer true.
    """
    forbidden = {"Registry", "ModuleContract", "Vocabulary", "MeasurementRegistry"}
    offenders = [
        f"{model.__name__}.{name} -> {nested.__name__}"
        for model in reachable(Pipeline)
        for name, field in model.model_fields.items()
        for nested in nested_models(field.annotation)
        if nested.__name__ in forbidden
    ]
    assert offenders == [], (
        "Pipeline must copy values, not hold the things it copied from:\n  "
        + "\n  ".join(offenders)
    )
