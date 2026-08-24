"""`/pipeline` — a goal in, a resolved and laid-out pipeline out.

**Read-only, and it writes nothing anywhere.** A build here is a computation, not a save: the
artifact on disk is what a pipeline *is*, and this endpoint exists so a canvas can show one
before anybody decides to keep it.

`POST` rather than `GET` because a `Goal` is a document — it carries a profile, wants and
producer pins — and a URL is the wrong place for it. Invariant 15 is why the body is a `Goal` and
not a path: no input here accepts a sample identifier, a filename or a path.
"""

from comeni_core.artifact.gates import Gate
from comeni_core.plan.draft import DraftGraph
from comeni_core.review.verdict import Verdict
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from mendel_resolver.compatibility import Compatibility
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict

from mendel_api import identity, jobs
from mendel_api.refusals import REFUSES
from mendel_api.services import build as service
from mendel_api.services import bundle as bundle_service
from mendel_api.services import compare as compare_service
from mendel_api.services import drafts as draft_service
from mendel_api.services import gates as gate_service
from mendel_api.services import registry
from mendel_api.services import validate as validation
from mendel_api.services.build import BuiltPipeline, ModuleView

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get(
    "/example",
    operation_id="examplePipeline",
    summary="The RNA-seq spine, from the goal committed in examples/",
)
def example() -> BuiltPipeline:
    """**What the canvas opens on.**

    Nothing can author a goal until the prompt door exists — that is after #69 — so a screen with
    no starting pipeline would be a screen nobody could reach. This is a real build of a real
    goal, not a fixture: if the registry changes underneath it, this changes.
    """
    return service.example()


@router.get(
    "/modules",
    operation_id="listModules",
    summary="Every landed contract, for the picker",
)
def modules() -> list[ModuleView]:
    """**Every contract, not only the ones in a pipeline.**

    The builder's left panel is a picker you drag from; a list containing only what is already on
    the canvas is a table of contents. `GET /tools` answers a different question — *what is the
    state of everything* — and carries drift, drafts and undrafted tools, none of which can be
    dragged onto a canvas.
    """
    return service.modules()


@router.post(
    "",
    operation_id="buildPipeline",
    summary="Resolve a goal and lay it out",
    responses=REFUSES,
)
def build(goal: Goal) -> BuiltPipeline:
    """A contract that disagrees with its module refuses here as a coded 422 — the same refusal
    the CLI prints and exits 2 on. `orchestrate.ConformanceRefused` is a `ValueError`, which the
    app already maps."""
    return service.of(goal)


@router.post(
    "/validate",
    operation_id="validatePipeline",
    summary="Is this graph legal, and what is unmet or unconventional about it",
)
def validate_graph(graph: DraftGraph) -> Verdict:
    """**200 whatever it finds.**

    A verdict is the answer, not an error: a person mid-gesture would rather see three problems
    than the first one, and the forge's `verify` ladder is the precedent. Refusal lives at
    `keep` and at the emission gates, which is the boundary the spec draws.

    An unknown contract comes back as an `MD0509` finding rather than a 422 — a draft naming a
    contract that has since been renamed is a thing to be told about on the canvas, not an
    error that empties the screen.
    """
    return validation.of(graph)


@router.get(
    "/compatibility",
    operation_id="compatibilityIndex",
    summary="What can feed what, so a browser can colour a wire without a round trip",
    response_model=Compatibility,
    responses={304: {"description": "the registry has not changed since your copy"}},
)
def compatibility_index(request: Request, response: Response) -> Compatibility | Response:
    """The client looks up; it never decides. See `mendel_resolver.compatibility`.

    `ETag` is the registry digest — the same string that invalidates the server's own cache, so
    "the registry changed" has one definition rather than two. A reload becomes a 304 instead of
    the whole table.
    """
    etag = f'"{registry.digest()}"'
    if request.headers.get("if-none-match") == etag:
        # A bare `Response` rather than an `HTTPException`: 304 is not an error, and a 304 with
        # a body is malformed. `response_model` on the decorator keeps the generated client's
        # schema even though this branch returns no model.
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return validation.index()


class DraftIn(BaseModel):
    """What a client sends to open or update a draft."""

    model_config = ConfigDict(extra="forbid")

    graph: DraftGraph
    name: str = ""


class DraftOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    graph: DraftGraph


class Kept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    """Where the server wrote it. **Returned, never accepted** — invariant 15 is about what
    an input may carry, and a server saying where it put something is the opposite direction."""


@router.post(
    "/drafts",
    operation_id="createDraft",
    summary="Open a draft",
    status_code=201,
    responses=REFUSES,
)
def create_draft(body: DraftIn) -> DraftOut:
    """The id is opaque and server-generated. `routes/build.py`'s own header records why the
    API cannot take a path, and a draft addressed by one would be that rule undone."""
    draft_id = draft_service.create(body.graph, body.name, identity.default_author())
    return DraftOut(id=draft_id, name=body.name, graph=body.graph)


