"""One writer for every change to intent and facts (Part I.0 spec §5.1).

The person's click or edit, the chat model's reply and a stage's own handler all arrive as a
`DecisionChange` and are written here, through `services.decisions`, so there is one path and
one set of checks: an undeclared type, tool or parameter is refused with `MI0204`, a value a
measurement refuses with `MI0208`, and nothing is written for either."""

from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Site
from mendel_authoring.decisions import ActorKind, FactOrigin, InputDecision
from mendel_authoring.payloads import DecisionChange, source_of

from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import decisions, registry


def _revision(draft_id: str) -> int:
    with session_scope() as db:
        return db.get(PipelineDraft, draft_id).decision_revision


def _type(stack, type_id: str) -> None:
    if type_id not in registry.builder_types(stack):
        raise ValueError(coded("MI0204", f"{type_id} is not a type this registry declares"))


def _tool(stack, contract: str) -> None:
    try:
        stack.registry.get(contract)
    except (KeyError, ValueError) as refused:
        raise ValueError(
            coded("MI0204", f"{contract} is not a tool this registry declares")
        ) from refused


def _parameter(stack, name: str) -> None:
    if not any(name == p.name for c in stack.registry.all() for p in c.params):
        raise ValueError(coded("MI0204", f"no step declares a setting called {name}"))


def _measurement(stack, subject: str, value) -> None:
    try:
        stack.measurements.get(subject)
        if value is not None:
            stack.measurements.check(subject, value)
    except (ValueError, KeyError, TypeError) as refused:
        raise ValueError(coded("MI0208", f"that answer does not fit {subject}")) from refused


def _role(stack, role: str) -> None:
    if not any(role in c.roles for c in stack.registry.all()):
        raise ValueError(coded("MI0204", f"no step fills a role called {role}"))


def _port(stack, consumer: str, port: str) -> None:
    _tool(stack, consumer)
    if not any(p.name == port for p in stack.registry.get(consumer).consumes):
        raise ValueError(coded("MI0204", f"{consumer} reads nothing called {port}"))


def check(change: DecisionChange) -> None:
    """Refuse what names something undeclared, before anything moves (`MI0204`, `MI0208`)."""
    stack = registry.stack()
    kind, subject = change.kind, change.subject
    if kind == "measurement":
        _measurement(stack, subject, None if change.retract else change.value)
    elif kind in ("want", "require", "pin", "producer"):
        _type(stack, subject)
        if kind == "pin" and not change.retract:
            _tool(stack, str(change.value))
    elif kind == "parameter":
        _parameter(stack, subject)
    elif kind == "role":
        _role(stack, subject)
    elif kind == "exclude":
        _type(stack, subject)
        _tool(stack, str(change.value))
    elif kind == "source":
        _port(stack, *source_of(subject))
        if not change.retract:
            _tool(stack, str(change.value))


def retracts_something(draft_id: str, change: DecisionChange) -> bool:
    """Whether a retraction has anything to retract (review I5): one that does not is no change,
    and the waiting question is left exactly as it was."""
    current = decisions.read(draft_id)
    subject = change.subject
    if change.kind == "measurement":
        return any(f.subject == subject and f.origin is not FactOrigin.OPEN
                   for f in current.facts)
    if change.kind == "input":
        return any((i.key == subject or i.type_id == subject)
                   and (i.present or i.origin is not FactOrigin.OPEN) for i in current.inputs)
    if change.kind in ("want", "require"):
        return any(w.type_id == subject and w.present for w in current.wants)
    if change.kind in ("pin", "producer"):
        return any(p.site.type_id == subject and p.contract for p in current.producers)
    if change.kind == "parameter":
        return any(p.name == subject and p.value is not None for p in current.parameters)
    if change.kind == "role":
        return any(r.role == subject and r.absent for r in current.roles)
    if change.kind == "exclude":
        return any(e.site == _site(change) and e.contract == change.value and e.excluded
                   for e in current.exclusions)
    if change.kind == "source":
        consumer, port = source_of(subject)
        return any((s.consumer, s.port) == (consumer, port) and s.producer
                   for s in current.sources)
    if change.kind == "asked":
        key = " ".join(subject.split()).casefold()
        return any(" ".join(a.phrase.split()).casefold() == key
                   for a in decisions.read_asked(draft_id))
    return True


