"""Invariant 14: data leaves through four declared doors and no others.

The doors are listed here, literally, on purpose. Adding one means editing a file
whose contents say "these are all the ways data leaves this building" — which is
the moment a person should be thinking, and this test is what makes them.
"""

import typing

from comeni_core import egress
from pydantic import BaseModel

DOORS = {"goal_extraction", "tier4_resolution", "compiler_repair", "publication"}

# Free text is the taint source. Exactly two fields may carry it, and both are
# named here. A third requires editing this line.
FREE_TEXT_FIELDS = {
    ("PromptRequest", "prompt"),
    ("GateFailure", "tool_message"),
}


def _payload_types() -> set[type[BaseModel]]:
    return {
        obj
        for obj in vars(egress).values()
        if isinstance(obj, type)
        and issubclass(obj, egress.EgressPayload)
        and obj is not egress.EgressPayload
    }


def _mentions(annotation: object, marker: object) -> bool:
    """Walk an annotation tree. `Text | None` hides its metadata one level down."""
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
    origin = typing.get_origin(annotation)
    if origin is not None and isinstance(origin, type) and issubclass(origin, dict):
        return True
    if getattr(annotation, "__metadata__", None):
        return any(_mentions_mapping(arg) for arg in typing.get_args(annotation)[:1])
    return any(_mentions_mapping(arg) for arg in typing.get_args(annotation))


def _fields(model: type[BaseModel], marker: object) -> set[tuple[str, str]]:
    hints = typing.get_type_hints(model, include_extras=True)
    return {
        (model.__name__, name)
        for name, annotation in hints.items()
        if name in model.model_fields and _mentions(annotation, marker)
    }


def test_the_doors_are_exactly_four():
    assert set(egress.DOORS) == DOORS


def test_every_door_declares_an_egress_payload():
    for name, payload in egress.DOORS.items():
        assert issubclass(payload, egress.EgressPayload), name


def test_free_text_lives_only_where_declared():
    found: set[tuple[str, str]] = set()
    for payload in _payload_types():
        found |= _fields(payload, egress.FreeText)
    assert found == FREE_TEXT_FIELDS


def test_payloads_forbid_unknown_fields():
    for payload in _payload_types():
        assert payload.model_config.get("extra") == "forbid", payload.__name__


def test_no_payload_carries_an_undeclared_string():
    """Every string is either a declared ID alias or explicitly marked FreeText.

    Without this, `user_note: str` sails through every other test in this file — it
    carries no FreeText marker to catch and no `Any` to forbid — and a prompt fits in
    it perfectly. Found by running the plan's own break-the-guard step, which is what
    that step is for.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _has_bare_str(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are plain `str`; annotate them as an ID type or as FreeText: "
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


def test_no_payload_carries_an_untyped_container():
    """A dict[str, Any] would defeat the whole thing, so no payload may declare one."""
    offenders = []
    for payload in _payload_types():
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _mentions(annotation, typing.Any):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == []
