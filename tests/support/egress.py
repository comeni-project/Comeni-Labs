"""Shared egress declarations and helpers; collected tests remain separate."""

import enum
import importlib
import pkgutil
import types
import typing
from collections import abc

from comeni_core import egress as egress_package
from comeni_core.egress import boundaries as egress
from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import Mark
from pydantic import BaseModel

from support.walk import reachable

PIPELINE_DOORS = {
    "goal_extraction",
    "tier4_resolution",
    "compiler_repair",
    "publication",
    # Door 6, 14.7.7: the characteriser. The first door that carries data from a person's file,
    # at protection level 0 only. On the pipeline path because what it reads becomes the goal.
    "characterisation",
}
"""The pipeline path's doors, and *pipeline data leaves through these* stays checkable against
this set rather than against the whole list."""


FORGE_DOORS = {"forge_review"}
"""Registry authoring. Public tool documentation in, reviewed registry data out, and no `Goal`
anywhere in it — a different path with a different author and the same rules."""


DOORS = PIPELINE_DOORS | FORGE_DOORS


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
# **`ai_invocation.response` is not here, and should not be** (#182, 2026-09-29): a model's reply
# is stored, never sent — it crosses no door. It is a level-0 store, recorded in
# `docs/design/authoring-protocol.md`'s protection table and loosenings.
FREE_TEXT_FIELDS = {
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
    # Fifteenth and sixteenth, 2026-09-05, and they arrive with a **new door** rather than by a
    # refactor — the second time that has happened, after `override_reason`.
    #
    # `ReviewTurn.content` is the load-bearing one: a curator types it, at request time, and it
    # goes to a provider. That is what `AuthoringRequest.prompt` is on the pipeline side, and it
    # is precisely the leg the forge's 2026-08-17 exemption stood on — *it has no prompt*. The
    # chat is a prompt, so the exemption stopped covering it and a door was declared instead of
    # the argument being stretched.
    #
    # `ForgeReviewRequest.candidate` is the proposed contract or module as a reviewer sees it.
    # It is composed rather than typed by anybody, from vendored modules and registry files —
    # the same public bound that keeps `Excerpt` on this list honest.
    #
    # What is NOT here, deliberately: the generation dossier. It is composed entirely from
    # those same public sources, so the line drawn is *who authored the string* rather than
    # *how much text crosses*, and by that line generating a proposal is not a door.
    ("ReviewTurn", "content"),
    ("ForgeReviewRequest", "candidate"),
    # Seventeenth, 2026-09-09, and it is **the same field it replaced**. Door 1's payload grew
    # from `PromptRequest` — one prompt, one call — into `AuthoringRequest`, because the living
    # pipeline is a conversation and not a single extraction. `prompt` is still exactly what it
    # was: the string a person just typed, the single taint source invariant 14 is written
    # around. The name on the left changed; nothing new crosses here.
    ("AuthoringRequest", "prompt"),
    # Eighteenth, and it IS new: the bounded tail. A follow-up turn is only answerable with
    # what was already said, so prior turns are quoted back the way `ReviewTurn` does for door
    # 5 — and this is the pipeline path, where the same shape had to be argued for separately
    # rather than inherited.
    #
    # **What bounds it is that a turn is not a transcript.** The tail is capped (`CHAT_TAIL`,
    # the Forge's precedent), and a `MODEL` turn is text this system produced from typed data.
    # A `PERSON` turn is prose the person typed — the same author, the same door, one more
    # sentence of the same conversation `prompt` already carries.
    ("AuthoringTurn", "content"),
}


SAMPLE_FIELDS = {
    # The first, 14.7.7: the start of a sample, decoded to text, for the characteriser. **Not
    # free text, and counted apart on purpose**: free text is what a person typed or a tool
    # printed, and this is what a person's *file* holds. At most 8 KB and 200 lines, which the
    # type enforces (`marks.SampleText`), and only at protection level 0.
    ("CharacteriseRequest", "excerpt"),
}
"""Every field that may hold data from a person's file. This set is the count."""


def _payload_types() -> set[type[BaseModel]]:
    """Walk registered payloads and every payload subclass in the egress package."""
    roots = set(egress.PAYLOADS.values())
    for module in pkgutil.iter_modules(egress_package.__path__, prefix="comeni_core.egress."):
        payload_module = importlib.import_module(module.name)
        roots |= {
            obj
            for obj in vars(payload_module).values()
            if isinstance(obj, type) and issubclass(obj, EgressPayload) and obj is not EgressPayload
        }
    return reachable(*roots)


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


def _marks_in(annotation: object) -> set[Mark]:
    """Every `Mark` anywhere in an annotation tree, containers and unions included."""
    found = {meta for meta in getattr(annotation, "__metadata__", ()) if isinstance(meta, Mark)}
    for arg in typing.get_args(annotation):
        found |= _marks_in(arg)
    return found
