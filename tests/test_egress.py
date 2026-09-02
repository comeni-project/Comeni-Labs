"""Invariant 14: data leaves through four declared doors and no others.

The doors are listed here, literally, on purpose. Adding one means editing a file
whose contents say "these are all the ways data leaves this building" — which is
the moment a person should be thinking, and this test is what makes them.
"""

import enum
import types
import typing
from collections import abc

import pytest
from _walk import reachable
from comeni_core.artifact import egress
from comeni_core.plan.tiers import Tier, ValueSource
from comeni_core.spell.marks import Mark
from pydantic import BaseModel, ValidationError, computed_field

DOORS = {"goal_extraction", "tier4_resolution", "compiler_repair", "publication"}

_BINARY = (bytes, bytearray, memoryview)
"""No payload may carry a blob. A signature field on a lockfile is the obvious way this
arrives, and it is still a blob — sign the artifact beside the bundle, not inside it."""

# Free text is the taint source, and **this set is the count** — not any sentence about it.
#
# This comment said "exactly two" for three plans while the set below held four, then six,
# then seven; A33 is the same drift in `CLAUDE.md` invariant 14, and round four found this
# copy of it. Naming a number in prose beside a literal set creates two sources of truth and
# only one of them is executable, so the number is deliberately not repeated here. Widening
# the boundary means adding a line below, which is a diff that says *these are all the ways
# data leaves*.
#
# Every increase so far arrived by a refactor rather than by a new kind of string crossing —
# A16 splitting `DecisionRecord` into three, and `Pipeline` taking door 4 — which is exactly
# what a literal list exists to make somebody look at.
FREE_TEXT_FIELDS = {
    ("PromptRequest", "prompt"),
    ("GateFailure", "tool_message"),
    # Reachable through RepairRequest.ir and Pipeline. Model- or resolver-written
    # prose explaining a choice — genuinely free text, and named here rather than
    # exempted, because an audit found these riding along unexamined inside a nested
    # model the guard never opened.
    ("ResolvedValue", "reason"),
    # One per decision kind since A16 split `DecisionRecord` into three. Four entries
    # became six by a refactor rather than by a new field crossing the boundary — which is
    # exactly the sort of change this literal list exists to make someone notice.
    ("ParamDecision", "reason"),
    ("ProducerDecision", "reason"),
    ("SourceDecision", "reason"),
    # Seventh, and expected: `Pipeline` became door 4's payload in Plan 1.10 Task 11, and
    # `Why.reason` is the citation beside every value — the legibility the whole artifact
    # exists for. It is a `Line`, so it is `FREE_TEXT` with a single-line validator, and it
    # reaches this set through exactly the same door the four `reason` fields above do.
    #
    # It is listed rather than exempted for the reason the whole list is literal: widening
    # the boundary should mean editing a file that says *these are all the ways data leaves*.
    ("Why", "reason"),
    # Eleventh through fourteenth, Plan 2.5, and they arrive as a GROUP for one reason:
    # `Ambiguity` became a `comeni_core.review.Question`, so the four fields the forge had
    # always carried on a `Hole` now reach door 2 as well. Two are prose and two are the
    # excerpt they point at.
    #
    # **Why they were let through rather than stripped.** The forge measured a local model
    # re-deriving shipped contracts at 69% and then 88%, and two of the three fixes behind
    # that were exactly *the question never said what it was about* (`what`) and *the
    # evidence was a Python repr nobody could read* (`evidence`). Door 2 hands a tier-4
    # question to a model. Carrying candidates and nothing else would rebuild the measured
    # 69% configuration on the build path, having already paid to learn it.
    # `test_the_door_carries_what_the_forge_measured_a_model_needs` is that argument as a
    # test, so removing them fails rather than silently regressing.
    ("AmbiguityRequest", "what"),
    ("AmbiguityRequest", "why_open"),
    # **`Excerpt` is the first author on this list that is not an author.** Every other entry
    # is composed by somebody — a user, a contract author, a rule author, the resolver, a
    # reviewer. These two are *quoted*: a source file already contains the text and an
    # excerpt copies it, with `locator` naming where. That is a weaker claim than the rest of
    # the list makes and it is written down rather than assumed, because "it is only quoted"
    # is exactly the kind of reasoning that widens a boundary without anybody noticing.
    #
    # What bounds it is the source: excerpts are read from vendored modules and registry
    # files, which are public data, and never from a prompt or a goal.
    ("Excerpt", "locator"),
    ("Excerpt", "text"),
    # Eighth and ninth, Plan 1.14 Task 5, and they are **one field splitting in two** rather
    # than a new kind of string crossing — the same pattern as A16 turning four `reason`
    # entries into six. `reason` was answering two questions at once: why this decision is
    # made this way at all (a rule block's methodology) and why *this answer* won (the row's
    # choice). Carrying both in one field is how the shipped registry came to cite the STAR
    # paper as the reason HISAT2 was chosen — A79 and A107.
    #
    # Same author, same source, same door: registry data written by a contract or rule
    # author, reaching this set through `RepairRequest.ir` and `Pipeline` exactly as
    # `reason` does. Nothing newly crosses; one thing that already crossed is now legible.
    ("ResolvedValue", "axis_reason"),
    ("Why", "axis_reason"),
    # Tenth, Plan 1.14 Task 8, and the **first one that is genuinely new** rather than a
    # split of something already crossing. The nine above are written by a contract author, a
    # rule author, or the resolver. This one is written by *the person answering a tier-4
    # question*, in the artifact, after resolution — a new author, and the only free-text
    # field in the system a reviewer fills in themselves.
    #
    # It is listed rather than exempted for exactly that reason. Tier 4 is the honesty
    # mechanism and the one tier where a person supplies the answer, and until now they had
    # nowhere to say why: `upgrade` replaced a hand-written sentence with "selected the first
    # of 1 candidates without judgement" under `source: human` (A77). The alternative to this
    # field is a reviewer's reasoning living nowhere, which is worse for the claim than one
    # more declared string crossing a door somebody has to argue for.
    ("ParamDecision", "override_reason"),
}


