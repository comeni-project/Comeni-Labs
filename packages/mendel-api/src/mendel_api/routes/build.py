"""`/pipeline` — a goal in, a resolved and laid-out pipeline out.

**Read-only, and it writes nothing anywhere.** A build here is a computation, not a save: the
artifact on disk is what a pipeline *is*, and this endpoint exists so a canvas can show one
before anybody decides to keep it.

`POST` rather than `GET` because a `Goal` is a document — it carries a profile, wants and
producer pins — and a URL is the wrong place for it. Invariant 15 is why the body is a `Goal` and
not a path: no input here accepts a sample identifier, a filename or a path.
"""

from fastapi import APIRouter
from mendel_resolver.goal import Goal

from mendel_api.refusals import REFUSES
from mendel_api.services import build as service
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
