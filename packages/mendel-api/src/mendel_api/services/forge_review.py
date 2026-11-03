"""Optional advice about immutable item revisions; this service applies no commands."""

import asyncio
import hashlib
import json

import sqlalchemy as sa
from comeni_ai import Client
from mendel_forge.forging.model import Piece, Status
from pydantic import BaseModel

from mendel_api import db, jobs
from mendel_api.forge.replies import ReviewReply
from mendel_api.invocations import InvocationPurpose
from mendel_api.models import ForgeMessage, ForgeReview
from mendel_api.services import forging, forging_ai


class ReviewView(BaseModel):
    item: str
    revision: int
    comment: str
    quote: str | None
    file: str | None
    model: str


def read(adaptation_id: str) -> list[ReviewView]:
    state = forging.load(adaptation_id)
    with db.session_scope() as session:
        rows = session.scalars(sa.select(ForgeReview).where(
            ForgeReview.adaptation == adaptation_id).order_by(ForgeReview.item)).all()
        return [ReviewView(item=r.item, revision=r.revision, comment=r.comment,
                          quote=r.quote, file=r.file, model=r.model) for r in rows
                if r.item in state.items and state.items[r.item].current.n == r.revision
                and state.items[r.item].status is not Status.REMOVED]


async def queue_review(adaptation_id: str, piece: str, revisions: dict[str, int]) -> None:
    if forging_ai._client(InvocationPurpose.REVIEW) is None:
        return
    digest = hashlib.sha256(json.dumps(revisions, sort_keys=True).encode()).hexdigest()
    seq = forging.post_message(adaptation_id, role="engine", pending=True,
                              content="The reviewer is waiting to read this piece.")
    try:
        queued = await jobs.enqueue("review_forge_piece", adaptation_id, piece, revisions, seq,
            queue=jobs.AI_QUEUE, job_id=jobs.job_id_for("forge", "review", adaptation_id, digest))
        if not queued:
            _finish(adaptation_id, seq, "This piece is already queued for review.")
    except Exception:
        _finish(adaptation_id, seq, "The reviewer could not be queued. The piece is ready for you.")


def _finish(adaptation_id: str, seq: int, text: str) -> None:
    with db.session_scope() as session:
        message = session.scalar(sa.select(ForgeMessage).where(
            ForgeMessage.adaptation == adaptation_id, ForgeMessage.seq == seq))
        if message is not None:
            message.pending = False
            message.content = text


def review_piece(adaptation_id: str, piece: str, revisions: dict[str, int],
                 client: Client | None = None) -> None:
    client = client or forging_ai._client(InvocationPurpose.REVIEW)
    if client is None:
        return
    adaptation = forging.row(adaptation_id)
    if adaptation.abandoned_at is not None:
        return
    state = forging.load(adaptation_id)
    # A queued review must not read a different revision under an old revision number.
    wanted = {key: n for key, n in revisions.items() if key in state.items
              and state.items[key].current.n == n and state.items[key].status is not Status.REMOVED
              and key.startswith(piece + ":")}
    with db.session_scope() as session:
        existing = {(r.item, r.revision) for r in session.scalars(sa.select(ForgeReview).where(
            ForgeReview.adaptation == adaptation_id))}
    wanted = {k: n for k, n in wanted.items() if (k, n) not in existing}
    if not wanted:
        return
    request = forging_ai.compose(adaptation, state, Piece(piece), "forge.review.v1")
    request = request.model_copy(update={"items": [i for i in request.items if i.key in wanted]})
    forging.record(adaptation_id, "started", what="reviewing", piece=piece)
    reply, invocation = forging_ai._call("forge.review.v1", request, ReviewReply, client,
                                         adaptation_id, 1, attempts=1)
    if reply is None:
        raise ValueError("The reviewer did not return usable comments.")
    keys = [c.item for c in reply.comments]
    if len(keys) != len(set(keys)) or set(keys) != set(wanted):
        raise ValueError("The reviewer did not comment on exactly the items it was given.")
    folder = forging.module_folder(adaptation.source, adaptation.path)
    sources = {name: text for name, text in {
        "main.nf": request.module.main_nf, "meta.yml": request.module.meta_yml,
        "tests/main.nf.test": request.module.nf_test,
    }.items() if (folder / name).is_file()}
    forging.record(adaptation_id, "checking")
    with db.transaction() as session:
        forging.lock(session, adaptation_id)
        existing = {(r.item, r.revision) for r in session.scalars(sa.select(ForgeReview).where(
            ForgeReview.adaptation == adaptation_id))}
        for comment in reply.comments:
            if (comment.item, wanted[comment.item]) in existing:
                continue
            quote = comment.quote
            if not quote or quote not in sources.get(comment.file, ""):
                quote = None
            session.add(ForgeReview(adaptation=adaptation_id, item=comment.item,
                revision=wanted[comment.item], comment=comment.comment, quote=quote,
                file=comment.file if quote else None,
                model=client.access.model, invocation=invocation))
    forging.record(adaptation_id, "saved", items=0, comments=len(reply.comments))


async def review_forge_piece(ctx: dict, adaptation_id: str, piece: str,
                             revisions: dict[str, int], seq: int) -> None:
    try:
        await asyncio.to_thread(review_piece, adaptation_id, piece, revisions)
    except asyncio.CancelledError:
        _finish(adaptation_id, seq, "The review stopped. The piece is ready for you.")
        raise
    except Exception:
        _finish(adaptation_id, seq, "The reviewer could not finish. The piece is ready for you.")
    else:
        _finish(adaptation_id, seq,
                "The review finished. Comments apply only to the revision reviewed.")