def _site(change: DecisionChange) -> Site:
    return Site(type_id=change.subject, states=frozenset(change.states))


def _apply_input(draft_id: str, change: DecisionChange, stack, *, said, heard) -> bool:
    """Apply an input answer; whether it wrote a decision."""
    current = decisions.read(draft_id)
    old = next(
        (i for i in current.inputs if i.key == change.subject or i.type_id == change.subject),
        None,
    )
    type_id = old.type_id if old else change.subject
    _type(stack, type_id)
    if change.retract:
        if old is None or (not old.present and old.origin is FactOrigin.OPEN):
            return False
        if old.present:
            decisions.withdraw_input(draft_id, old.key, who=said["who"])
        else:
            # *I don't have one*, forgotten (review I5): nobody knows again.
            decisions.set_input(
                draft_id,
                old.model_copy(update={"present": False, "origin": FactOrigin.OPEN}),
                **said,
            )
        return True
    if change.value is not None and type(change.value) is not bool:
        raise ValueError(coded("MI0208", "an input answer must say whether you have it"))
    decisions.set_input(
        draft_id,
        InputDecision(
            key=old.key if old else type_id,
            type_id=type_id,
            name=old.name if old else None,
            states=list(change.states) or (old.states if old else []),
            # **`None` is *unknown*, not *have it*** — the correction's meaning since
            # Part F: `True` held, `False` not held, `None` nobody knows.
            present=change.value is True,
            origin=FactOrigin.OPEN if change.value is None else FactOrigin.PERSON_SAID,
        ),
        **said,
        **heard,
    )
    return True


def apply(draft_id: str, change: DecisionChange, *, who: str) -> bool:
    """Write one change; whether the decisions moved. Retracting what is not there is no
    change (Review Focus 5 of plan A)."""
    stack = registry.stack()
    before = _revision(draft_id)
    said = {
        "who": who,
        "actor_kind": ActorKind(change.actor),
    }
    heard = {"heard": change.heard, "heard_seq": change.heard_seq}
    kind, subject = change.kind, change.subject

    if kind == "measurement":
        _measurement(stack, subject, None if change.retract else change.value)
        current = {f.subject: f for f in decisions.read(draft_id).facts}
        if change.retract and current.get(subject) is None:
            return False
        decisions.set_fact(
            draft_id,
            subject,
            None if change.retract else change.value,
            **said,
            **({} if change.retract else heard),
        )
    elif kind == "input":
        if not _apply_input(draft_id, change, stack, said=said, heard=heard):
            return False
    elif kind == "want":
        _type(stack, subject)
        if change.retract:
            return decisions.retract_want(draft_id, subject, **said) is not None
        decisions.set_want(draft_id, subject, **said, **heard)
    elif kind == "require":
        _type(stack, subject)
        unknown = [s for s in change.states if s not in stack.vocabulary.types[subject]]
        if unknown:
            raise ValueError(coded("MI0204", f"{subject} declares no state {unknown[0]}"))
        decisions.require_states(
            draft_id, subject, [] if change.retract else change.states, **said, **heard
        )
    elif kind in ("pin", "producer"):
        _type(stack, subject)
        site = Site(type_id=subject, states=frozenset(change.states))
        pinned = {
            (p.site.type_id, p.site.states): p.contract for p in decisions.read(draft_id).producers
        }
        if change.retract or kind == "producer":
            if pinned.get((subject, frozenset(change.states))) is None:
                return False
            decisions.release_producer(draft_id, site, who=who)
        else:
            _tool(stack, str(change.value))
            decisions.pin_producer(draft_id, site, str(change.value), **said, **heard)
    elif kind == "parameter":
        _parameter(stack, subject)
        if change.retract:
            current = {p.name: p.value for p in decisions.read(draft_id).parameters}
            if current.get(subject) is None:
                return False
            decisions.release_parameter(draft_id, subject, who=who)
        else:
            decisions.set_parameter(draft_id, subject, change.value, **said, **heard)
    elif kind == "asked":
        if change.retract:
            return decisions.retract_asked(draft_id, subject, **said) is not None
        decisions.set_asked(draft_id, subject, **said, **heard)
    elif kind in ("role", "exclude", "source"):
        check(change)
        if change.retract:
            if not retracts_something(draft_id, change):
                return False
            family = {"role": "role", "exclude": "exclusion", "source": "source"}[kind]
            key = (decisions.exclusion_key(_site(change), change.value) if kind == "exclude"
                   else subject)
            decisions.release_intent(draft_id, family, key, who=who)
        elif kind == "role":
            decisions.switch_off_role(draft_id, subject, **said)
        elif kind == "exclude":
            decisions.exclude_producer(draft_id, _site(change), str(change.value), **said)
        else:
            decisions.pin_source(draft_id, *source_of(subject), str(change.value), **said)
    elif kind == "retain":
        decisions.retain_fact(draft_id, subject, who=who)
    elif kind == "observation":
        decisions.select_observation(draft_id, subject, change.observation_id, who=who)
    moved = _revision(draft_id) != before
    if moved:
        from mendel_api.services import suggestions

        suggestions.stale_for(draft_id, change)
    return moved


