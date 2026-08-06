"""Invariant 14: data leaves through four declared doors and no others.

The doors are listed here, literally, on purpose. Adding one means editing a file
whose contents say "these are all the ways data leaves this building" — which is
the moment a person should be thinking, and this test is what makes them.
"""

import enum
import types
import typing
from collections import abc

from comeni_core import egress
from comeni_core.marks import Mark
from pydantic import BaseModel

DOORS = {"goal_extraction", "tier4_resolution", "compiler_repair", "publication"}

_BINARY = (bytes, bytearray, memoryview)
"""No payload may carry a blob. A signature field on a lockfile is the obvious way this
arrives, and it is still a blob — sign the artifact beside the bundle, not inside it."""

# Free text is the taint source. Exactly two fields may carry it, and both are
# named here. A third requires editing this line.
FREE_TEXT_FIELDS = {
    ("PromptRequest", "prompt"),
    ("GateFailure", "tool_message"),
    # Reachable through RepairRequest.ir and PublishBundle. Model- or resolver-written
    # prose explaining a choice — genuinely free text, and named here rather than
    # exempted, because an audit found these riding along unexamined inside a nested
    # model the guard never opened.
    ("ResolvedValue", "reason"),
    ("DecisionRecord", "reason"),
}


def _payload_types() -> set[type[BaseModel]]:
    """Every model reachable from a declared payload, not just the payload itself.

    The first version returned only `EgressPayload` subclasses, and every check walked
    `typing.get_args`, which returns `()` at a nested `BaseModel`. So nothing ever looked
    inside `RepairRequest.ir`, and a payload serialised a patient path and an SSN while
    this file reported green. Transitive expansion is the fix; exempting nested models
    would be the hole.
    """
    roots = {
        obj
        for obj in vars(egress).values()
        if isinstance(obj, type)
        and issubclass(obj, egress.EgressPayload)
        and obj is not egress.EgressPayload
    }
    seen: set[type[BaseModel]] = set()
    queue = list(roots)
    while queue:
        model = queue.pop()
        if model in seen:
            continue
        seen.add(model)
        for annotation in typing.get_type_hints(model, include_extras=True).values():
            queue += [n for n in _nested_models(annotation) if n not in seen]
    return seen


def _nested_models(annotation: object) -> list[type[BaseModel]]:
    """Every BaseModel mentioned anywhere in an annotation, however deeply wrapped."""
    found = []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.append(annotation)
    for arg in typing.get_args(annotation):
        found += _nested_models(arg)
    return found


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


def _fields(model: type[BaseModel], marker: object) -> set[tuple[str, str]]:
    hints = typing.get_type_hints(model, include_extras=True)
    return {
        (model.__name__, name)
        for name, annotation in hints.items()
        if name in model.model_fields and _mentions(annotation, marker)
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
        hints = typing.get_type_hints(payload, include_extras=True)
        for name, annotation in hints.items():
            if name in payload.model_fields:
                offenders += _leaf_problems(annotation, f"{payload.__name__}.{name}", models)
    assert offenders == [], "these payload fields are not declared shapes:\n" + "\n".join(offenders)


def test_the_doors_are_exactly_four():
    assert set(egress.DOORS) == DOORS


def test_every_door_declares_an_egress_payload():
    for name, payload in egress.DOORS.items():
        assert issubclass(payload, egress.EgressPayload), name


def test_free_text_lives_only_where_declared():
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
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _has_bare_str(annotation):
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
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _mentions_mapping(annotation):
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
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _mentions_binary(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are binary blobs, which no rule in this file can inspect: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_an_untyped_container():
    """A dict[str, Any] would defeat the whole thing, so no payload may declare one."""
    offenders = []
    for payload in _payload_types():
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _mentions_any(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are `Any`, which defeats every other rule here: "
        + ", ".join(sorted(offenders))
    )
