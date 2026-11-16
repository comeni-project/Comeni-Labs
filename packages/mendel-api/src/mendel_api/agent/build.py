"""The builder agent's build tools (#463): resolve the decisions into the pipeline, which the
canvas then draws, and compile it to Nextflow. The engine routes, applies the rules and wires the
modules; the agent never writes pipeline code."""

from comeni_core.diagnostics import coded
from comeni_core.egress.agent import CompiledView, FiredLine, ResolvedView
from mendel_authoring.blueprint import committed
from mendel_authoring.decisions import ActorKind
from mendel_authoring.diff import diff_of

from mendel_api.agent.read import built, read_pipeline, what_is_needed
from mendel_api.agent.tools import Nothing, Tool, ToolContext, register
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import decisions, draft_mutations, drafts


def _project(ctx: ToolContext, blueprint, resolved_from: int) -> None:
    """Every step of the resolved pipeline into the draft, so the canvas and the compiler read
    it. The engine's steps are the AI's to have built: it holds them, and the person reviews."""
    from comeni_core.plan.draft import DraftGraph, DraftProvenance

    graph, provenance = DraftGraph(profile=decisions.goal(ctx.draft_id).profile), DraftProvenance()
    for node in blueprint.order:
        graph, provenance = committed(blueprint, graph, provenance, node, by=ctx.who,
                                      actor_kind=ActorKind.MODEL)
    with session_scope() as db:
        draft = db.get(PipelineDraft, ctx.draft_id, with_for_update=True)
        draft_mutations.project(db, draft, graph, provenance=provenance.model_dump(mode="json"),
                                resolved_from=resolved_from)


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


def resolve(ctx: ToolContext, _: Nothing) -> ResolvedView:
    resolved_from = decisions.revision(ctx.draft_id)
    blueprint, unbuilt = built(ctx)
    if blueprint is None:
        return ResolvedView(unbuilt=unbuilt or "nothing is wanted yet",
                            needs=what_is_needed(ctx, Nothing()).needs)
    _project(ctx, blueprint, resolved_from)
    before = None
    if ctx.session_id is not None:
        # **Kept on the session**: what the page draws and marks as the AI's comes from it,
        # without resolving again on every poll; the one it replaces is what changed.
        from mendel_authoring.blueprint import Blueprint

        from mendel_api.models import PipelineAuthoringSession

        with session_scope() as db:
            row = db.get(PipelineAuthoringSession, ctx.session_id)
            if row.blueprint:
                before = Blueprint.model_validate(row.blueprint)
            row.blueprint = blueprint.model_dump(mode="json")
            row.registry_digest = blueprint.registry
    pipeline = read_pipeline(ctx, Nothing())
    said = diff_of(before, blueprint).sentence() if before is not None else "built the pipeline"
    return ResolvedView(
        steps=list(pipeline.steps),
        open_values=[f"{s.node}.{v}" for s in pipeline.steps for v in s.open_values],
        rules=_fired(blueprint),
        needs=what_is_needed(ctx, Nothing()).needs,
        changed=said,
    )


def compile_(ctx: ToolContext, _: Nothing) -> CompiledView:
    resolved_from = decisions.revision(ctx.draft_id)
    blueprint, unbuilt = built(ctx)
    if blueprint is None:
        raise ValueError(coded("MI0219", f"there is no pipeline to compile yet: {unbuilt}"))
    _project(ctx, blueprint, resolved_from)
    done = drafts.emitted(ctx.draft_id)
    processes = sorted({step.process for step in blueprint.pipeline.steps})
    return CompiledView(processes=processes, main_nf_lines=len(done.main_nf.splitlines()),
                        config_lines=len(done.config.splitlines()))


for _tool in (
    Tool("resolve",
         "Build the pipeline from the decisions. Returns its steps, what changed, open values, "
         "fired rules and what is still needed. The canvas shows it.",
         
         Nothing, resolve),
    Tool("compile", "Compile to Nextflow; says it compiled and lists the processes.",
         Nothing, compile_),
):
    register(_tool)
