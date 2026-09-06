"""What a reviewer reads: the candidate contract, where each value came from, and its files.

**The workspace is the authority and this is a projection of it.** The scaffold, the source
bundle and the holes live on disk under `settings.workspace_root`, written by the jobs that
produced them; nothing here writes, and nothing here recomputes a verdict. A second copy of the
candidate in Postgres would be a second thing to keep honest, and the one that a reviewer
actually approves is the one `land.py` reads — which is this one.

**No path leaves this module.** `ForgeRevision.manifest` holds workspace-relative paths for
exactly this reason, and the same claim has to hold on the way out: an absolute host path in a
response is a path in a screenshot, in a bug report and eventually in a prompt. What crosses is
file *contents* and the relative name.

**Provenance per field is the whole point.** §8.5 asks for `SOURCE`, `DERIVED`, `AI` and
`HUMAN` labels on a diff and for solid/outlined/dashed marks on a graph, and both are the same
fact — `FilledValue.how`, which `Scaffold.fill` has recorded since Phase 1. Deriving it in the
browser from anything else would be a second implementation of *who decided this*.
"""

import json
from typing import Any

from comeni_core.review import ValueSource
from mendel_forge.catalogue import NumberedExcerpt
from mendel_forge.hole_manifest import ScaffoldHole
from mendel_forge.scaffold import Scaffold
from mendel_forge.workspace import Workspace
from pydantic import BaseModel, ConfigDict

from mendel_api.settings import settings

_FROZEN = ConfigDict(extra="forbid", frozen=True)


class ContractField(BaseModel):
    """One settled field of the candidate contract, and who settled it."""

    model_config = _FROZEN

    field: str
    """The scaffold's own key — `consumes[0].type_id`."""
    hole_id: str = ""
    """The semantic id this field was asked under — `consumes.reads.type_id` — or empty when
    the deterministic half read it and it was never a hole.

    **Two addressings, and both are load-bearing.** A hole id is stable across revisions and is
    what a citation, an event and a change request point at; the scaffold key is positional and
    is what `contract_from` writes. Joining them here rather than in the browser means the page
    never has to know that `/consumes/0/type_id` and `consumes.reads.type_id` are one thing.
    """
    value: str
    """JSON, so a list of states and a bare string are told apart by the reader.

    A `str(value)` here would render `['coordinate_sorted']` and `coordinate_sorted` identically
    on a screen whose job is to show exactly what will be written.
    """
    how: ValueSource
    by: str
    why: str
    evidence_ids: tuple[str, ...] = ()


class OpenHole(BaseModel):
    """A question still open on this candidate.

    Carried in full — `question`, `why_open`, the legal values and whether that list is the
    whole of what is legal — because §8.4 asks the scaffold summary to link each hole to its
    evidence and its prompt hint, and a page given only an id would have to invent the sentence.
    """

    model_config = _FROZEN

    id: str
    pointer: str
    kind: str
    question: str
    why_open: str
    required: bool
    legal_values: tuple[str, ...] = ()
    exhaustive: bool = True
    suggested: str | None = None
    evidence_ids: tuple[str, ...] = ()
    hint: str = ""


class GraphPort(BaseModel):
    """One side of the input/output graph — §8.5's *ports show semantic type and states*.

    **`origin` is three-valued and not a boolean.** *From the source*, *proposed by a model* and
    *still open* are what the artboard's solid, outlined and dashed marks say, and collapsing
    the last two would draw an unanswered question as an answer.
    """

    model_config = _FROZEN

    channel: str
    name: str = ""
    type_id: str = ""
    states: tuple[str, ...] = ()
    origin: str = "open"
    """`derived`, `model`, `human` or `open`."""
    hole_id: str = ""
    """What to open when this port is selected. Empty when nothing about it was ever a hole."""


class IoGraph(BaseModel):
    """Inputs on the left, one process node, outputs on the right.

    **Not `dag-core`.** §8.5 allows it *only if its layout can express this without coupling the
    Forge to builder state*, and it cannot without carrying one: this graph is three columns
    with no edges to route, and `dag-core` answers *where do nodes go in a DAG*. Using it here
    would be importing a layout engine to place three boxes in a row.
    """

    model_config = _FROZEN

    process: str = ""
    consumes: tuple[GraphPort, ...] = ()
    produces: tuple[GraphPort, ...] = ()
    params: int = 0


class FilePane(BaseModel):
    """One candidate file, whole, with the relative name a reviewer sees."""

    model_config = _FROZEN

    path: str
    text: str
    authored: bool
    """Whether the forge wrote this file, or copied it from upstream unchanged.

    **This is the claim the Files tab exists to let somebody check.** A source that ships
    Nextflow gets a contract bound to its process and nothing downstream may author one, so an
    authored `main.nf` beside a source that shipped one is a rule broken — and the only way to
    see that is for the page to say which it is.
    """


class Origins(BaseModel):
    """How many values came from where. §8.5's provenance summary, counted once."""

    model_config = _FROZEN

    derived: int = 0
    model: int = 0
    human: int = 0
    open: int = 0


class ReviewCandidate(BaseModel):
    """Everything the review page renders about one candidate.

    One response rather than five, for the reason `detail` gives: a graph from one moment beside
    a hole list from another shows a port as settled that the hole list says is open.
    """

    model_config = _FROZEN

    adaptation_id: str
    graph: IoGraph
    fields: tuple[ContractField, ...] = ()
    holes: tuple[OpenHole, ...] = ()
    evidence: tuple[NumberedExcerpt, ...] = ()
    files: tuple[FilePane, ...] = ()
    origins: Origins = Origins()
    source_digest: str = ""


