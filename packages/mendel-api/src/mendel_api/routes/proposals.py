"""Rules proposed from people's answers (#462): the Learned rules page's reads and verbs.

Approving writes a rule file to this installation's own registry layer; withdrawing removes it.
Every verb is a person's, recorded by name."""

from fastapi import APIRouter

from mendel_api import jobs
from mendel_api.identity import default_author
from mendel_api.refusals import REFUSES
from mendel_api.services import proposals

router = APIRouter(prefix="/rules", tags=["rules"])


async def _view() -> proposals.ProposalsView:
    view = proposals.read()
    return view.model_copy(
        update={"running": await jobs.running(proposals.JOB_ID, jobs.AI_QUEUE)})


@router.get("/proposals", operation_id="readRuleProposals",
            summary="Rules proposed from people's answers, refused targets, and rules in use")
async def read_rule_proposals() -> proposals.ProposalsView:
    return await _view()


@router.post("/proposals/run", operation_id="proposeRules", status_code=202, responses=REFUSES,
             summary="Ask the model again for each target whose answers changed")
async def propose_rules() -> proposals.ProposalsView:
    await proposals.start()
    return await _view()


@router.post("/proposals/{proposal_id}/approve", operation_id="approveRuleProposal",
             responses=REFUSES, summary="Put a proposed rule in force in this installation")
async def approve_rule_proposal(proposal_id: str) -> proposals.ProposalsView:
    proposals.approve(proposal_id, default_author())
    return await _view()


@router.post("/proposals/{proposal_id}/reject", operation_id="rejectRuleProposal",
             responses=REFUSES, summary="Reject a proposed rule")
async def reject_rule_proposal(proposal_id: str) -> proposals.ProposalsView:
    proposals.reject(proposal_id, default_author())
    return await _view()


@router.post("/learned/{name}/withdraw", operation_id="withdrawLearnedRule", responses=REFUSES,
             summary="Remove a learned rule; its question is asked again")
async def withdraw_learned_rule(name: str) -> proposals.ProposalsView:
    proposals.withdraw(name, default_author())
    return await _view()
