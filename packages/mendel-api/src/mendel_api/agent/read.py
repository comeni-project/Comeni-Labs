"""The builder agent's read tools (#463): the decisions, the pipeline as built, one step in full,
the registry around a type, the rules for a role, the facts, and what is still needed.

Every view names types in words beside their ids. Reading the pipeline resolves the decisions
as they stand, so the agent always reads what the engine would build now.
"""

from comeni_core.diagnostics import coded
from comeni_core.egress.agent import (
    ChoiceLine,
    FactLine,
    FactsView,
    GoalView,
    InputLine,
    MeasureLine,
    NeedLine,
    NeedsView,
    PipelineView,
    RuleLine,
    RulesView,
    SettingLine,
    StepLine,
    StepView,
    ToolRef,
    ToolsView,
    TypeLine,
    VocabularyView,
)
from mendel_authoring.brief import tool_of
from pydantic import BaseModel, Field

from mendel_api.agent.tools import Tool, ToolContext, register
from mendel_api.authoring.types import FactKind
from mendel_api.services import authoring_decisions, decisions, explain, gaps, protection, registry


class Nothing(BaseModel):
    """No arguments."""


class StepArgs(BaseModel):
    node: str = Field(description="The step's id, as read_pipeline lists it, e.g. star_align")


class TypeArgs(BaseModel):
    type_id: str = Field(description="A declared type id, e.g. alignment.bam")


class RoleArgs(BaseModel):
    role: str = Field(description="A role a tool fills, e.g. alignment or trimming")


def _type_line(stack, type_id: str, states=()) -> TypeLine:
    return TypeLine(type_id=type_id, name=stack.vocabulary.names.get(type_id, type_id),
                    states=sorted(states))


def _tool_name(stack, contract_id: str) -> str:
    tool = stack.tools.tools.get(tool_of(contract_id))
    return tool.name if tool else tool_of(contract_id)


def list_vocabulary(ctx: ToolContext, _: Nothing) -> VocabularyView:
    """Every type and measurement the registry declares, sorted by id."""
    stack = registry.stack()
    types = [_type_line(stack, t, stack.vocabulary.types[t])
             for t in sorted(stack.vocabulary.types)]
    measures = []
    for mid in sorted(stack.measurements.ids()):
        m = stack.measurements.get(mid)
        measures.append(MeasureLine(
            measurement=mid, name=(m.description or mid)[:200], kind=str(m.kind),
            values=[str(v) for v in (m.values or [])], unit=str(m.unit or ""),
            describes=m.describes or None))
    return VocabularyView(types=types, measurements=measures)


def built(ctx: ToolContext):
    """The pipeline the engine builds from the decisions now, or why it cannot."""
    from mendel_api.services import blueprint as bp

    try:
        blueprint, _ = bp.resolve(decisions.goal(ctx.draft_id))
    except (ValueError, KeyError, LookupError) as unbuilt:
        return None, " ".join(str(unbuilt).split())[:300]
    return blueprint, ""


def read_goal(ctx: ToolContext, _: Nothing) -> GoalView:
    stack, current = registry.stack(), decisions.read(ctx.draft_id)
    choices = [ChoiceLine(subject=f"the tool that makes {p.site.type_id}", value=p.contract,
                          by=p.by, because=p.because)
               for p in current.producers if p.contract is not None]
    choices += [ChoiceLine(subject=f"the setting {p.name}", value=p.value, by=p.by,
                           because=p.because)
                for p in current.parameters if p.value is not None]
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineDraft

    with session_scope() as db:
        name = db.get(PipelineDraft, ctx.draft_id).name or ""
    return GoalView(
        name=name[:200],
        wants=[_type_line(stack, w.type_id, w.states) for w in current.wants if w.present],
        have=[_type_line(stack, i.type_id, i.states) for i in current.inputs if i.present],
        facts=[FactLine(measurement=f.subject, value=f.value, source=f.origin.value)
               for f in current.facts],
        choices=choices,
    )


def read_pipeline(ctx: ToolContext, _: Nothing) -> PipelineView:
    stack = registry.stack()
    blueprint, unbuilt = built(ctx)
    if blueprint is None:
        return PipelineView(unbuilt=unbuilt or "nothing is wanted yet")
    pipeline = blueprint.pipeline
    steps = []
    for step in pipeline.steps:
        contract = stack.routing.get(step.module.contract_id)
        steps.append(StepLine(
            node=step.id,
            contract=step.module.contract_id,
            tool=_tool_name(stack, step.module.contract_id),
            reads=sorted({p.type_id for p in contract.consumes if p.type_id}),
            makes=sorted({p.type_id for p in contract.produces if p.type_id}),
            chosen_by=step.why.source.value,
            open_values=[s.name for s in step.settings if s.value is None and s.at_run is None],
            ai_unreviewed=(step.why.source.value == "model"
                           or any(s.why.source.value == "model" for s in step.settings)),
        ))
    return PipelineView(
        steps=steps,
        inputs=[_type_line(stack, c.type_id) for c in pipeline.channels],
        gives=[_type_line(stack, t) for t in pipeline.goal.want],
    )