def _payload_types() -> set[type[BaseModel]]:
    """Every model reachable from a declared payload, not just the payload itself.

    The first version returned only `EgressPayload` subclasses, and every check walked
    `typing.get_args`, which returns `()` at a nested `BaseModel`. So nothing ever looked
    inside `RepairRequest.ir`, and a payload serialised a patient path and an SSN while
    this file reported green. Transitive expansion is the fix; exempting nested models
    would be the hole.

    **The roots come from `DOORS`**, not from what happens to be defined in `egress.py`.
    That distinction had no consequences until Plan 1.10 Task 11 moved the publication
    payload to `comeni_core.artifact.pipeline`: scanning `vars(egress)` then found three doors
    out of four, and `Pipeline` — the door with no undo — crossed the boundary entirely
    unchecked
    while this file reported ten passed.

    `DOORS` is the declaration of what actually leaves. The subclass scan stays beside it,
    so a payload type declared and not yet wired to a door is still covered; the union is
    what makes both "declared but unused" and "used but declared elsewhere" visible.
    """
    roots = set(egress.DOORS.values())
    roots |= {
        obj
        for obj in vars(egress).values()
        if isinstance(obj, type)
        and issubclass(obj, egress.EgressPayload)
        and obj is not egress.EgressPayload
    }
    return reachable(*roots)


def test_every_door_is_walked_by_the_checks_below():
    """The guard that would have caught the hole above.

    Every check in this file starts from `_payload_types()`, so a door whose payload that
    set does not contain is a door nothing in here inspects — silently, and with a full green
    run to say so.
    """
    walked = _payload_types()
    for name, payload in egress.DOORS.items():
        assert payload in walked, f"door {name} carries {payload.__name__}, and nothing walks it"


def _mentions(annotation: object, marker: object) -> bool:
    """Walk an annotation tree. `Text | None` hides its metadata one level down.

    `marker` is a `Mark` member or `typing.Any`. Identity rather than equality: a `Mark` is a
    `StrEnum`, so `"free-text" == Mark.FREE_TEXT` is true while `"free-text" is Mark.FREE_TEXT`
    is not — and the whole point of closing the vocabulary (A20) is that a bare string must not
    read as a declared marker.
    """
    metadata = getattr(annotation, "__metadata__", ())
    if any(meta is marker for meta in metadata):
        return True
    return any(_mentions(arg, marker) for arg in typing.get_args(annotation))


def _has_bare_str(annotation: object) -> bool:
    """True if `str` is reachable without passing through an `Annotated[...]` wrapper.

    `Annotated` is the declaration. `NodeId`, `Text` and friends all carry metadata,
    and a `StrEnum` is a closed vocabulary rather than free text, so neither trips
    this. A plain `str` is the thing with nothing said about it.
    """
    if annotation is str:
        return True
    if getattr(annotation, "__metadata__", None):
        return False
    return any(_has_bare_str(arg) for arg in typing.get_args(annotation))


