"""What is known about a session, from the store, for every conversational prompt (Part I.0 spec
§6.3). The rendering is `mendel_authoring.memory`'s; this gathers what it renders."""

from mendel_authoring.decisions import FactOrigin
from mendel_authoring.memory import Known, KnownItem, render

from mendel_api.authoring.types import FactKind
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import authoring_decisions, decisions, explain, gaps, registry

_SOURCE = {
    FactOrigin.PERSON_SAID: "said",
    FactOrigin.MEASURED: "measured",
    FactOrigin.MODEL_READ: "read_by_ai",
    FactOrigin.OPEN: "open",
}


def _value(value) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def _suggested(session_id: str) -> list[str]:
    """The model's suggestions still waiting for a click, in words."""
    return []


def of(session_id: str) -> Known:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft_id = row.draft_id
    stack = registry.stack()
    current = decisions.read(draft_id)
    heard = decisions.heard_of(draft_id)

    def words(family: str, key: str) -> str | None:
        found = heard.get((family, key))
        return found[0] if found else None

    wants = [w for w in current.wants if w.present]
    open_ = gaps.gaps([w.type_id for w in wants], authoring_decisions.facts(draft_id), stack)
    return Known(
        wants=[KnownItem(label=explain.name_of(stack, FactKind.INPUT, w.type_id),
                         # A want nobody quoted is the model's reading until *That's right*.
                         source="said" if words("want", w.type_id) else "model",
                         heard=words("want", w.type_id)) for w in wants],
        constraints=[
            *[KnownItem(label=explain.name_of(stack, FactKind.INPUT, w.type_id),
                        value=", ".join(w.states), source="said") for w in wants if w.states],
            *[KnownItem(label=f"tool for {p.site.type_id}", value=p.contract, source="said")
              for p in current.producers if p.contract],
            *[KnownItem(label=p.name, value=_value(p.value), source="said")
              for p in current.parameters if p.value is not None],
        ],
        not_offered=[a.phrase for a in decisions.read_asked(draft_id)],
        inputs=[KnownItem(label=explain.name_of(stack, FactKind.INPUT, i.type_id),
                          value=None if i.present else "not held",
                          source=_SOURCE[i.origin], heard=words("input", i.key))
                for i in current.inputs],
        facts=[KnownItem(label=f.subject.replace("_", " "),
                         value=None if f.value is None else _value(f.value),
                         source=_SOURCE[f.origin], heard=words("fact", f.subject))
               for f in current.facts],
        suggested=_suggested(session_id),
        open=[] if isinstance(open_, gaps.Unreachable)
        else [explain.name_of(stack, g.kind, g.subject) for g in open_],
        confirmed=authoring_decisions.confirmed(draft_id),
    )


def text(session_id: str) -> str:
    return render(of(session_id))
