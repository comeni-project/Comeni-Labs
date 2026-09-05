"""`/forge` — the whole adaptation surface, §7.

**No request body accepts a path, a provider key, a base URL or a model name.** Every one of
those comes from `settings`, and a browser choosing any of them would be a second answer to a
question that file answers once. `test_forge_routes.py` holds it as a literal field allowlist
rather than as a rule, because a path cannot be recognised by its type — the same construction
`test_ai_schemas.py` uses for the response side.

**A queued mutation answers `202`, never `200`.** §7, and the distinction is not ceremony: a
`200` says *this is done*, and what has actually happened is that a row exists and a worker will
get to it. A page that reads `200` as done shows a finished adaptation that has not started.
"""

from typing import Annotated, Literal

from comeni_core.artifact.digest import digest_of_directory
from fastapi import APIRouter, Body, Query, status
from mendel_forge.catalogue import CatalogueItem, Freshness
from mendel_forge.workflow import AdaptationState
from pydantic import BaseModel, ConfigDict, Field

from mendel_api.identity import default_author
from mendel_api.services import (
    forge_adaptations,
    forge_candidate,
    forge_catalogue,
    forge_jobs,
    forge_overview,
)
from mendel_api.services import forge_review as review_service
from mendel_api.settings import settings

router = APIRouter(prefix="/forge", tags=["forge"])

Adapted = Literal["adapted"]
"""The one status that is not a `Freshness`: the union of `current` and `outdated`.

It exists because *N of M adaptable* on the overview counts exactly that union, and a person
clicking that figure means "the ones we have done" rather than "the ones that are up to date".
Spelled as a `Literal` beside the enum rather than added to `Freshness`, because a sixth member
would be a sixth thing `counts` has to tally and it is not a state a tool can be in — it is two.
"""

_FROZEN = ConfigDict(extra="forbid", frozen=True)


class Reason(BaseModel):
    """Every state-changing request carries one, and it is the only field.

    **`extra="forbid"` is what makes the allowlist test meaningful.** A body that silently
    ignored an unknown key would accept `{"reason": "...", "registry_root": "/etc"}` and the
    test that says *these are all the fields* would be describing a model rather than a
    boundary.
    """

    model_config = _FROZEN

    reason: str = Field(min_length=1, max_length=2000)


class Ask(BaseModel):
    """A curator's question. `message` and nothing else — see the module docstring."""

    model_config = _FROZEN

    message: str = Field(min_length=1, max_length=review_service.MAX_MESSAGE)


class Start(BaseModel):
    """Which catalogue item to adapt. **An id, never a ref or a path.**

    A ref would have to be resolved against a source, and *which source* is then a second field
    a caller could get wrong; the id already names exactly one row.
    """

    model_config = _FROZEN

    catalogue_item_id: str = Field(min_length=1, max_length=64)


class Approval(BaseModel):
    model_config = _FROZEN

    reason: str = Field(min_length=1, max_length=2000)
    rule_candidate_ids: list[str] = Field(default_factory=list, max_length=50)
    """Which proposed rules the approver is accepting alongside the contract.

    Separate from `reason` because they are separate decisions: a person may approve a contract
    and decline every rule it came with, and a single field could not say so.
    """


class CatalogueRow(BaseModel):
    """One tool, and where it stands with us.

    **Two halves that come from two places.** `item` is what upstream published and is a cache
    of somebody else's words; `standing` is what this installation has done about it. Keeping
    them as separate objects rather than flattening is what stops a page reading a freshness as
    though the source had asserted it.
    """

    model_config = _FROZEN

    item: CatalogueItem
    standing: forge_catalogue.Standing


class CataloguePage(BaseModel):
    """A slice of the catalogue, and the total it is a slice of.

    **Typed rather than a `dict`, and that is a fix.** This route answered `-> dict`, so
    `CatalogueItem` never reached the OpenAPI document and the generated client had nothing to
    describe a tool with — the one screen that lists sixteen hundred of them would have had to
    hand-write the shape, which is exactly the drift `frontend/src/api/` exists to make
    impossible. Found on the first consumer.
    """

    model_config = _FROZEN

    rows: tuple[CatalogueRow, ...] = ()
    total: int
    """The count for the CURRENT filter, unlimited by the page — what `1–50 of 1,612` needs."""


class Queued(BaseModel):
    """What a `202` carries: the row as it is now, and that work was queued.

    **`queued` may be `False` and the request still succeeded.** ARQ refuses a duplicate job id,
    which is the mechanism working — the caller pressed twice, or two tabs are open. Reporting
    it lets a page say *already running* instead of implying a second attempt started.
    """

    model_config = _FROZEN

    adaptation: forge_adaptations.AdaptationRow
    queued: bool = True


