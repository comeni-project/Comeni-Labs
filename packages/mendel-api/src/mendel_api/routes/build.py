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
from mendel_compiler import locate, pipeline_file
from mendel_resolver.compatibility import Compatibility
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict, Field

from mendel_api import identity, jobs
from mendel_api.refusals import REFUSES, Refusal
from mendel_api.services import build as service
from mendel_api.services import bundle as bundle_service
from mendel_api.services import candidates, deletion, draft_mutations, registry
from mendel_api.services import compare as compare_service
from mendel_api.services import drafts as draft_service
from mendel_api.services import gates as gate_service
from mendel_api.services import validate as validation
from mendel_api.services.build import BuiltPipeline, ModuleView
from mendel_api.services.candidates import Candidates

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


@router.get(
    "/candidates",
    operation_id="listCandidates",
    summary="What could sit on the other end of a wire, in the resolver's own order",
)
def list_candidates(type_id: str, states: str = "", side: str = "producing") -> Candidates:
    """The port picker's ordering, and the reason beside each row.

    **Filtering is the browser's; ordering is not.** `GET /pipeline/compatibility` already tells a
    client what fits — that is a lookup it can do without a round trip, and `useCompatibility`
    does. What it cannot know is which candidate `resolve()` would reach for, and that is what
    makes the picker an answer rather than a filtered list.

    `states` is a comma-separated list, empty for none. A **query** rather than a path segment
    because a state set is unordered and a path implies one.

    `side=producing` asks *what could feed this input*; `side=consuming` asks *what would accept
    this output*. Only the first has the resolver's authority behind its order, and
    `services/candidates.py` says so rather than pretending otherwise.
    """
    wanted = frozenset(part for part in states.split(",") if part)
    if side == "consuming":
        return candidates.consuming(type_id, wanted)
    return candidates.producing(type_id, wanted)


class DraftIn(BaseModel):
    """What a client sends to open or update a draft."""

    model_config = ConfigDict(extra="forbid")

    graph: DraftGraph
    name: str | None = None
    """`None` leaves a saved draft's name as it is (issue 271); a new draft gets `""`."""


class DraftSave(BaseModel):
    """A checked save; omitting graph permits a metadata-only rename."""

    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    graph: DraftGraph | None = None
    name: str | None = None


class DraftOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    graph: DraftGraph
    revision: int


class Kept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    """Where the server wrote it. **Returned, never accepted** — invariant 15 is about what
    an input may carry, and a server saying where it put something is the opposite direction."""
    findings: list[str] = []
    """What the kept file cannot do on its own (MD0231, MD0232), one coded sentence each."""


class DraftsPage(BaseModel):
    """A page of the lab's pipelines, and the total behind it."""

    model_config = ConfigDict(extra="forbid")

    drafts: list[draft_service.DraftRow]
    total: int


@router.get("/drafts", operation_id="listDrafts", summary="Every pipeline this lab has")
def list_drafts(after: int = 0, limit: int = 50) -> DraftsPage:
    """The *by pipeline* half of the front door — and **it had no query at all** until Plan 4
    phase 2. The build router carried create, read, save, keep and bundle, every one addressed
    by a known id; nothing could answer *what do we have*.

    **Readiness, never history.** A run's outcome belongs to `wiener-api` and to the *by run*
    view; leaking one onto a pipeline row is the defect `ov-work` names by hand.

    **Nothing here resolves.** Provenance is read off the artifact `keep` wrote.
    """
    drafts, total = draft_service.list_drafts(after=after, limit=limit)
    return DraftsPage(drafts=drafts, total=total)


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
    name = body.name or ""
    draft_id = draft_service.create(body.graph, name, identity.default_author())
    return DraftOut(id=draft_id, name=name, graph=body.graph, revision=0)


