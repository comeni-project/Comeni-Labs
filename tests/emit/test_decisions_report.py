"""The decisions report: every choice in a pipeline, who made it and why, for a person (#619).

It reads `pipeline.yml` alone, so these build a real pipeline and then set the provenance a
build can produce (an AI choice over a rule, a person's answer) rather than run an agent.
"""

import re

import pytest
from comeni_core.artifact.pipeline import AiChoice, Pipeline, Why
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.plan.ir import Overrode
from comeni_core.plan.tiers import TIER_VOCABULARY, Tier, ValueSource
from mendel_compiler import report
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of
from support.paths import ROOT

STAR = "nf-core/star/align@2.7.11b"
GENOME = "nf-core/star/genomegenerate@2.7.11b"
HOSTILE = "<script>alert(1)</script> & \"more\""
FOOTER = ("Curated tools are reference material for a laboratory to validate. This pipeline is "
          "not a validated clinical test.")


@pytest.fixture(scope="module")
def built() -> Pipeline:
    stack = layers.load(ROOT / "registry")
    graph = DraftGraph(
        nodes=[DraftNode(id="index", contract_id=GENOME), DraftNode(id="align", contract_id=STAR)],
        edges=[DraftEdge(from_node="index", from_port="index", to_node="align", to_port="index")],
    )
    pipeline = Pipeline.of(ir_of(graph, stack), stack.registry, stack.vocabulary,
                           stack.measurements, stack.paths, goal=goal_of(graph, stack))
    assert pipeline.steps and any(step.settings for step in pipeline.steps)
    return pipeline


def _with_ai_choice(pipeline: Pipeline) -> tuple[Pipeline, str, str]:
    """The first setting of the first step that has one, set by the AI over a rule."""
    steps = list(pipeline.steps)
    at = next(i for i, step in enumerate(steps) if step.settings)
    step = steps[at]
    first = step.settings[0]
    why = Why(tier=Tier.AMBIGUOUS, source=ValueSource.MODEL, reason=HOSTILE,
              for_value=first.value,
              overrode=Overrode(rule="the rule-of-thumb rule", value="its own value",
                                cite="a cited paper"))
    settings = [first.model_copy(update={"why": why}), *step.settings[1:]]
    steps[at] = step.model_copy(update={"settings": settings})
    choice = AiChoice(node=step.id, what=f"set {first.name}", reviewed=False)
    changed = pipeline.model_copy(update={"steps": steps, "ai_choices": [choice]})
    return changed, step.id, first.name


def _section(html: str, heading: str) -> str:
    """The text from `heading` to the next `<h2`."""
    start = html.index(heading)
    end = html.find("<h2", start + len(heading))
    return html[start:] if end < 0 else html[start:end]


def test_every_choice_appears_with_its_reason(built):
    html = report.render(built)
    reasons = [s.why.reason for step in built.steps for s in step.settings]
    assert reasons
    for step in built.steps:
        assert step.id in html
        assert step.module.contract_id in html
        assert report.escape(step.why.reason) in html
        for setting in step.settings:
            assert f"<code>{setting.name}</code>" in html
            assert report.escape(setting.why.reason) in html


def test_flagged_for_review_comes_first_and_holds_every_tier_4(built):
    pipeline, step_id, name = _with_ai_choice(built)
    html = report.render(pipeline)
    flagged = _section(html, "Flagged for review")
    assert html.index("Flagged for review") < html.index('id="step-')
    assert report.escape(HOSTILE) in flagged
    assert "the rule-of-thumb rule" in flagged and "its own value" in flagged
    assert step_id in flagged and name in flagged
    assert "the AI" in flagged


def test_nothing_flagged_says_so(built):
    """Said, not left out: an empty section would read as a page that forgot to look."""
    quiet = built.model_copy(update={"steps": [], "decisions": [], "ai_choices": []})
    assert "Nothing is flagged for review." in report.render(quiet)
    assert "Nothing is flagged for review." not in report.render(_with_ai_choice(built)[0])


def test_who_decided_uses_the_served_words(built):
    html = report.render(built)
    tiers = {s.why.tier for step in built.steps for s in step.settings}
    assert tiers
    for tier in tiers:
        assert TIER_VOCABULARY[tier].name in html


def test_every_source_has_words():
    assert set(report.SOURCE_WORDS) == set(ValueSource)


def test_text_is_escaped(built):
    pipeline, _, _ = _with_ai_choice(built)
    html = report.render(pipeline)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; &#34;more&#34;" in html


def test_the_same_pipeline_renders_the_same_bytes(built):
    assert report.render(built) == report.render(built)


def test_the_footer_states_what_the_tools_are(built):
    text = re.sub(r"\s+", " ", report.render(built))
    assert FOOTER in text


def test_it_is_a_whole_page_that_prints(built):
    html = report.render(built)
    assert html.startswith("<!doctype html>")
    assert "@media print" in html
    assert "<link" not in html and "<script" not in html, "self-contained: no fetched assets"