@router.get("/overview", operation_id="forgeOverview", summary="Counts across the whole forge")
def overview() -> forge_overview.Overview:
    """**Counts and never lists.** `docs/design/forge-review.md` §3 records an Overview page
    designed and cut for answering the same question as the queue; the moment a tool ref appears
    here it has become that page."""
    return forge_overview.overview()


@router.get("/catalogue", operation_id="forgeCatalogue", summary="Every tool a source can read")
def catalogue(
    q: Annotated[str, Query(description="Match the ref, name or summary")] = "",
    source: Annotated[str | None, Query(description="Only this source")] = None,
    status: Annotated[
        Freshness | Adapted | None,
        Query(description="Only tools standing here with us"),
    ] = None,
    adaptable_only: Annotated[bool, Query(description="Hide what cannot be adapted")] = False,
    limit: Annotated[int, Query(ge=1, le=forge_adaptations.MAX_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CataloguePage:
    """A page of the catalogue, and the total it is a slice of.

    **`status` is a SQL clause, never a filter over the page.** Fetching fifty and dropping the
    ones that do not match gives a page of eleven under a total of sixteen hundred, and the
    next page silently skips whatever the first one dropped.

    **Offset here and a cursor on adaptations, deliberately.** The catalogue is ordered by
    `(source, ref)` — a stable key that a sync updates in place rather than reordering — so an
    offset page does not shift under a refresh the way a list ordered by `updated_at` does.
    A total is also cheap over that ordering and is what a *1 to 50 of 1,612* control needs.
    """
    items, total = forge_catalogue.search(
        source=source,
        query=q,
        status=status.value if status else "",
        adaptable_only=adaptable_only,
        limit=limit,
        offset=offset,
    )
    where = forge_catalogue.standing(items)
    return CataloguePage(
        rows=tuple(CatalogueRow(item=item, standing=where[item.id]) for item in items),
        total=total,
    )


@router.get(
    "/catalogue/{item_id}", operation_id="forgeCatalogueItem", summary="One tool, in full"
)
def catalogue_item(item_id: str) -> CatalogueItem:
    """One tool, by id — what the catalogue's inspector opens when the row is not on screen."""
    return forge_catalogue.one(item_id)


@router.post(
    "/sources/sync",
    operation_id="forgeSyncSources",
    summary="Refresh a source's catalogue",
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync(source: Annotated[str, Body(embed=True)]) -> dict:
    """Queued, not performed. A walk of sixteen hundred tools does not belong in a request."""
    return {"source": source, "queued": await forge_jobs.enqueue_sync(source)}


@router.post(
    "/adaptations",
    operation_id="forgeStartAdaptation",
    summary="Start adapting one tool",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start(body: Start) -> Queued:
    """Creates the durable state and queues the deterministic scaffold.

    **The row exists before the job is enqueued**, so a queue that is down costs a scaffold
    rather than the record of what somebody asked for. `forge_jobs.enqueue_scaffold` is
    idempotent on the adaptation id, so a retried request cannot start two.
    """
    row = forge_adaptations.begin(body.catalogue_item_id, who=default_author())
    return Queued(adaptation=row, queued=await forge_jobs.enqueue_scaffold(row.id))


@router.get("/adaptations", operation_id="forgeAdaptations", summary="Adaptations, newest first")
def adaptations(
    state: Annotated[AdaptationState | None, Query(description="Only this stage")] = None,
    source: Annotated[str | None, Query(description="Only this source")] = None,
    cursor: Annotated[str | None, Query(description="From a previous page's next_cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=forge_adaptations.MAX_LIMIT)] = 50,
) -> forge_adaptations.Page:
    return forge_adaptations.listing(state=state, source=source, cursor=cursor, limit=limit)


@router.get(
    "/adaptations/{adaptation_id}",
    operation_id="forgeAdaptation",
    summary="One adaptation, its revisions and its history",
)
def adaptation(adaptation_id: str) -> forge_adaptations.Adaptation:
    return forge_adaptations.detail(adaptation_id)


@router.get(
    "/adaptations/{adaptation_id}/revisions/{revision_id}",
    operation_id="forgeRevision",
    summary="One revision of one adaptation",
)
def revision(adaptation_id: str, revision_id: str) -> forge_adaptations.Revision:
    return forge_adaptations.revision(adaptation_id, revision_id)


@router.get(
    "/adaptations/{adaptation_id}/candidate",
    operation_id="forgeCandidate",
    summary="The candidate contract, its provenance and its files",
)
def candidate(adaptation_id: str) -> forge_candidate.ReviewCandidate:
    """What the review page renders — read out of the workspace, never recomputed.

    **404 until something has been scaffolded.** An adaptation still in `scaffolding` has no
    candidate, and an empty one would read as *the scaffold produced nothing*.
    """
    return forge_candidate.candidate(adaptation_id)


@router.get(
    "/adaptations/{adaptation_id}/approval",
    operation_id="forgeApprovalState",
    summary="Whether approval is available, and every reason it is not",
)
def approval(adaptation_id: str) -> forge_adaptations.ApprovalState:
    """**Read before the click.** §8.5 asks approval to be disabled with a visible reason, and
    the reasons are `approval_refusals`' — the same six the POST refuses on, so a button that
    says it is available and a server that then refuses cannot disagree."""
    return forge_adaptations.approval(
        adaptation_id,
        who=default_author(),
        registry_digest_now=digest_of_directory(settings.registry_root),
    )


@router.post(
    "/adaptations/{adaptation_id}/retry",
    operation_id="forgeRetryAdaptation",
    summary="Resume a failed adaptation at the stage it failed",
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry(adaptation_id: str, body: Reason) -> Queued:
    """**Rule 9 decides where it resumes, not this endpoint.** `retry_target` reads
    `failed_stage`: a scaffold that could not be built is not repaired by queueing a model."""
    row = forge_adaptations.retry(adaptation_id, who=default_author())
    queued = (
        await forge_jobs.enqueue_scaffold(row.id)
        if row.state is AdaptationState.SCAFFOLDING
        else await forge_jobs.enqueue_generation(row.id, revision=str(row.row_version))
    )
    return Queued(adaptation=row, queued=queued)


@router.post(
    "/adaptations/{adaptation_id}/messages",
    operation_id="forgeAskReview",
    summary="Ask a question about this candidate",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ask(adaptation_id: str, body: Ask) -> dict:
    """The pending turn is visible immediately — §7. A curator who sees nothing until an answer
    arrives cannot tell *sent* from *lost*, and at 227 seconds they retype it."""
    turn = review_service.ask(adaptation_id, message=body.message)
    queued = await forge_jobs.enqueue_answer(adaptation_id, str(turn.id))
    return {"message": turn.model_dump(mode="json"), "queued": queued}


@router.get(
    "/adaptations/{adaptation_id}/messages",
    operation_id="forgeReviewConversation",
    summary="The whole review conversation",
)
def conversation(adaptation_id: str) -> list[review_service.Turn]:
    return list(review_service.conversation(adaptation_id))


@router.post(
    "/adaptations/{adaptation_id}/changes",
    operation_id="forgeRequestChanges",
    summary="Send a candidate back for another attempt",
    status_code=status.HTTP_202_ACCEPTED,
)
async def changes(adaptation_id: str, body: Reason) -> Queued:
    """**Not rejection** — §1.6's word, and the reason it is not `reject` is that a terminal word
    makes an ordinary correction feel destructive. The candidate being corrected is kept."""
    row = forge_adaptations.request_changes(adaptation_id, who=default_author(), reason=body.reason)
    return Queued(
        adaptation=row,
        queued=await forge_jobs.enqueue_generation(row.id, revision=str(row.row_version)),
    )


@router.post(
    "/adaptations/{adaptation_id}/approve",
    operation_id="forgeApproveAdaptation",
    summary="Approve a candidate for publication",
    status_code=status.HTTP_202_ACCEPTED,
)
async def approve(adaptation_id: str, body: Approval) -> Queued:
    """Records that a named human approved, and queues the one job that writes to a registry.

    **The registry digest is read here, at the moment of approval.** `approval_refusals` compares
    it against the one the candidate was validated against, because a green verdict describes the
    layer that was read at the time and that layer can be gone.
    """
    row = forge_adaptations.approve(
        adaptation_id,
        who=default_author(),
        reason=body.reason,
        registry_digest_now=digest_of_directory(settings.registry_root),
    )
    return Queued(
        adaptation=row,
        queued=await forge_jobs.enqueue_publish(row.id, row.current_revision_id or "none"),
    )


@router.post(
    "/adaptations/{adaptation_id}/archive",
    operation_id="forgeArchiveAdaptation",
    summary="Close an adaptation nobody is working on",
)
def archive(adaptation_id: str, body: Reason) -> forge_adaptations.AdaptationRow:
    """**200, not 202** — nothing is queued. Archiving is one row moving, and it is the one
    mutation on this surface that finishes when the request does.

    Legal from any state a worker does not hold; `ALLOWED` refuses the rest with `MF0300`.
    """
    return forge_adaptations.archive(adaptation_id, who=default_author(), reason=body.reason)