@router.get("/drafts/{draft_id}", operation_id="readDraft", summary="A draft as it stands")
def read_draft(draft_id: str) -> DraftOut:
    try:
        row = draft_service.read(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None
    return DraftOut(id=row.id, name=row.name, graph=DraftGraph.model_validate(row.graph),
                    revision=row.revision)


@router.delete("/drafts/{draft_id}", status_code=204, operation_id="deleteDraft",
               summary="Delete a draft and everything about it, permanently", responses=REFUSES)
def delete_draft(draft_id: str) -> None:
    """**Permanent.** The draft, its conversations, decisions and gate results go; its model
    calls keep their record without their text (Part H)."""
    deletion.delete_draft(draft_id)


class DraftSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str


@router.post("/drafts/{draft_id}/session", operation_id="openDraftSession",
             summary="Open a pipeline in the builder: its conversation, or a new one",
             responses=REFUSES)
def open_draft_session(draft_id: str) -> DraftSession:
    """**Every pipeline has a conversation** (one builder, #395). A draft drawn by hand gets one
    with nothing said, which reads the drawing back for the person to confirm; a draft that has
    one is answered with it. Two opens at once make one: the unique index decides, and the
    loser is answered with the winner's."""
    from mendel_authoring import commands as c
    from sqlalchemy.exc import IntegrityError

    from mendel_api.services import session
    from mendel_api.stages import describe

    try:
        draft_service.read(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None
    try:
        opened = session.perform(c.OpenDrawn(draft_id, identity.default_author())).result
    except (IntegrityError, ValueError):
        # The other open won, at the index (`IntegrityError`) or at `open_session`'s own check
        # (`MI0200`); anything else leaves no session and is raised.
        opened = describe.session_of(draft_id)
        if opened is None:
            raise
    return DraftSession(session_id=opened)


@router.put("/drafts/{draft_id}", operation_id="saveDraft", summary="Save a checked draft",
            responses={**REFUSES, 409: {"model": Refusal,
                        "description": "MI0201: stale save; "
                                       "MI0217: authored work is in progress."}})
def save_draft(draft_id: str, body: DraftSave) -> DraftOut:
    try:
        row = draft_mutations.save(draft_id, graph=body.graph, name=body.name,
                                   expected_revision=body.expected_revision)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None
    except draft_mutations.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return DraftOut(id=row.id, name=row.name, graph=DraftGraph.model_validate(row.graph),
                    revision=row.revision)


@router.post(
    "/drafts/{draft_id}/keep",
    operation_id="keepDraft",
    summary="Stop being a draft: write the pipeline.yml",
    responses=REFUSES,
)
def keep_draft(draft_id: str) -> Kept:
    """**Where `validate` reports and this refuses.** An illegal finding answers 422 with its
    code; `mendel explain <code>` expands it, the same as everywhere else."""
    from mendel_api.services import session as authoring_session

    try:
        # **An authored draft states its AI points, the same way its preview does.** Without them
        # a Spawn draft carrying a model's tier-4 choice is refused by `MD0225` — correctly, since
        # the file would otherwise claim no AI point was available to make it.
        path = draft_service.keep(draft_id, ai=authoring_session.ai_for_draft(draft_id))
        kept = pipeline_file.load(path)
        return Kept(path=str(path), findings=locate.findings(kept.registry.layers))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}") from None


class Artifact(BaseModel):
    """A kept pipeline, as the document it is."""

    model_config = ConfigDict(extra="forbid")

    text: str
    """The `pipeline.yml` verbatim.

    **Not a projection of it.** `CLAUDE.md`: *`pipeline.yml` IS the pipeline* — one artifact
    carrying the goal, every step and setting with a `why:`, every contract pinned by digest.
    The builder's second view is that file, so sending a re-serialised model would mean the
    screen showed something structurally similar to what `mendel emit` reads, which is exactly
    the gap a reader opens this view to close.
    """
    sections: list[str] = []
    """Top-level keys, in the order they appear, so the view can offer jumps without parsing
    YAML in the browser. A row of chips, not another left-hand list (`n-bartifact`)."""


@router.get(
    "/drafts/{draft_id}/artifact",
    operation_id="readArtifact",
    summary="The kept pipeline.yml, as text",
    responses=REFUSES,
)
def read_artifact(draft_id: str) -> Artifact:
    """**The other view of the canvas.** `n-bartifact`: *pipeline.yml is the pipeline, so the
    other view of the canvas is the artifact itself.*

    404 when the draft has never been kept — a draft has no artifact until `keep` writes one,
    and inventing an empty document would claim otherwise.
    """
    path = draft_service.artifact_path(draft_id)
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="this pipeline has not been kept yet, so there is no artifact to read",
        )
    text = path.read_text()
    sections = [
        line.split(":", 1)[0]
        for line in text.splitlines()
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line
    ]
    return Artifact(text=text, sections=sections)


class EmittedPipeline(BaseModel):
    """The draft's Nextflow: what *Compile it* shows (one builder plan 5)."""

    model_config = ConfigDict(extra="forbid")

    revision: int
    main_nf: str
    nextflow_config: str


@router.get(
    "/drafts/{draft_id}/emitted",
    operation_id="emittedPipeline",
    summary="The Nextflow the draft compiles to, as it previews",
    responses=REFUSES,
)
def emitted(draft_id: str) -> EmittedPipeline:
    """Read-only: emitted from the preview's materialisation, written nowhere (`MI0219` when
    there is no pipeline yet)."""
    try:
        done = draft_service.emitted(draft_id)
    except ValueError as nothing:
        raise HTTPException(status_code=422, detail=str(nothing)) from None
    return EmittedPipeline(
        revision=done.revision, main_nf=done.main_nf, nextflow_config=done.config
    )


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
    try:
        run_id = await run_in_threadpool(
            gate_service.request, draft_id, body.gate, identity.default_author()
        )
    except ValueError as busy:  # MI0003: one live gate per draft (issue 278)
        raise HTTPException(status_code=409, detail=str(busy)) from None
    await jobs.enqueue("run_gate_job", run_id)
    return await run_in_threadpool(gate_service.read, run_id)


@router.get("/gates/{run_id}", operation_id="readGate", summary="How a gate is going")
def read_gate(run_id: str) -> gate_service.GateView:
    """Poll one gate. The browser stops asking once `state` leaves `queued`/`running`."""
    try:
        return gate_service.read(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no such gate run: {run_id}") from None