def _mentions_mapping(annotation: object) -> bool:
    """Any mapping, not just the concrete `dict`.

    This tested `issubclass(origin, dict)`, and `collections.abc.Mapping` is a
    *superclass* of `dict` rather than a subclass — so `Mapping[MeasurementId,
    ParamValue]` walked straight through a rule whose own docstring forbids it, while
    being an ordinary dict at runtime with arbitrary keys. Audit A6.

    Testing against `Mapping` catches `dict`, `MutableMapping`, `OrderedDict`, `Counter`
    and `defaultdict` in one, because all of them are subclasses of it and that is the
    direction the check has to run.
    """
    origin = typing.get_origin(annotation)
    if origin is not None and isinstance(origin, type) and issubclass(origin, abc.Mapping):
        return True
    if getattr(annotation, "__metadata__", None):
        return any(_mentions_mapping(arg) for arg in typing.get_args(annotation)[:1])
    return any(_mentions_mapping(arg) for arg in typing.get_args(annotation))


def _mentions_any(annotation: object) -> bool:
    """`Any` is the annotation, never metadata — which is why the old rule could not fire.

    `test_no_payload_carries_an_untyped_container` called `_mentions(annotation, typing.Any)`,
    and `_mentions` searches `__metadata__` for a marker object. `typing.Any` is never an
    `Annotated` metadata element, so the predicate was `False` for every annotation that has
    ever existed and the rule had never been able to fail. Audit A20.
    """
    if annotation is typing.Any:
        return True
    return any(_mentions_any(arg) for arg in typing.get_args(annotation))


def _mentions_binary(annotation: object) -> bool:
    """`bytes` is not `str`, not a mapping, not `Any`, and carried no marker.

    So it was invisible to every rule in this file while being an unbounded channel for
    exactly the free text the boundary exists to contain — a prompt, a path and a
    diagnosis all fit in one, and none of them is inspectable by anything here. Banned
    outright rather than annotated, because there is no declared-ID version of a blob:
    an `Annotated[bytes, ...]` is a blob with a label on it. Audit A6.
    """
    if isinstance(annotation, type) and issubclass(annotation, _BINARY):
        return True
    return any(_mentions_binary(arg) for arg in typing.get_args(annotation))


def _serialised_hints(model: type[BaseModel]) -> dict[str, object]:
    """Name → annotation for everything that reaches the JSON, not everything declared.

    A57. `model_fields` is what a payload *declares*; a `@computed_field` lands in
    `model_computed_fields` and crosses the door all the same. Every rule below asks this
    instead, because the question a door guard has to answer is what is **serialised** — not
    what was annotated.

    A `@model_serializer` is the third route and cannot be covered here: it replaces the dump
    wholesale, so there is no per-key annotation to return. `test_no_payload_replaces_its_own_dump`
    forbids it outright, which is the only enforceable rule about a shape with nothing to check.
    """
    hints = typing.get_type_hints(model, include_extras=True)
    serialised: dict[str, object] = {
        name: annotation for name, annotation in hints.items() if name in model.model_fields
    }
    serialised.update(
        {name: info.return_type for name, info in model.model_computed_fields.items()}
    )
    return serialised


def _fields(model: type[BaseModel], marker: object) -> set[tuple[str, str]]:
    return {
        (model.__name__, name)
        for name, annotation in _serialised_hints(model).items()
        if _mentions(annotation, marker)
    }


_PERMITTED_TERMINALS = (int, float, bool, type(None))
_PERMITTED_CONTAINERS = (list, frozenset)