def read_step(ctx: ToolContext, args: StepArgs) -> StepView:
    stack = registry.stack()
    blueprint, unbuilt = built(ctx)
    if blueprint is None:
        raise ValueError(coded("MI0204", f"there is no pipeline yet: {unbuilt}"))
    step = next((s for s in blueprint.pipeline.steps if s.id == args.node), None)
    if step is None:
        known = ", ".join(s.id for s in blueprint.pipeline.steps)
        raise KeyError(coded("MI0204", f"no step called {args.node}; the steps are {known}"))
    contract = stack.routing.get(step.module.contract_id)
    tool = stack.tools.tools.get(tool_of(contract.id))
    return StepView(
        node=step.id,
        contract=contract.id,
        tool=_tool_name(stack, contract.id),
        description=" ".join((tool.description or "").split()) if tool else "",
        does=contract.does or "",
        why_here=step.presence.reason if step.presence else "",
        chosen=step.why.reason,
        chosen_tier=int(step.why.tier),
        inputs=[InputLine(name=p.name, type_id=p.type_id, optional=not p.required)
                for p in contract.consumes],
        settings=[SettingLine(name=s.name, value=s.value, tier=int(s.why.tier),
                              source=s.why.source.value, reason=s.why.reason,
                              cite=s.why.axis_reason)
                  for s in step.settings],
    )


def find_tools(ctx: ToolContext, args: TypeArgs) -> ToolsView:
    stack = registry.stack()
    if args.type_id not in stack.vocabulary.names and args.type_id not in \
            registry.builder_types(stack):
        raise KeyError(coded("MI0204", f"{args.type_id} is not a type this registry declares"))

    def ref(contract) -> ToolRef:
        return ToolRef(contract=contract.id, tool=_tool_name(stack, contract.id),
                       roles=sorted(contract.roles))

    readers = [c for c in stack.registry.all()
               if any(a.type_id == args.type_id for p in c.consumes for a in p.alternatives())]
    return ToolsView(
        type_id=args.type_id,
        name=stack.vocabulary.names.get(args.type_id, args.type_id),
        makes=[ref(c) for c in stack.registry.producers_of(args.type_id, frozenset())],
        reads=[ref(c) for c in readers],
    )


def _predicate(value) -> str:
    if isinstance(value, BaseModel):
        return ", ".join(f"{k} {v}" for k, v in value.model_dump(exclude_none=True).items())
    return str(value)


def _row(row) -> str:
    when = " and ".join(f"{fact} {_predicate(test)}" for fact, test in row.when.items())
    then = row.then.fact if hasattr(row.then, "fact") else row.then
    return f"{when or 'otherwise'} → {then}"


def read_rules(ctx: ToolContext, args: RoleArgs) -> RulesView:
    stack = registry.stack()
    found = [d for d in stack.rules.decisions if any(t.of == args.role for t in d.targets())]
    if not found and not any(args.role in c.roles for c in stack.registry.all()):
        raise KeyError(coded("MI0204", f"no step fills a role called {args.role}"))
    return RulesView(role=args.role, rules=[
        RuleLine(decides=", ".join(t.key() for t in d.targets()),
                 rows=[" ".join(_row(r).split())[:300] for r in d.rows],
                 because=" ".join((d.because or "").split())[:500],
                 cite=" ".join((d.cite or "").split())[:300])
        for d in found])


def read_facts(ctx: ToolContext, _: Nothing) -> FactsView:
    current = decisions.read(ctx.draft_id)
    samples: list[str] = []
    if ctx.session_id and protection.allows(protection.Crossing.AGENT):
        from mendel_api.db import session_scope
        from mendel_api.models import PipelineAuthoringSession

        with session_scope() as db:
            row = db.get(PipelineAuthoringSession, ctx.session_id)
            samples = [str(s.get("name")) for s in (row.samples or []) if s.get("name")]
    return FactsView(
        facts=[FactLine(measurement=f.subject, value=f.value, source=f.origin.value)
               for f in current.facts],
        samples=samples,
    )


def what_is_needed(ctx: ToolContext, _: Nothing) -> NeedsView:
    stack, current = registry.stack(), decisions.read(ctx.draft_id)
    wants = [w for w in current.wants if w.present]
    found = gaps.gaps([w.type_id for w in wants], authoring_decisions.facts(ctx.draft_id), stack,
                      required={w.type_id: list(w.states) for w in wants if w.states},
                      absent=[i.type_id for i in current.inputs if not i.present])
    if isinstance(found, gaps.Unreachable):
        return NeedsView(needs=[NeedLine(
            kind="unreachable", subject=found.subject,
            name=stack.vocabulary.names.get(found.subject, found.subject),
            why="nothing in the registry makes it")])
    return NeedsView(needs=[
        NeedLine(kind=g.kind.value, subject=g.subject,
                 name=explain.name_of(stack, FactKind(g.kind), g.subject),
                 why=g.why, optional=g.optional)
        for g in found])


for _tool in (
    Tool("list_vocabulary", "Every type and measurement the registry declares, by exact id: read "
         "this before naming a type (want, have) or a fact (set_fact).", Nothing, list_vocabulary),
    Tool("read_goal", "What is wanted, what the person has, the facts about their data, and the "
         "tools and values chosen so far, with who chose them.", Nothing, read_goal),
    Tool("read_pipeline", "The pipeline the engine builds from the decisions now: each step, "
         "what it reads and makes, who chose it, and values still open.", Nothing,
         read_pipeline),
    Tool("read_step", "One step in full: the tool, what it does, why it is here, why this tool, "
         "and every setting with its value, how it was decided, and the citation.", StepArgs,
         read_step),
    Tool("find_tools", "Which tools in the registry make a type, and which read it.", TypeArgs,
         find_tools),
    Tool("read_rules", "The registry's rules for a role: what each decides, its conditions, "
         "why, and its citation. Rules are advice: you may choose otherwise, with a reason.",
         RoleArgs, read_rules),
    Tool("read_facts", "The facts about the person's data, and their samples by name.", Nothing,
         read_facts),
    Tool("what_is_needed", "What the wanted results still need that nothing settles: inputs "
         "to ask for and facts to find out.", Nothing, what_is_needed),
):
    register(_tool)