def _key(pointer: str) -> str:
    """`/consumes/0/type_id` -> `consumes[0].type_id`.

    The same arithmetic as `mendel_forge.ai.render.field_for`, and deliberately not an import of
    it: that function is on the generation path and belongs to the model adapter, and reaching
    across for it would make a read of the workspace depend on the module that writes it.
    Should the two ever disagree, `test_a_hole_and_its_field_address_one_thing` fails.
    """
    head, *rest = [part for part in pointer.split("/") if part]
    out = head
    for part in rest:
        out += f"[{part}]" if part.isdigit() else f".{part}"
    return out


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        # A value the scaffold accepted that JSON cannot spell. Rendering its `repr` is honest
        # about being a fallback; raising here would make one odd field blank the whole page.
        return json.dumps(repr(value))


def _ports(scaffold: Scaffold, holes: tuple[ScaffoldHole, ...], group: str) -> list[GraphPort]:
    """The ports of one side, assembled from whatever is settled and whatever is still asked.

    **Driven by the holes and the filled fields together**, because either alone is incomplete:
    a port the source fully described has no holes at all, and a port nothing was read for
    exists only as three open questions.
    """
    by_channel: dict[str, dict[str, Any]] = {}

    for hole in holes:
        parts = hole.id.split(".")
        if len(parts) != 3 or parts[0] != group:
            continue
        port = by_channel.setdefault(parts[1], {"holes": {}, "values": {}})
        port["holes"][parts[2]] = hole

    for field, filled in scaffold.filled.items():
        if not field.startswith(f"{group}["):
            continue
        index, _, attribute = field.partition("].")
        slot = index[len(group) + 1 :]
        # A filled field is addressed positionally and a hole semantically; the pointer on the
        # hole is what joins them, so a filled port with no hole is keyed by its index.
        channel = next(
            (
                name
                for name, port in by_channel.items()
                if any(h.pointer == f"/{group}/{slot}/{key}" for key, h in port["holes"].items())
            ),
            slot,
        )
        by_channel.setdefault(channel, {"holes": {}, "values": {}})["values"][attribute] = filled

    out: list[GraphPort] = []
    for channel, port in by_channel.items():
        values = port["values"]
        holes_here = port["holes"]
        settled = values.get("type_id")
        states = values.get("state") or values.get("states")
        out.append(
            GraphPort(
                channel=channel,
                name=str(values["name"].value) if "name" in values else channel,
                type_id=str(settled.value) if settled else "",
                states=tuple(str(s) for s in (states.value if states else ()) or ()),
                origin=(
                    "open"
                    if not settled
                    else str(settled.how.value if hasattr(settled.how, "value") else settled.how)
                ),
                hole_id=next(iter(holes_here.values())).id if holes_here else "",
            )
        )
    return sorted(out, key=lambda port: port.channel)


def candidate(adaptation_id: str) -> ReviewCandidate:
    """Read one candidate out of the workspace.

    **`KeyError` when nothing has been scaffolded yet**, which the transport turns into a 404 —
    the same convention every other forge service uses. An adaptation in `scaffolding` has no
    candidate, and answering with an empty one would tell the page that the scaffold produced
    nothing rather than that it has not run.
    """
    workspace = Workspace(root=settings.workspace_root)
    try:
        draft = workspace.read_draft(adaptation_id)
        holes = workspace.read_holes(adaptation_id)
        source = workspace.read_source(adaptation_id)
    except ValueError as absent:
        raise KeyError(adaptation_id) from absent

    answered = {hole.id for hole in holes} - {
        hole.id for hole in holes if _key(hole.pointer) not in draft.scaffold.filled
    }
    open_holes = tuple(
        OpenHole(
            id=hole.id,
            pointer=hole.pointer,
            kind=str(hole.kind),
            question=hole.question,
            why_open=hole.why_open,
            required=hole.required,
            legal_values=hole.legal_values,
            exhaustive=hole.exhaustive,
            suggested=hole.suggested,
            evidence_ids=hole.evidence_ids,
            hint=hole.hint,
        )
        for hole in holes
        if hole.id not in answered
    )

    by_pointer = {_key(hole.pointer): hole for hole in holes}
    fields = tuple(
        ContractField(
            field=field,
            hole_id=by_pointer[field].id if field in by_pointer else "",
            value=_json(filled.value),
            how=filled.how,
            by=filled.by,
            why=filled.why,
            evidence_ids=(
                by_pointer[field].evidence_ids if field in by_pointer else ()
            ),
        )
        for field, filled in sorted(draft.scaffold.filled.items())
    )

    origins = Origins(
        derived=sum(1 for f in fields if f.how is ValueSource.DERIVED),
        model=sum(1 for f in fields if f.how is ValueSource.MODEL),
        human=sum(1 for f in fields if f.how is ValueSource.HUMAN),
        open=len(open_holes),
    )

    files = []
    if draft.module is not None:
        files.append(FilePane(path="main.nf", text=draft.module, authored=True))
    else:
        upstream = source.file("main.nf")
        if upstream is not None:
            files.append(FilePane(path="main.nf", text=upstream.text, authored=False))

    process = draft.scaffold.filled.get("nf_process")
    return ReviewCandidate(
        adaptation_id=adaptation_id,
        graph=IoGraph(
            process=str(process.value) if process else draft.scaffold.target,
            consumes=tuple(_ports(draft.scaffold, holes, "consumes")),
            produces=tuple(_ports(draft.scaffold, holes, "produces")),
            params=sum(1 for field in draft.scaffold.filled if field.startswith("params[")),
        ),
        fields=fields,
        holes=open_holes,
        evidence=source.evidence,
        files=tuple(files),
        origins=origins,
        source_digest=source.source_digest,
    )
