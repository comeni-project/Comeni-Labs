"""Your graph beside the one the resolver would have built.

**The alignment is the reason this is one endpoint.** Deciding what counts as *the same step*
when you drew HISAT2 and Mendel picked STAR — both emit `alignment.bam` with no state, so they
are interchangeable at the port level and are not the same choice — is a judgement. In the
browser it is a judgement the agent cannot reach, and then there are two answers to *how does my
pipeline differ from Mendel's*.

**Two steps fill the same slot when their produced signatures match.** That reuses
`compatibility.signature` rather than comparing `type_id` and `state` here, so "the same shape of
output" has one definition and Task 4's index cannot drift from this.
"""

from enum import StrEnum

from comeni_core.plan.draft import DraftGraph
from comeni_core.review.verdict import Verdict
from mendel_resolver.compatibility import signature
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict

from mendel_api.services import build, registry
from mendel_api.services import validate as validation


class Alignment(StrEnum):
    SAME = "same"
    """The same contract fills this step in both."""

    DIFFERS = "differs"
    """Both have a step here and chose differently — HISAT2 where Mendel resolved STAR."""

    YOURS_ONLY = "yours-only"
    """A step the resolver did not reach for. Not an error: you may want it."""

    MENDEL_ONLY = "mendel-only"
    """A step you do not have. The missing trimmer, the missing sorter."""


class AlignedStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Alignment
    yours_node: str | None = None
    yours_contract: str | None = None
    mendel_node: str | None = None
    mendel_contract: str | None = None
    why: str = ""
    """The resolver's own reason for its choice, **carried through rather than composed here**.

    A diff explaining itself in words this file invented would be a new author of prose about a
    decision it did not make — which is the shape of defect A79/A107 were, where the registry
    cited the STAR paper as the reason HISAT2 was chosen.
    """


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yours: Verdict
    mendel: build.BuiltPipeline
    alignment: list[AlignedStep]


class CompareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: DraftGraph
    goal: Goal


def _emits(contract_id: str) -> frozenset[str]:
    """The set of signatures a contract produces. Two steps fill one slot when these match."""
    contract = registry.stack().registry.get(contract_id)
    return frozenset(signature(port.type_id, port.state) for port in contract.produces)


def of(graph: DraftGraph, goal: Goal) -> Comparison:
    verdict = validation.of(graph)
    built = build.of(goal)

    yours = [(node.id, node.contract_id) for node in graph.nodes]
    theirs = {step.id: step.contract_id for step in built.steps}
    reasons = {step.id: step.reason for step in built.steps}

    rows: list[AlignedStep] = []
    matched: set[str] = set()

    for node_id, contract_id in yours:
        exact = [t for t, c in theirs.items() if c == contract_id and t not in matched]
        if exact:
            matched.add(exact[0])
            rows.append(
                AlignedStep(
                    state=Alignment.SAME,
                    yours_node=node_id,
                    yours_contract=contract_id,
                    mendel_node=exact[0],
                    mendel_contract=contract_id,
                )
            )
            continue

        shape = _emits(contract_id)
        slot = [t for t, c in theirs.items() if t not in matched and _emits(c) == shape]
        if slot:
            matched.add(slot[0])
            rows.append(
                AlignedStep(
                    state=Alignment.DIFFERS,
                    yours_node=node_id,
                    yours_contract=contract_id,
                    mendel_node=slot[0],
                    mendel_contract=theirs[slot[0]],
                    why=reasons.get(slot[0], ""),
                )
            )
            continue

        rows.append(
            AlignedStep(
                state=Alignment.YOURS_ONLY, yours_node=node_id, yours_contract=contract_id
            )
        )

    for step in built.steps:
        if step.id not in matched:
            rows.append(
                AlignedStep(
                    state=Alignment.MENDEL_ONLY,
                    mendel_node=step.id,
                    mendel_contract=step.contract_id,
                    why=step.reason,
                )
            )

    # Deterministic, so two calls with the same inputs produce the same diff. A diff that
    # reorders between calls is unreadable, and a test holds it.
    rows.sort(key=lambda r: (r.state.value, r.mendel_node or "", r.yours_node or ""))
    return Comparison(yours=verdict, mendel=built, alignment=rows)