def _leaf_problems(
    annotation: object, where: str, models: set[type[BaseModel]], marked: bool = False
) -> list[str]:
    """Every leaf of an annotation that is not a declared shape. **An allowlist.**

    The four rules below this one enumerate forbidden shapes, which is why each audit finds
    the next one — `Mapping` and `bytes` in round one, then `object`, `Path` and `Any` in
    round two. The space of Python annotations is open and a blocklist can only forbid what
    somebody named.

    This asks the opposite question. The permitted set is a transcription of what the payload
    graph already holds: 22 models, `list` and `frozenset` and nothing else, eight terminal
    kinds. Anything outside it fails and the person adding it edits this function.

    `marked` tracks whether an enclosing `Annotated` carried a `Mark`, because that is what
    makes a `str` declared. It is *some* metadata element, never all — `HumanParamValue`
    legitimately carries an `AfterValidator` alongside, and requiring all would break A3's fix.
    """
    metadata = getattr(annotation, "__metadata__", ())
    if metadata:
        inner = typing.get_args(annotation)[0]
        seen = marked or any(isinstance(meta, Mark) for meta in metadata)
        return _leaf_problems(inner, where, models, seen)

    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        # A discriminator. `Literal[DecisionKind.PARAM]` is *narrower* than the enum it
        # draws from — one member rather than any — so it is permitted for the same reason
        # an enum is, and only for values that would themselves be permitted leaves.
        return [
            problem
            for value in typing.get_args(annotation)
            for problem in _leaf_problems(type(value), where, models, marked)
        ]
    if origin in (typing.Union, types.UnionType) or origin in _PERMITTED_CONTAINERS:
        return [
            problem
            for arg in typing.get_args(annotation)
            for problem in _leaf_problems(arg, where, models, marked)
        ]
    if origin is not None:
        name = getattr(origin, "__name__", repr(origin))
        return [f"{where}: `{name}` is not a declared container (only list and frozenset are)"]

    if annotation is str:
        if marked:
            return []
        return [f"{where}: a bare `str` — annotate it with a `Mark`"]
    if annotation in _PERMITTED_TERMINALS:
        return []
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            # **A closed vocabulary, and "closed" is a claim about the class.** `_missing_`
            # is the documented hook for accepting an *undeclared* value and can synthesise
            # a member from anything, so an enum that defines one is an open vocabulary
            # wearing a closed one's type. A63: a reviewer added such a field to `GateFailure`
            # and crossed an arbitrary path string with fifteen tests passing.
            #
            # Every class below `Enum` is checked, not only this one — a `_missing_` on a base
            # is the same hook one level up, and `vars(cls)` alone would miss it.
            opened = [
                base.__name__
                for base in annotation.__mro__
                if base not in (enum.Enum, enum.StrEnum, enum.IntEnum, str, int, object)
                and "_missing_" in vars(base)
            ]
            if opened:
                return [
                    f"{where}: `{annotation.__name__}` defines `_missing_` "
                    f"(on {', '.join(opened)}), so it accepts undeclared values — that is an "
                    "open vocabulary with a closed one's type"
                ]
            return []
        if issubclass(annotation, BaseModel) and annotation in models:
            return []
    return [f"{where}: `{annotation}` is not a declared shape"]


def test_every_payload_field_is_a_declared_shape():
    """Invariant 14, asked as an allowlist rather than as four prohibitions.

    Audit A19 (`object`), A20 (`Any`) and A30 (`Path`) are all the same defect: a shape the
    guard was not written against is silence. This closes them together with everything
    round three would otherwise find.
    """
    models = _payload_types()
    offenders: list[str] = []
    for payload in sorted(models, key=lambda m: m.__name__):
        for name, annotation in _serialised_hints(payload).items():
            offenders += _leaf_problems(annotation, f"{payload.__name__}.{name}", models)
    assert offenders == [], "these payload fields are not declared shapes:\n" + "\n".join(offenders)


def test_the_doors_are_exactly_four():
    assert set(egress.DOORS) == DOORS


def test_every_door_declares_an_egress_payload():
    for name, payload in egress.DOORS.items():
        assert issubclass(payload, egress.EgressPayload), name


def test_free_text_lives_only_where_declared():
    """Fourteen fields, not two, and not six, and not ten.

    CLAUDE.md said "exactly two" for a plan and a half while this list held four, then six;
    the list is the honest count and the prose is what drifts. Six became seven when
    `Pipeline` took door 4 — by a payload swap rather than by a new kind of string crossing,
    which is exactly the sort of change a literal list exists to make someone look at.
    """
    found: set[tuple[str, str]] = set()
    for payload in _payload_types():
        found |= _fields(payload, Mark.FREE_TEXT)
    assert found == FREE_TEXT_FIELDS


def test_payloads_forbid_unknown_fields():
    for payload in _payload_types():
        assert payload.model_config.get("extra") == "forbid", payload.__name__


