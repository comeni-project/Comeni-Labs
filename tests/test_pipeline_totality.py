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

import typing

from _walk import nested_models, reachable
from comeni_core.artifact.egress import Emitted, EmittedFile
from comeni_core.artifact.lockfile import LockedContract, LockedLayer, Lockfile
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.layered import Displacement
from comeni_core.goal.asked import Goal
from comeni_core.goal.profile import DataProfile
from comeni_core.plan.decision import ParamDecision, ProducerDecision, SourceDecision
from comeni_core.plan.ir import IREdge, IRNode, ParamBinding, PipelineIR, ResolvedValue
from comeni_core.spell.marks import Mark

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


def _shape(annotation: object) -> str:
    """An annotation reduced to the thing it carries, ignoring optionality and containers.

    `list[Digest]`, `Digest | None` and `Digest` are the same home for this purpose: the
    question A68 asks is whether the *value* has somewhere to go, not whether the wrapper
    matches. Reducing rather than comparing exactly is what keeps this from refusing every
    field `Pipeline` legitimately re-wraps.

    A `Mark` is the reduction for a marked string, because that is what makes two strings the
    same kind of thing here: `ModuleRef.digest` and `EmittedFile.digest` are both `Digest` and
    the check is not meant to separate them, while `Digest` and `NodeId` are different homes
    even though both are `str`. That distinction is the whole of A68's first reproduction.
    """
    marks = [m for m in getattr(annotation, "__metadata__", ()) if isinstance(m, Mark)]
    if marks:
        return marks[0].value
    models = nested_models(annotation)
    if models:
        return models[0].__name__
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    if args:
        return _shape(args[0])
    return getattr(annotation, "__name__", str(annotation))


def _homes_by_type() -> dict[str, set[str]]:
    """Field name -> every shape carried under that name anywhere in `Pipeline`."""
    homes: dict[str, set[str]] = {}
    for model in reachable(Pipeline):
        for name, field in model.model_fields.items():
            homes.setdefault(name, set()).add(_shape(field.annotation))
    return homes


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


# --- A68, issue #32: the guard checked names against themselves ---------------------------

VERBATIM = frozenset(
    {
        "Goal",
        "DataProfile",
        "Displacement",
        "Emitted",
        "EmittedFile",
        "LockedLayer",
        "ParamDecision",
        "ProducerDecision",
        "SourceDecision",
    }
)
"""Types `Pipeline` carries **whole**, for which the name check is vacuous by construction.

A68: nine of the sixteen `REPLACED` types are reachable from `Pipeline` unchanged, so deleting
one of their fields removes it from the required set and the available set at once. The
reviewer removed `Displacement.winning_key` and got `4 passed`. **That is 47 of 78 fields
checked against themselves** — including `candidates`, `chosen` and `confidence`, three of the
five fields this test was written to catch.

Naming them is the fix rather than a workaround: for a type carried verbatim there is nothing
to check, and pretending otherwise is what made the number look like coverage.
`test_the_verbatim_set_is_what_pipeline_actually_carries` keeps the list from drifting.

**And the residue is real, so it is written down.** Deleting a field from a verbatim type —
the reviewer's `Displacement.winning_key` probe — is still invisible *here*, and no totality
check can see it: the field is defined once and read once, so removing it removes the question
along with the answer. What that probe actually tests is "did somebody mean to delete this",
which is a different question, and the tests that *read* `winning_key` are where it is asked.
A68's second reproduction is therefore acknowledged rather than closed, and the 60% figure it
reports is now 0% of what this file claims to cover instead of 60% of what it appeared to.
"""


