"""Read a saved alternative with one joined SELECT, without changing its offer."""

from comeni_core.diagnostics import coded
from sqlalchemy import select
from sqlalchemy.orm import undefer

from mendel_api.authoring.canvas import AlternativePreview, checked_previews
from mendel_api.authoring.envelopes import OfferContext, StepOffer
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.services import blueprint as bp
from mendel_api.settings import settings


def read(session_id: str, proposal_id: str, option_id: str,
         expected: OfferContext) -> AlternativePreview:
    statement = (select(PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft)
                 .join(PipelineAuthoringSession,
                       PipelineAuthoringProposal.session_id == PipelineAuthoringSession.id)
                 .join(PipelineDraft, PipelineAuthoringSession.draft_id == PipelineDraft.id)
                 .options(undefer(PipelineAuthoringProposal.preview_views))
                 .where(PipelineAuthoringProposal.id == proposal_id,
                        PipelineAuthoringSession.id == session_id))
    with session_scope() as db:
        found = db.execute(statement).one_or_none()
        if found is None:
            raise KeyError(proposal_id)
        proposal, row, draft = found
        if proposal.state != "pending":
            raise ValueError(coded("MI0203", "this proposal has already been settled"))
        if proposal.kind != "step":
            raise ValueError(coded("MI0205", "this proposal has no alternative preview"))
        current = OfferContext(draft_revision=draft.revision,
                               decision_revision=draft.decision_revision,
                               session_version=row.row_version, registry=row.registry_digest)
        if expected != current:
            raise ValueError(coded("MI0201", "the preview context changed; re-read the build"))
        offer = StepOffer.model_validate(proposal.payload)
        if (offer.context.draft_revision != current.draft_revision
                or offer.context.decision_revision != current.decision_revision
                or offer.context.registry != current.registry
                or bp.registry_digest([settings.registry_root]) != current.registry):
            raise ValueError(coded("MI0201", "the draft or registry changed after this offer"))
        if option_id not in offer.amendments:
            raise ValueError(coded("MI0205", "that alternative was not offered"))
        if proposal.preview_views is None or option_id not in offer.preview_options:
            raise ValueError(coded("MI0218", "Preview unavailable for this older offer"))
        snapshots = checked_previews(proposal.preview_views, proposal.payload, proposal_id)
        return AlternativePreview.model_validate(snapshots[option_id]).model_copy(
            update={"observed_context": current})
