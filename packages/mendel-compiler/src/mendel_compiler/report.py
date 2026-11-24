"""The decisions report: every choice in a pipeline, who made it and why, as a page (#619).

**A person's view of `pipeline.yml`'s provenance**, for someone who does not read YAML. Each
step's tool, each setting and each optional input carries a `Why` (its tier, who supplied it,
its reason, the facts it rested on, the layer it came from); this lays them out in pipeline
order, and puts every tier-4 choice first under *Flagged for review*, with the rule an AI
choice overrode beside it. Nothing flagged is collapsed or left out.

**One self-contained HTML file**, laid out for print, so a browser's *Save as PDF* makes the
PDF and nothing here needs a PDF library. Derived from the `Pipeline` alone, like the
Nextflow: no registry, no clock, the same bytes for the same pipeline. It holds no path, sample
or file content, because `pipeline.yml` holds none.

Tier words are the served vocabulary (`TIER_VOCABULARY`); `SOURCE_WORDS` names who supplied a
value, because no served wording exists for that yet.
"""

from dataclasses import dataclass, field
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline, Why
from comeni_core.plan.tiers import TIER_VOCABULARY, Tier, ValueSource
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import escape as _escape

_TEMPLATES = Path(__file__).parent / "templates"

SOURCE_WORDS: dict[ValueSource, str] = {
    ValueSource.RESOLVER: "a rule",
    ValueSource.SAID: "the person, when describing the analysis",
    ValueSource.HUMAN: "a person",
    ValueSource.MODEL: "the AI",
    ValueSource.MEASURED: "measured from the data",
    ValueSource.DERIVED: "read from the inputs",
}
"""Who supplied a value, in a reader's words."""

FOOTER = ("Curated tools are reference material for a laboratory to validate. This pipeline is "
          "not a validated clinical test.")


def escape(text: str) -> str:
    """How the page escapes text (the template's own autoescape), for a caller checking what
    it contains."""
    return str(_escape(text))


@dataclass(frozen=True)
class Choice:
    """One decided thing, as the page shows it."""

    step: str
    what: str
    value: str
    tier: str
    who: str
    reason: str
    method: str = ""
    facts: list[str] = field(default_factory=list)
    layer: str = ""
    overrode: str = ""
    flagged: bool = False


def _value(value) -> str:
    if value is None:
        return "not set"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_value(v) for v in value) or "none"
    return str(value)


def _choice(step: str, what: str, why: Why, value=None) -> Choice:
    layer = why.from_layer or ""
    if why.displaced_layer:
        layer = f"{layer} (over {why.displaced_layer})" if layer else f"over {why.displaced_layer}"
    overrode = ""
    if why.overrode:
        o = why.overrode
        overrode = f"Over the rule “{o.rule}”, which gave {_value(o.value)}"
        overrode += f" ({o.cite})." if o.cite else "."
    return Choice(
        step=step, what=what, value=_value(value if value is not None else why.for_value),
        tier=TIER_VOCABULARY[why.tier].name, who=SOURCE_WORDS[why.source], reason=why.reason,
        method=why.axis_reason,
        facts=[f"{p.id} = {_value(p.value)} ({p.origin.value})" for p in why.premise],
        layer=layer, overrode=overrode, flagged=why.tier is Tier.AMBIGUOUS,
    )


def _steps(pipeline: Pipeline) -> list[dict]:
    steps = []
    for step in pipeline.steps:
        tool = _choice(step.id, "tool", step.why, step.module.contract_id)
        needed = _choice(step.id, "why this step", step.presence) if step.presence else None
        settings = [_choice(step.id, s.name, s.why, s.value) for s in step.settings]
        steps.append({
            "id": step.id, "tool": step.module.contract_id, "chosen": tool, "needed": needed,
            "settings": settings,
            "inputs": [{"port": i.port, "state": str(i.state), "by": str(i.by), "reason": i.reason}
                       for i in step.input_states],
        })
    return steps


def _decisions(pipeline: Pipeline) -> list[dict]:
    rows = []
    for d in sorted(pipeline.decisions, key=lambda d: (str(d.subject), str(d.key))):
        human = getattr(d, "human_override", None)
        model = getattr(d, "model_override", None)
        if human is not None:
            answer, who = human, "a person"
        elif model is not None:
            answer, who = model, "the AI"
        else:
            answer, who = getattr(d, "chosen", None), f"a rule ({d.resolved_by})"
        rows.append({
            "subject": str(d.subject), "kind": str(d.kind.value), "answer": _value(answer),
            "who": who, "tier": TIER_VOCABULARY[d.tier].name,
            "reason": getattr(d, "override_reason", "") or d.reason,
            "flagged": d.tier is Tier.AMBIGUOUS,
        })
    return rows


def render(pipeline: Pipeline) -> str:
    """The report: one HTML document."""
    env = Environment(loader=FileSystemLoader(_TEMPLATES), undefined=StrictUndefined,
                      autoescape=True, trim_blocks=True, lstrip_blocks=True,
                      keep_trailing_newline=True)
    steps = _steps(pipeline)
    every = [c for s in steps for c in [s["chosen"], *([s["needed"]] if s["needed"] else []),
                                        *s["settings"]]]
    decisions = _decisions(pipeline)
    layers = [{"name": layer.name, "digest": layer.digest,
               "at": layer.release or (layer.commit or "")[:12]}
              for layer in pipeline.registry.layers]
    return env.get_template("decisions.html.j2").render(
        produces=[str(t) for t in pipeline.intent.want],
        steps=steps,
        flagged=[c for c in every if c.flagged],
        flagged_decisions=[d for d in decisions if d["flagged"]],
        decisions=decisions,
        ai_choices=sorted(({"step": c.node, "what": c.what, "reviewed": c.reviewed}
                           for c in pipeline.ai_choices),
                          key=lambda c: (c["step"], c["what"])),
        layers=layers,
        tiers=[(TIER_VOCABULARY[t].name, TIER_VOCABULARY[t].what) for t in Tier],
        footer=FOOTER,
    )