@router.get("/drafts/{draft_id}", operation_id="readDraft", summary="A draft as it stands")
def read_draft(draft_id: str) -> DraftOut:
    try:
        row = draft_service.read(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None
    return DraftOut(id=row.id, name=row.name, graph=DraftGraph.model_validate(row.graph))


@router.put("/drafts/{draft_id}", operation_id="saveDraft", summary="Save a draft")
def save_draft(draft_id: str, body: DraftIn) -> DraftOut:
    """One write per save, not per edit. The client owns the working graph and sends it whole —
    a schema that could hold half a graph would be a second definition of what a graph is."""
    try:
        draft_service.update(draft_id, body.graph)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None
    return DraftOut(id=draft_id, name=body.name, graph=body.graph)


@router.post(
    "/drafts/{draft_id}/keep",
    operation_id="keepDraft",
    summary="Stop being a draft: write the pipeline.yml",
    responses=REFUSES,
)
def keep_draft(draft_id: str) -> Kept:
    """**Where `validate` reports and this refuses.** An illegal finding answers 422 with its
    code; `mendel explain <code>` expands it, the same as everywhere else."""
    try:
        return Kept(path=str(draft_service.keep(draft_id)))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None


@router.get(
    "/drafts/{draft_id}/bundle",
    operation_id="downloadBundle",
    summary="The kept pipeline, as a zip somebody else can run",
    response_class=Response,
    responses={**REFUSES, 200: {"content": {"application/zip": {}}}},
)
def bundle(draft_id: str) -> Response:
    """**Mendel's half of the courier, and the whole of what it knows about running** — A179.

    `docs/design/wiener.md` §12: the browser fetches this and posts it to Wiener, so the copy
    happens in a place that can see both halves and neither half can see the other. This route
    does not know that Wiener exists, has no idea what will be done with the archive, and would
    serve the same bytes to `curl`.

    **It does not check that a gate passed.** Whether an un-gated pipeline may run is a policy
    about running, and running is Wiener's — `execution-boundary.md` §3. What Mendel owes here
    is an honest artifact; the builder's own control is what refuses to offer the button before
    a gate has passed, where a person can read the reason.
    """
    try:
        archive = bundle_service.of(draft_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"nothing has been kept under draft {draft_id}"
        ) from None
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="pipeline-{draft_id[:8]}.zip"'},
    )


@router.post(
    "/compare",
    operation_id="comparePipeline",
    summary="Your graph beside the one the resolver would build",
    responses=REFUSES,
)
def compare_pipeline(body: compare_service.CompareIn) -> compare_service.Comparison:
    """**One call, not two.** Deciding what counts as the same step is a judgement — HISAT2
    where Mendel put STAR fills one slot rather than being two unrelated steps — and a judgement
    made in the browser is one the agent driving this API cannot reach."""
    return compare_service.of(body.graph, body.goal)


@router.post(
    "/draw",
    operation_id="drawPipeline",
    summary="Lay out a hand-drawn graph, in the shape the canvas already renders",
    responses=REFUSES,
)
def draw(graph: DraftGraph) -> BuiltPipeline:
    """**Layout stays in Python.** `CLAUDE.md`: the DAG layout is computed server-side so the
    canvas is as deterministic as the emitted `.nf`. A drawn graph gets the same treatment — a
    browser laying out its own nodes would be the one part of the picture that could differ
    between two people looking at the same pipeline.

    Returns a `BuiltPipeline`, which is what `/pipeline` already returns, so Plan 3C's canvas
    draws a hand-drawn graph without a component changing.
    """
    return service.drawn(graph)


class GateIn(BaseModel):
    """**A gate, and nothing else.**

    `docs/design/execution-boundary.md` §3: the test for whether something is a *run* rather
    than a *gate* is whether it takes a samplesheet, and this cannot. No path, no output
    directory, no input — `extra="forbid"` is what keeps it that way as the type grows.
    """

    model_config = ConfigDict(extra="forbid")
    gate: Gate


@router.post(
    "/drafts/{draft_id}/gate",
    operation_id="startGate",
    summary="Gate a kept draft",
    responses=REFUSES,
)
async def start_gate(draft_id: str, body: GateIn) -> gate_service.GateView:
    """Queue a gate and return immediately with a `queued` run.

    A stub gate is up to 900s cold and nothing that long may sit in a request — `worker.py`'s
    docstring has said so since phase 8.

    **This is not *Run pipeline*.** A gate proves the artifact on public test data; running a
    laboratory's data is Wiener's, and Mendel has no route for it by design.
    """
    # **`run_in_threadpool`, because this route had to become `async` to await the enqueue.**
    # Every other route here is a plain `def`, which FastAPI already runs in a threadpool; an
    # `async def` doing a synchronous Postgres session blocks the event loop for every other
    # request in flight.
    run_id = await run_in_threadpool(
        gate_service.request, draft_id, body.gate, identity.default_author()
    )
    await jobs.enqueue("run_gate_job", run_id)
    return await run_in_threadpool(gate_service.read, run_id)


@router.get("/gates/{run_id}", operation_id="readGate", summary="How a gate is going")
def read_gate(run_id: str) -> gate_service.GateView:
    """Poll one gate. The browser stops asking once `state` leaves `queued`/`running`."""
    try:
        return gate_service.read(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no such gate run: {run_id}") from None