def test_no_payload_carries_an_undeclared_string():
    """Every string is either a declared ID alias or explicitly marked `Mark.FREE_TEXT`.

    Without this, `user_note: str` sails through every other test in this file — it
    carries no `Mark` to catch and no `Any` to forbid — and a prompt fits in
    it perfectly. Found by running the plan's own break-the-guard step, which is what
    that step is for.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _has_bare_str(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are plain `str`; annotate them as an ID type or as free text: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_a_mapping():
    """A payload may not contain a dict, however cleverly its key is typed.

    `dict[MeasurementId, MeasurementValue]` passes every other rule in this file —
    the key is an Annotated newtype, so the bare-str rule does not fire — and is
    still unsafe, because nothing checks the key was ever *declared*. A payload
    carrying {"patient_id": "4471023"} would type-check perfectly.

    That is the `user_note: str` lesson one level up: the right shape is not the
    right content. Rather than a subtle rule about which key types are acceptable,
    payloads carry lists of declared records. Subtlety is what failed last time.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _mentions_mapping(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are mappings; use a list of declared records instead: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_raw_bytes():
    """A blob is an unbounded channel, and no rule in this file can see inside one.

    Nothing carries one today, which is why this is the easy time to forbid it. A
    `signature: bytes` on the lockfile is the plausible next field and would have been
    accepted by every other rule here.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _mentions_binary(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are binary blobs, which no rule in this file can inspect: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_an_untyped_container():
    """A dict[str, Any] would defeat the whole thing, so no payload may declare one."""
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _mentions_any(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are `Any`, which defeats every other rule here: "
        + ", ".join(sorted(offenders))
    )


def test_every_ambiguity_field_can_cross_the_door():
    """A32 — a field a model is never told is as much a boundary defect as one it should
    not be told.

    `Ambiguity` projects to `AmbiguityRequest` at door 2. The projection is written in Plan
    2, so nothing builds one yet — which is exactly when this is worth asserting, because a
    field added to an ambiguity between now and then would land nowhere and nobody would
    see it fail. `type_id` and `required` were already in that state when this was written.
    """

    from comeni_core.artifact.egress import AmbiguityRequest
    from comeni_core.plan.decision import Ambiguity, AmbiguityKinds

    # `model_fields`, not `_serialised_hints`, and deliberately: this asks whether each
    # ambiguity field has somewhere *to go*, and a `@computed_field` is not a destination —
    # nothing can be assigned to it. A57 widened the rules that ask what crosses a door; this
    # one asks what can be carried, which is a different question with a different answer.
    crossable = set(AmbiguityRequest.model_fields)
    for asked in AmbiguityKinds:
        for name in asked.model_fields:
            if name == "kind":
                continue  # the discriminator picks the projection; it is not projected
            assert name in crossable, (
                f"{asked.__name__}.{name} has nowhere to go in AmbiguityRequest, so a "
                f"model behind door 2 would never be told it"
            )
    assert Ambiguity.model_config.get("extra") == "forbid"


def test_every_tier_four_question_can_actually_cross_the_door():
    """A129 — the test above compares field *names*, and names were not the problem.

    `AmbiguityRequest` is documented as "the union of what the three `*Asked` types carry",
    and it accepted **one** of the three. Two failed on their *values*:

        ParamAsked  candidates=[None]                Input should be a valid string
        SourceAsked candidates=['star_align.bam']    not a contract id

    Door 2 is exactly what Plan 2 Task 5 opens, so today only producer questions can be asked
    of a model. A name-shaped assertion could never see it: every field had somewhere to go,
    and two kinds still could not get through. Construct one of each instead.
    """

    from comeni_core.artifact.egress import AmbiguityRequest
    from comeni_core.plan.decision import ParamAsked, ProducerAsked, SourceAsked

    for asked in (
        ParamAsked(node_id="star_align", subject="seq_platform", candidates=[None]),
        # Shaped exactly as `resolve.py:215` builds one — `type_id` and `required` included,
        # because a source question that does not say what type it is asking about is not a
        # question anybody asks. Omitting them here produced a second, spurious failure and
        # would have made this test assert something the resolver never emits.
        SourceAsked(
            node_id="samtools_sort",
            subject="source:reads",
            candidates=["star_align.bam", "trimgalore.reads"],
            type_id="alignment.bam",
            required=["coordinate_sorted"],
        ),
        ProducerAsked(
            node_id="star_align",
            subject="producer:alignment.bam",
            candidates=["nf-core/star/align@1.11.0"],
        ),
    ):
        payload = asked.model_dump()
        payload.pop("kind", None)
        AmbiguityRequest(**payload)


# --- Plan 1.10 Task 11: Pipeline is door 4's payload ----------------------------------


def test_publication_carries_a_pipeline():
    """The artifact a person reads before publishing and the thing that crosses the boundary
    are one document. `PublishBundle` held goal + IR + decisions + lockfile — the same
    information one layer less assembled, and one more thing that could disagree with what
    was on disk."""
    from comeni_core.artifact.pipeline import Pipeline

    assert egress.DOORS["publication"] is Pipeline


def test_publish_bundle_is_gone():
    """Retired, not deprecated. A type nothing constructs is a type that drifts, and its name
    was load-bearing rationale in eight other files — rationale citing a deleted type reads as
    authoritative and cannot be checked."""
    assert not hasattr(egress, "PublishBundle")


def test_the_publication_payload_is_frozen():
    """`EgressPayload` sets `frozen=True`, so what was reviewed is what is sent.

    `gate` and `emitted` are stamped with `model_copy` rather than assigned, which is the
    right shape for them anyway: both are evidence about a finished pipeline, and evidence
    should not be edited in place.
    """
    import pytest
    from comeni_core.artifact.pipeline import Pipeline
    from comeni_core.goal.asked import Goal
    from pydantic import ValidationError

    # A real `goal` so the refusal is the *frozen assignment*, not a missing field (A48 made
    # `goal` required, and a bare `Pipeline()` would now raise for the wrong reason).
    frozen = Pipeline(goal=Goal())
    with pytest.raises(ValidationError):
        frozen.gate = "test"


def test_pipeline_holds_no_registry():
    """`registry.py` carries a mapping and says it is legal because a `Registry` is not
    payload-reachable. That sentence became load-bearing the moment the artifact itself
    crossed door 4: materialisation must copy values, never hold the thing it read them from.
    """
    import re

    from comeni_core.artifact.pipeline import Pipeline

    # Word boundaries, not `in`. The first version matched `RegistryProvenance` and reported
    # `Pipeline.registry holds a Registry` — the same substring trap `test_pipeline_totality`
    # hit on the same word, which is what makes it worth a comment rather than a quiet fix.
    forbidden = re.compile(r"\b(Registry|ModuleContract|Vocabulary|MeasurementRegistry)\b")
    for model in reachable(Pipeline):
        for name, annotation in _serialised_hints(model).items():
            held = forbidden.search(str(annotation))
            assert held is None, f"{model.__name__}.{name} holds a {held.group()}"


def test_a_computed_field_cannot_cross_a_door_unchecked():
    """A57. `@computed_field` puts a key in the serialised JSON and lands in
    `model_computed_fields` — which no rule in this file consulted, because every one of them
    filtered on `model_fields`.

    The leaf allowlist was inverted from a blocklist precisely so that a shape nobody named
    could not be silence (A19, A20, A30). It was still a blocklist with respect to *where a
    value comes from*: the audit put a patient path into `PromptRequest`'s JSON this way with
    the whole file reporting 15 passed.
    """

    class Sneaky(egress.PromptRequest):
        @computed_field
        @property
        def context(self) -> str:
            return "/data/patients/PT-4471023/notes: BRCA1 c.68_69del"

    models = _payload_types() | {Sneaky}
    offenders = [
        problem
        for name, annotation in _serialised_hints(Sneaky).items()
        for problem in _leaf_problems(annotation, f"Sneaky.{name}", models)
    ]
    assert offenders, "a computed bare `str` crossed the door with no Mark and no complaint"


def test_no_payload_replaces_its_own_dump():
    """A57, the other half — and a different shape, which is the finding's real content.

    A `@computed_field` has a return annotation, so it can go through the leaf check above.
    A `@model_serializer` replaces the dump wholesale: there is no per-key annotation left to
    check, and the audit returned `{"site": "/mnt/phi/…", "notes": "BRCA1 c.68_69del"}` from
    one with 15 passed. Nothing can be checked about it, so the only enforceable rule is that
    a payload may not define one.
    """
    for payload in sorted(_payload_types(), key=lambda m: m.__name__):
        declared = dict(payload.__pydantic_decorators__.model_serializers)
        assert not declared, (
            f"{payload.__name__} defines @model_serializer {sorted(declared)} — the dump no "
            "longer corresponds to the fields this file checks, so nothing here can see what "
            "crosses the door"
        )


# --- Round four's carried egress findings: A63, A65, A66 ---------------------------------


def test_an_enum_with_a_missing_hook_is_not_a_declared_shape():
    """A63, issue #27. `_leaf_problems` returned `[]` for any `Enum`, on the premise that an
    enum is closed vocabulary. `Enum._missing_` is the documented hook for accepting
    *undeclared* values and can synthesise a member from anything — the reviewer added such a
    field to `GateFailure` (door 3) and crossed an arbitrary path string with 15 passed.

    So "an enum is closed" is a claim about a class, not about the type, and the check has to
    read the class to know which it has.
    """

    class Sneaky(enum.StrEnum):
        KNOWN = "known"

        @classmethod
        def _missing_(cls, value):  # pragma: no cover — never called; its presence is the point
            return cls.KNOWN

    assert _leaf_problems(Sneaky, "Probe.field", set()), "an open enum passed as closed vocabulary"


def test_an_ordinary_enum_is_still_a_declared_shape():
    """The negative. Every closed vocabulary in this repository is a `StrEnum`, and refusing
    them would be a check nobody could satisfy."""
    assert _leaf_problems(Tier, "Probe.field", set()) == []
    assert _leaf_problems(ValueSource, "Probe.field", set()) == []


def test_a_missing_hook_on_a_base_class_is_caught_too():
    """`_missing_` inherited from a base below `Enum` is the same hook one level up, and a
    check that reads only `vars(cls)` would miss it."""

    class OpenBase(enum.StrEnum):
        @classmethod
        def _missing_(cls, value):  # pragma: no cover
            return None

    class Derived(OpenBase):
        KNOWN = "known"

    assert _leaf_problems(Derived, "Probe.field", set())


def test_the_ambiguity_kinds_tuple_is_the_subclass_set():
    """A65, issue #29. The door-totality test loops over a literal tuple in `decision.py`,
    and its docstring claims "a fourth kind added without a slot would fail" — true only if
    the author also edits the tuple. The reviewer added a fourth `Ambiguity` subclass not in
    the tuple and got 15 passed: the check is live and its input was incomplete.
    """
    from comeni_core.plan.decision import Ambiguity, AmbiguityKinds

    assert set(AmbiguityKinds) == set(Ambiguity.__subclasses__()), (
        "a kind exists that the totality check never sees"
    )


BUILDERS = frozenset({"PipelineIR", "IRNode", "IREdge", "ParamBinding", "ResolvedValue"})
"""The IR, which is door **3**'s payload and is deliberately mutable.

A66 says every payload-reachable model should be frozen, and that is right for door 4 and
wrong for door 3 — because door 3's payload is *the thing being repaired*. `RepairRequest.ir`
is handed to a model precisely so the IR can change, and invariant 5 says repair patches the
IR and re-emits. Freezing these breaks 109 tests, which is the resolver saying the same thing
less politely: it builds an `IRNode` and then fills its parameters in.

So the rule is scoped to the door it is about. `Pipeline` is door 4 — publication, the door
with no undo — and what a person reviewed must be what is sent. An IR that changes between
review and repair is the mechanism working."""


def test_every_publication_payload_model_is_frozen():
    """A66, issue #30. `EgressPayload` was frozen and every nested model was a plain
    `BaseModel`, so `Emitted.files[0].digest` could be reassigned after review — on the one
    field that *is* the self-verification evidence.

    `test_the_publication_payload_is_frozen` asserted the top level and generalised in its
    docstring to "what was reviewed is what is sent". Publication is the door with no undo,
    so the gap between the claim and the check mattered most exactly there.
    """
    mutable = sorted(
        model.__name__
        for model in reachable(egress.DOORS["publication"])
        if not model.model_config.get("frozen", False)
    )
    assert mutable == [], (
        "these models are reachable from the publication payload and can be mutated after "
        f"review; that door has no undo:\n  {', '.join(mutable)}"
    )


def test_the_only_unfrozen_payload_models_are_the_ir_builders():
    """The residue, named so it is a decision rather than an oversight — and pinned, so a
    *new* mutable model cannot join them quietly."""
    mutable = {
        model.__name__
        for model in _payload_types()
        if not model.model_config.get("frozen", False)
    }
    assert mutable == BUILDERS, (
        "the unfrozen set moved. Anything outside the IR that a payload can reach must be "
        f"frozen, or listed in BUILDERS with its reason:\n  {sorted(mutable ^ BUILDERS)}"
    )


# --- A64, issue #28: a declared ID alias that validates nothing is a `str` with a label ---


@pytest.mark.parametrize(
    "alias, bad, why",
    [
        ("NodeId", "patient PT-4471, /data/S1_R1.fastq.gz", "a path and an identifier"),
        ("PortName", "dx: carcinoma", "a colon and a space"),
        ("StateName", "dx: carcinoma\nnotes: see /mnt/phi/4471.pdf", "a newline"),
        ("MeasurementId", "/data/patients/PT-4471023/S1.fastq.gz", "a path"),
        ("ModuleKey", "notes: see /mnt/phi/4471.pdf", "a path"),
        ("Digest", "not-a-digest: PT-4471023", "not a digest at all"),
        ("Subject", "dx: carcinoma\nnotes: /mnt/phi/4471.pdf", "a newline"),
        ("DecisionKey", "a\nb", "a newline"),
        ("LayerName", "x\ny", "a newline"),
    ],
)
def test_a_declared_id_alias_refuses_free_text(alias, bad, why):
    """A64, issue #28. Invariant 14 says every string on a payload is *"a declared ID alias
    or marked `Mark.FREE_TEXT`"*, and nine of the aliases were `Annotated[str, Mark.X]` with
    no `AfterValidator` — so "a declared ID alias" meant "a `str` with a label".

    On the **unmodified tree** the reviewer crossed door 2 with a patient identifier as a
    `node_id`, a variant as a `subject` and clinical notes with an embedded newline as a
    `state`, and door 4 with `digest='not-a-digest: PT-4471023'`. All serialised verbatim.
    This generalises A3, which was recorded for `PARAM_LITERAL` alone.
    """
    from comeni_core.spell import marks
    from pydantic import TypeAdapter

    with pytest.raises(ValidationError):
        TypeAdapter(getattr(marks, alias)).validate_python(bad)


@pytest.mark.parametrize(
    "alias, good",
    [
        ("NodeId", "star_align"),
        ("PortName", "reads"),
        ("StateName", "coordinate_sorted"),
        ("MeasurementId", "read_length"),
        ("ModuleKey", "nf-core/star/align"),
        ("Digest", "sha256:" + "a" * 64),
        ("Subject", "seq_platform"),
        ("DecisionKey", "star_align.seq_platform"),
        ("LayerName", "comeni-registry-examples"),
    ],
)
def test_a_declared_id_alias_accepts_what_the_repository_writes(alias, good):
    """The negative that keeps every validator above honest. A shape check tight enough to
    refuse a real value is a check somebody has to disable, and a disabled check is worse
    than none — which is `_computed_over`'s `paired-end` lesson, one layer down."""
    from comeni_core.spell import marks
    from pydantic import TypeAdapter

    assert TypeAdapter(getattr(marks, alias)).validate_python(good) == good


def test_every_mark_carries_a_validator_or_is_listed_as_a_label():
    """The residue, pinned. A `Mark` with no validator is legitimate only if somebody decided
    it, and this is what turns that into a decision."""
    from comeni_core.spell import marks

    unvalidated = sorted(
        name
        for name, alias in vars(marks).items()
        if name[0].isupper()
        and typing.get_origin(alias) is typing.Annotated
        and any(isinstance(m, Mark) for m in getattr(alias, "__metadata__", ()))
        and not any(
            type(m).__name__ == "AfterValidator" for m in getattr(alias, "__metadata__", ())
        )
    )
    assert unvalidated == sorted(marks.LABEL_ONLY), (
        "a declared ID alias with no validator is a `str` with a label. Give it one, or add "
        f"it to `marks.LABEL_ONLY` with the reason:\n  {unvalidated}"
    )


def test_the_door_carries_what_the_forge_measured_a_model_needs():
    """Not a shape check — a content one.

    The forge's prompt search (`docs/notes/journal/2026-08-17-prompt-search.md`) measured a local
    model going from 69% to 88% on three fixes, and two of them were **the question did not
    say what it was about** and **the evidence was not readable**. Door 2 projects a tier-4
    question to a model. A door that carries candidates and nothing else rebuilds the 69%
    configuration on the build path, having already paid to learn it.

    `closed` is here for the third measurement: opening a closed field was the *worst*
    configuration tested, six points below closing it, so whether the candidate list binds
    is something the model must be told rather than left to infer.
    """
    from comeni_core.artifact.egress import AmbiguityRequest

    for needed in ("what", "why_open", "closed", "evidence"):
        assert needed in AmbiguityRequest.model_fields, (
            f"{needed} does not cross door 2, so a tier-4 model call is the configuration "
            f"the forge measured at 69%"
        )