RETYPED: dict[str, str] = {
    "IRNode.params": (
        "carried as `Step.settings`, a `list[Setting]`. A `ParamBinding` is a name and a "
        "`ResolvedValue`; a `Setting` is that plus the **route** that carries the value to "
        "the tool, which is what issue #10 added and what a reader needs beside the number."
    ),
    "IRNode.presence": (
        "carried as `Step.presence`, a `Why`. Same reduction `IRNode.selection` makes to "
        "`Step.why` — a `ResolvedValue` is provenance the resolver builds, and a `Why` is "
        "provenance a reader opens."
    ),
    "ParamBinding.value": (
        "carried as `Setting.value` plus `Setting.why`. The `ResolvedValue` is split in two: "
        "the answer, and the account of it. A104 is why the account records `for_value`."
    ),
}
"""Fields `Pipeline` carries under a **different type**, each naming the target.

A third category, and it exists because A68's fix made the second one necessary. `NOT_CARRIED`
means left behind; this means carried and reshaped. The name-only check could not tell the two
apart — it saw `params` somewhere in the graph and stopped — which is exactly how removing
`ModuleRef.digest` stayed green on `EmittedFile.digest`.

Written out rather than inferred, because "this became something else" is a design decision and
the reason is the part worth keeping.
"""


CARRIED_AS: dict[str, str] = {
    "PipelineIR.decisions": "decisions",
    "PipelineIR.profile": "goal.profile",
    "PipelineIR.displaced": "registry.displaced",
    "PipelineIR.unverified": "registry.unverified",
    "IRNode.id": "steps.id",
    "IRNode.contract_id": "steps.module.contract_id",
    "IREdge.type_id": "channels.type_id",
    "IREdge.states": "steps.inputs.states",
    "ParamBinding.name": "steps.settings.name",
    "ResolvedValue.value": "steps.settings.value",
    "ResolvedValue.tier": "steps.why.tier",
    "ResolvedValue.source": "steps.why.source",
    "ResolvedValue.reason": "steps.why.reason",
    "ResolvedValue.premise": "steps.why.premise",
    "ResolvedValue.axis_reason": "steps.why.axis_reason",
    "ResolvedValue.from_layer": "steps.why.from_layer",
    "ResolvedValue.displaced_layer": "steps.why.displaced_layer",
    "Lockfile.version": "version",
    "Lockfile.layers": "registry.layers",
    "LockedContract.id": "steps.module.contract_id",
    "LockedContract.digest": "steps.module.digest",
    "LockedContract.container": "steps.module.container",
}
"""Where each restructured field lives in `Pipeline`, **by path**.

A68's first reproduction is why this is a path and not a name. `_homes()` was a flat set of
field names, so removing `ModuleRef.digest` — the module content pin, and the field the
`sealed` profile's digests-required rule depends on — left the guard green, because
`EmittedFile.digest` supplied the word. Reducing to the declared `Mark` does not help either:
both are `Digest`, and they are meant to be.

So the mapping is written out and then *walked*. `test_every_carried_field_is_where_it_says`
follows each path from `Pipeline` and fails if a segment does not exist — which is the check
that removing `ModuleRef.digest` now trips, because nothing else is at `steps.module.digest`.

Hand-written, like `NOT_CARRIED` and `RETYPED`, and for the same reason: a consolidation of
three types into one is a design decision per field, and the machine's job is to notice when
the design and the code stop agreeing — not to infer the design.
"""


def _walk_path(path: str) -> object | None:
    """Follow a dotted field path from `Pipeline`, returning the annotation it lands on.

    Containers are transparent: `steps.module.digest` walks `list[Step]` -> `Step` without the
    path having to say so, because the question is where the value lives and not how many of
    them there are.
    """
    current: object = Pipeline
    for segment in path.split("."):
        models = nested_models(current) if not isinstance(current, type) else [current]
        model = next(
            (m for m in models if hasattr(m, "model_fields") and segment in m.model_fields),
            None,
        )
        if model is None:
            return None
        current = model.model_fields[segment].annotation
    return current


def _restructured() -> list[type]:
    return [model for model in REPLACED if model.__name__ not in VERBATIM]


