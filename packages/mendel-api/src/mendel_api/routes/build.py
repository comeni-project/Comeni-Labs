"""`/pipeline` — a goal in, a resolved and laid-out pipeline out.

**Read-only, and it writes nothing anywhere.** A build here is a computation, not a save: the
artifact on disk is what a pipeline *is*, and this endpoint exists so a canvas can show one
before anybody decides to keep it.

`POST` rather than `GET` because a `Goal` is a document — it carries a profile, wants and
producer pins — and a URL is the wrong place for it. Invariant 15 is why the body is a `Goal` and
not a path: no input here accepts a sample identifier, a filename or a path.
"""

from comeni_core.plan.draft import DraftGraph
from comeni_core.review.verdict import Verdict
from fastapi import APIRouter, Request, Response
from mendel_resolver.compatibility import Compatibility
from mendel_resolver.goal import Goal

from mendel_api.refusals import REFUSES
from mendel_api.services import build as service
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
