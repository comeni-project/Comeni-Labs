"""A model's reply, admitted against the registry and sorted into heard and suggested changes
(Part I.0 spec §5.3, §7).

**Heard** when a change quotes the person and the quote is in one of their turns
(`mendel_authoring.heard.find`): it may be recorded. **Suggested** otherwise: offered, and
recorded only when the person clicks. A want is always issued, because gathering needs one, and
the goal card confirms it; `not_offered` is heard or dropped, never suggested — claiming someone
asked for what they did not is the one thing it must not do."""

from collections.abc import Sequence
from dataclasses import dataclass

from comeni_core.diagnostics import coded
from mendel_authoring import heard as heard_mod
from mendel_authoring.payloads import DecisionChange
from sqlalchemy import select

from mendel_api.authoring.types import ChatReply, TurnRole, Understanding
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringTurn


@dataclass(frozen=True)
class Issued:
    heard: list[DecisionChange]
    suggested: list[DecisionChange]
    dropped: list[str]
    """`not_offered` phrases whose quote did not check, for the call's log."""


def person_turns(session_id: str) -> list[tuple[int, str]]:
    """Every turn the person typed in this session, in order: what a quote is checked against."""
    with session_scope() as db:
        rows = db.scalars(
            select(PipelineAuthoringTurn)
            .where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.role == TurnRole.PERSON,
            )
            .order_by(PipelineAuthoringTurn.seq)
        ).all()
        return [(row.seq, row.text or "") for row in rows]


def admit(reply: Understanding | ChatReply, stack) -> Understanding | ChatReply:
    """Every id against what the registry declares, before anything reads the reply (`MI0204`).
    A value a measurement refuses is refused the same way: the reply named something this
    registry cannot hold."""
    types, measurements = stack.vocabulary.types, stack.measurements
    unknown: list[str] = []

    def _type(type_id: str, states=()) -> None:
        if type_id not in types:
            unknown.append(f"type {type_id}")
            return
        unknown.extend(f"state {s} on {type_id}" for s in states if s not in types[type_id])

    for item in reply.wants:
        _type(item.type)
    for item in reply.inputs:
        _type(item.type)
    for item in reply.requires:
        _type(item.type, item.states)
    for item in reply.facts:
        if item.subject in types:
            continue
        try:
            measurements.check(item.subject, item.value)
        except (ValueError, KeyError, TypeError) as refused:
            unknown.append(f"measurement {item.subject} ({refused})")
    for item in getattr(reply, "pins", []):
        _type(item.type)
        try:
            stack.registry.get(item.tool)
        except (KeyError, ValueError):
            unknown.append(f"tool {item.tool}")
    for item in getattr(reply, "parameters", []):
        if not any(item.name == p.name for c in stack.registry.all() for p in c.params):
            unknown.append(f"setting {item.name}")
    for item in getattr(reply, "retract", []):
        if item.subject not in types and item.subject not in measurements.measurements:
            unknown.append(f"subject {item.subject}")
    if unknown:
        raise ValueError(
            coded("MI0204", "the reply names something this registry does not declare")
            + "".join(f"\n  {u}" for u in unknown)
        )
    return reply


def _changes(reply, stack, wanted: frozenset[str]) -> list[tuple[DecisionChange, str | None]]:
    """Each item as the change it asks for, with its quote."""
    types = stack.vocabulary.types
    out: list[tuple[DecisionChange, str | None]] = []
    for item in reply.wants:
        out.append((DecisionChange(kind="want", subject=item.type), item.quote))
    for item in reply.inputs:
        out.append((DecisionChange(kind="input", subject=item.type, value=True), item.quote))
    for item in reply.facts:
        if item.subject in types:
            held = item.value if isinstance(item.value, bool) else True
            out.append((DecisionChange(kind="input", subject=item.subject, value=held), item.quote))
        else:
            out.append(
                (
                    DecisionChange(kind="measurement", subject=item.subject, value=item.value),
                    item.quote,
                )
            )
    for item in reply.requires:
        out.append(
            (
                DecisionChange(kind="require", subject=item.type, states=sorted(item.states)),
                item.quote,
            )
        )
    for item in getattr(reply, "pins", []):
        out.append((DecisionChange(kind="pin", subject=item.type, value=item.tool), item.quote))
    for item in getattr(reply, "parameters", []):
        out.append(
            (DecisionChange(kind="parameter", subject=item.name, value=item.value), item.quote)
        )
    for item in getattr(reply, "retract", []):
        if item.subject in types:
            kind = "want" if item.subject in wanted else "input"
        else:
            kind = "measurement"
        out.append((DecisionChange(kind=kind, subject=item.subject, retract=True), item.quote))
    return out


def issue(
    reply: Understanding | ChatReply,
    *,
    turns: Sequence[tuple[int, str]],
    stack,
    invocation_id: str | None,
    wanted: frozenset[str] = frozenset(),
) -> Issued:
    """Sort an admitted reply into heard and suggested changes. `wanted` is what the goal wants
    now, so retracting a type knows whether it was a want or an input."""
    pairs = _changes(reply, stack, wanted)
    # **One subject said two ways is not heard** (Review Focus 3): both are offered.
    values: dict[tuple[str, str], set] = {}
    for change, _quote in pairs:
        values.setdefault((change.kind, change.subject), set()).add(
            repr((change.value, change.retract, tuple(change.states)))
        )
    contested = {key for key, seen in values.items() if len(seen) > 1}

    heard, suggested = [], []
    for change, quote in pairs:
        seq = heard_mod.find(quote, turns)
        stamped = change.model_copy(update={"actor": "model", "invocation_id": invocation_id})
        if seq is not None and (change.kind, change.subject) not in contested:
            heard.append(stamped.model_copy(update={"heard": quote, "heard_seq": seq}))
        elif change.kind == "want":
            heard.append(stamped)
        else:
            suggested.append(stamped)

    dropped = []
    for item in reply.not_offered:
        seq = heard_mod.find(item.quote, turns)
        if seq is None:
            dropped.append(item.quote)
            continue
        heard.append(
            DecisionChange(
                kind="asked",
                subject=item.quote,
                heard=item.quote,
                heard_seq=seq,
                actor="model",
                invocation_id=invocation_id,
            )
        )
    return Issued(heard=heard, suggested=suggested, dropped=dropped)