def test_the_verbatim_set_is_what_pipeline_actually_carries():
    """The list is derived-checked, never trusted. A type that quietly becomes carried whole
    would otherwise keep a name-match that proves nothing, and a type that stops being carried
    would lose its check without anybody noticing."""
    carried = {model.__name__ for model in reachable(Pipeline)}
    claimed_but_absent = sorted(VERBATIM - carried)
    assert claimed_but_absent == [], (
        "VERBATIM names types Pipeline does not carry — their fields are being excused from "
        f"a check that would apply:\n  {claimed_but_absent}"
    )
    unclaimed = sorted(model.__name__ for model in REPLACED if model.__name__ in carried)
    assert unclaimed == sorted(VERBATIM), (
        "a REPLACED type is carried whole and is not in VERBATIM, so its fields are being "
        f"checked against themselves:\n  {sorted(set(unclaimed) ^ VERBATIM)}"
    )


def test_a_restructured_field_needs_a_home_of_a_compatible_type():
    """A68's first half. `_homes()` was a flat set of field *names*, so removing
    `ModuleRef.digest` — the module content pin — left the test green because
    `EmittedFile.digest` supplied the name. Two different digests, one word.

    Nineteen to twenty-two other tests catch the consequence; the guard written to catch it
    did not.
    """
    homes = _homes_by_type()
    missing = []
    for model in _restructured():
        for name, field in model.model_fields.items():
            key = f"{model.__name__}.{name}"
            if key in NOT_CARRIED or key in RETYPED:
                continue
            if key not in CARRIED_AS and _shape(field.annotation) not in homes.get(
                name, set()
            ):
                missing.append(f"{key}: {_shape(field.annotation)}")
    assert missing == [], (
        "these fields have no home in Pipeline *of a compatible type* — a name-match with an "
        "unrelated field is not a home:\n  " + "\n  ".join(missing)
    )


def test_nothing_is_retyped_that_is_actually_carried_unchanged():
    """A stale `RETYPED` entry is the same defect as a stale `NOT_CARRIED` one: it reads as a
    decision somebody made while the field is carried as-is after all."""
    homes = _homes_by_type()
    stale = [
        key
        for key in RETYPED
        for model in REPLACED
        if model.__name__ == key.split(".")[0]
        and _shape(model.model_fields[key.split(".")[1]].annotation)
        in homes.get(key.split(".")[1], set())
    ]
    assert stale == [], f"RETYPED names fields Pipeline carries unchanged: {stale}"


def test_the_three_excuse_lists_do_not_overlap():
    """A field excused twice is a field whose reason nobody has to agree with."""
    overlap = sorted(set(NOT_CARRIED) & set(RETYPED))
    assert overlap == [], f"excused as both left-behind and reshaped: {overlap}"


def test_every_carried_field_is_where_it_says():
    """A68's first reproduction, closed. Each restructured field names its path in `Pipeline`
    and the path is walked — so removing `ModuleRef.digest` fails here, where a name-match on
    `EmittedFile.digest` used to carry it."""
    missing = [
        f"{key} -> {path}"
        for key, path in CARRIED_AS.items()
        if _walk_path(path) is None
    ]
    assert missing == [], (
        "these fields claim a home in Pipeline that does not exist — the mapping and the "
        "code have stopped agreeing:\n  " + "\n  ".join(missing)
    )


def test_every_restructured_field_is_accounted_for():
    """No field of a restructured type may be silently absent from all three lists. The lists
    are the design; a field in none of them is a decision nobody made."""
    unaccounted = [
        f"{model.__name__}.{name}"
        for model in _restructured()
        for name in model.model_fields
        if f"{model.__name__}.{name}" not in CARRIED_AS
        and f"{model.__name__}.{name}" not in NOT_CARRIED
        and f"{model.__name__}.{name}" not in RETYPED
    ]
    assert unaccounted == [], (
        "these fields are in none of CARRIED_AS, RETYPED or NOT_CARRIED:\n  "
        + "\n  ".join(unaccounted)
    )
