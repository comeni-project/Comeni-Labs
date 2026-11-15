"""What the person does directly, beside the agent (#463): a change, a corrected fact, a tool
released, an edit on the canvas, a sample uploaded. Each is the person's, through the same
writer the agent's tools use, and the pipeline is built again so the canvas follows at once.
A write against a revision that moved is refused (`MI0201`), so the person and the agent never
overwrite each other unseen."""

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from mendel_authoring.blueprint import Blueprint
from mendel_authoring.decisions import FactOrigin
from mendel_authoring.intent import read_edit
from mendel_authoring.payloads import DecisionChange

from mendel_api.agent.build import resolve
from mendel_api.agent.read import Nothing
from mendel_api.agent.tools import ToolContext
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import changes, decisions, registry


def _draft_of(session_id: str) -> str:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        return row.draft_id


def _rebuild(session_id: str, draft_id: str, who: str) -> None:
    """The pipeline built again from the decisions, so the canvas shows the person's change."""
    resolve(ToolContext(draft_id=draft_id, session_id=session_id, who=who,
                        expected_revision=decisions.revision(draft_id)), Nothing())


def apply(session_id: str, change: DecisionChange, *, who: str,
          expected_revision: int | None = None) -> bool:
    """The person's change. Whether the decisions moved."""
    draft_id = _draft_of(session_id)
    if expected_revision is not None and decisions.revision(draft_id) != expected_revision:
        raise ValueError(coded("MI0201", "the pipeline changed since you last saw it; look "
                                         "again before changing it"))
    moved = changes.apply(draft_id, change.model_copy(update={"actor": "person"}), who=who)
    if moved:
        _rebuild(session_id, draft_id, who)
    return moved


def _values(before: DraftGraph, after: DraftGraph) -> list[DecisionChange]:
    """The settings typed on steps both graphs hold: set, or cleared."""
    was = {n.id: {p.name: p.value for p in n.params} for n in before.nodes}
    out: list[DecisionChange] = []
    for node in sorted(after.nodes, key=lambda n: n.id):
        old = was.get(node.id)
        if old is None:
            continue
        now = {p.name: p.value for p in node.params}
        out += [DecisionChange(kind="parameter", subject=name, value=value)
                for name, value in sorted(now.items()) if old.get(name) != value]
        out += [DecisionChange(kind="parameter", subject=name, retract=True)
                for name in sorted(old.keys() - now.keys())]
    return out


def edit(session_id: str, graph: DraftGraph, *, who: str, expected_revision: int) -> int:
    """A canvas edit (#395), read as what it means — a step removed, a tool swapped, a wire
    pinned, a value typed — and applied as the person's changes. A move is layout: nothing is
    written. Returns the draft's revision after."""
    draft_id = _draft_of(session_id)
    with session_scope() as db:
        draft = db.get(PipelineDraft, draft_id)
        if draft.revision != expected_revision:
            raise ValueError(coded("MI0201", "the pipeline changed since you last saw it"))
        before = DraftGraph.model_validate(draft.graph or {})
        stored = db.get(PipelineAuthoringSession, session_id).blueprint
    sites = Blueprint.model_validate(stored).sites if stored else {}
    readings = read_edit(before, graph, sites, registry.stack().registry)
    moved = False
    for change in [r.change() for r in readings] + _values(before, graph):
        moved = changes.apply(draft_id, change, who=who) or moved
    if moved:
        _rebuild(session_id, draft_id, who)
    with session_scope() as db:
        return db.get(PipelineDraft, draft_id).revision


def upload(session_id: str, files: list[tuple[str, bytes]], sizes: tuple[int, ...],
           *, who: str) -> dict:
    """Samples measured by this server's inspectors (#134, #466): kept on the session, and each
    fact every sample agrees on recorded as measured, unless the person already said it — their
    word stands. Returns what was read, for the person's next message to the agent."""
    from mendel_api.services import inspect
    from mendel_api.services.sample_upload import samples_of
    from mendel_api.stages.samples import _agreed, _keep_samples

    draft_id = _draft_of(session_id)
    grouped = samples_of(list(files), tuple(sizes))
    inspections = [inspect.inspect_sample(list(s.files), registry.stack(), None, sizes=s.sizes)
                   for s in grouped]
    _keep_samples(session_id, grouped, inspections)
    agreed = inspections[0] if len(inspections) == 1 else _agreed(inspections)
    said = {f.subject for f in decisions.read(draft_id).facts
            if f.origin is FactOrigin.PERSON_SAID}
    recorded = []
    for fact in agreed.facts:
        if fact.undetermined is not None or fact.value is None or fact.measurement in said:
            continue
        decisions.observe(draft_id, fact.measurement, fact.value, origin=FactOrigin.MEASURED,
                          pieces=fact.pieces)
        recorded.append(fact.measurement)
    if agreed.type_id:
        changes.apply(draft_id, DecisionChange(kind="input", subject=agreed.type_id, value=True),
                      who=who)
    return {"outcome": agreed.outcome, "type_id": agreed.type_id, "samples": len(grouped),
            "recorded": recorded, "facts": [f.model_dump() for f in agreed.facts],
            "reason": agreed.reason, "steps": list(agreed.steps)}