def describe(change: DecisionChange) -> str:
    """The change in a person's words, for a receipt or a suggestion card."""
    from mendel_api.authoring.types import FactKind
    from mendel_api.services import explain

    stack = registry.stack()
    subject = change.subject
    if change.kind == "measurement":
        label = subject.replace("_", " ")
        return f"forgot the {label}" if change.retract else f"{label} is {change.value}"
    if change.kind == "input":
        name = explain.name_of(stack, FactKind.INPUT, subject)
        if change.retract:
            return f"forgot that you have the {name}"
        return f"you don't have the {name}" if change.value is False else f"you have the {name}"
    if change.kind == "want":
        name = explain.name_of(stack, FactKind.INPUT, subject)
        return f"no longer wanting the {name}" if change.retract else f"you want the {name}"
    if change.kind == "require":
        return f"the {explain.name_of(stack, FactKind.INPUT, subject)} must be " + ", ".join(
            change.states
        )
    if change.kind in ("pin", "producer"):
        if change.retract or change.kind == "producer":
            return f"released the tool choice for {subject}"
        return f"{change.value} makes the {explain.name_of(stack, FactKind.INPUT, subject)}"
    if change.kind == "parameter":
        return f"cleared {subject}" if change.retract else f"{subject} is {change.value}"
    if change.kind == "asked":
        # The subject is the person's own phrase, which need not read after "you asked for"
        # (#327: "you asked for also I want …").
        return f'not offered here: "{subject}"'
    if change.kind == "role":
        role = subject.replace("_", " ")
        return f"{role} back on" if change.retract else f"no {role} here"
    if change.kind == "exclude":
        tool = _process(stack, str(change.value))
        return (f"{tool} allowed again" if change.retract
                else f"not {tool} for the {explain.name_of(stack, FactKind.INPUT, subject)}")
    if change.kind == "source":
        consumer, port = source_of(subject)
        if change.retract:
            return f"{_process(stack, consumer)}'s {port} back to the engine's choice"
        return (f"{_process(stack, consumer)} reads its {port} from "
                f"{_process(stack, str(change.value))}")
    if change.kind == "retain":
        return f"kept your selected answer for {subject}"
    return f"selected the evidence for {subject}"


def _process(stack, contract: str) -> str:
    try:
        return stack.registry.get(contract).nf_process
    except (KeyError, ValueError):
        return contract
