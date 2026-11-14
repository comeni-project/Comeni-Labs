"""The builder agent's build tools (#463): resolve the decisions into the pipeline, which the
canvas then draws, and compile it to Nextflow. The engine routes, applies the rules and wires the
modules; the agent never writes pipeline code."""

from comeni_core.diagnostics import coded
from comeni_core.egress.agent import CompiledView, FiredLine, ResolvedView
from mendel_authoring.blueprint import committed
from mendel_authoring.decisions import ActorKind
from mendel_authoring.diff import diff_of

from mendel_api.agent.read import Nothing, built, read_pipeline
from mendel_api.agent.tools import Tool, ToolContext, register
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import decisions, draft_mutations, drafts


def _project(ctx: ToolContext, blueprint) -> None:
    """Every step of the resolved pipeline into the draft, so the canvas and the compiler read
    it. The engine's steps are the AI's to have built: it holds them, and the person reviews."""
    from comeni_core.plan.draft import DraftGraph, DraftProvenance

    graph, provenance = DraftGraph(profile=decisions.goal(ctx.draft_id).profile), DraftProvenance()
    for node in blueprint.order:
        graph, provenance = committed(blueprint, graph, provenance, node, by=ctx.who,
                                      actor_kind=ActorKind.MODEL)
    with session_scope() as db:
        draft = db.get(PipelineDraft, ctx.draft_id)
        draft_mutations.project(db, draft, graph, provenance=provenance.model_dump(mode="json"))


def _fired(blueprint) -> list[FiredLine]:
    fired = []
    for step in blueprint.pipeline.steps:
        site = blueprint.sites.get(step.id)
        if int(step.why.tier) == 3:
            fired.append(FiredLine(
                decides=f"which tool makes {site.type_id if site else step.id} ({step.id})",
                value=step.module.contract_id, reason=step.why.reason,
                cite=step.why.axis_reason))
        fired += [FiredLine(decides=f"{step.id}.{s.name}", value=s.value, reason=s.why.reason,
                            cite=s.why.axis_reason)
                  for s in step.settings if int(s.why.tier) == 3]
    return fired


_LAST: dict[str, object] = {}
"""The blueprint each draft last resolved to in this process, for *what changed*."""


def resolve(ctx: ToolContext, _: Nothing) -> ResolvedView:
    blueprint, unbuilt = built(ctx)
    if blueprint is None:
        return ResolvedView(unbuilt=unbuilt or "nothing is wanted yet")
    before = _LAST.get(ctx.draft_id)
    _LAST[ctx.draft_id] = blueprint
    _project(ctx, blueprint)
    if ctx.session_id is not None:
        # **Kept on the session**: what the page draws and marks as the AI's comes from it,
        # without resolving again on every poll.
        from mendel_api.models import PipelineAuthoringSession
        from mendel_authoring.blueprint import Blueprint

        with session_scope() as db:
            row = db.get(PipelineAuthoringSession, ctx.session_id)
            if before is None and row.blueprint:
                before = Blueprint.model_validate(row.blueprint)
            row.blueprint = blueprint.model_dump(mode="json")
            row.registry_digest = blueprint.registry
    pipeline = read_pipeline(ctx, Nothing())
    said = diff_of(before, blueprint).sentence() if before is not None else "built the pipeline"
    return ResolvedView(
        steps=list(pipeline.steps),
        open_values=[f"{s.node}.{v}" for s in pipeline.steps for v in s.open_values],
        rules=_fired(blueprint),
        changed=said,
    )


def compile_(ctx: ToolContext, _: Nothing) -> CompiledView:
    blueprint, unbuilt = built(ctx)
    if blueprint is None:
        raise ValueError(coded("MI0219", f"there is no pipeline to compile yet: {unbuilt}"))
    _project(ctx, blueprint)
    done = drafts.emitted(ctx.draft_id)
    return CompiledView(main_nf=done.main_nf, nextflow_config=done.config)


for _tool in (
    Tool("resolve", "Build the pipeline from the decisions as they stand: the engine routes, "
         "applies the registry's rules and wires the steps. Returns the steps, what changed, "
         "values still open, and every rule that decided something. The canvas shows it.",
         Nothing, resolve),
    Tool("compile", "Compile the pipeline to Nextflow: main.nf and nextflow.config.", Nothing,
         compile_),
):
    register(_tool)
