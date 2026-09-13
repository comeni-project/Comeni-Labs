"""The builder's committed prompt text, and the only place that knows where it lives.

**Prompt text is here and not in `comeni-ai`.** That package loads, renders and versions a
caller's templates; what those templates *say* about goals, vocabulary and steps belongs to the
caller. `mendel_forge.prompts` is the same arrangement one agent over, and the reason it is two
directories rather than one shared pile is that the two agents share a transport and share
nothing else: the Forge's rules are about evidence ids and registry vocabulary, and these are
about a goal, the ids the engine issued, and invariant 15.

**Changing behaviour means adding a `v2`, never editing a `v1`.** An `ai_invocation` row cites
the prompt id it ran under, and somebody re-reading a session six months later has to be able to
reach the instruction the model was actually given. An edited `v1` makes every row that cites it
quietly wrong — the same property `pipeline.yml` buys by pinning contracts to a content digest.
`test_the_digest_is_over_the_rendered_text_and_not_the_template` is the mechanical half.
"""

from pathlib import Path

from comeni_ai import PromptId, PromptTemplate

HERE = Path(__file__).parent / "prompts"
"""The prompt files sit *inside* the package rather than beside it, which is what makes
hatchling carry them into a wheel — the same arrangement `py.typed` already relies on. A
prompts directory at the repository root would work in an editable install and be absent from
every built artifact, and the symptom would be an empty prompt rather than an import error.
`test_the_templates_ship_inside_the_built_wheel` builds one and looks.
"""

GOAL: PromptId = "builder.goal.v1"
"""Prose in, a typed `Goal` and a plain-language summary out. Egress door 1."""

CHAT: PromptId = "builder.chat.v1"
"""A follow-up turn in, exactly one declared authoring intent out."""

TIER4: PromptId = "builder.tier4.v1"
"""One tier-4 ambiguity in, one of its own candidates out. Egress door 2.

**Spawn only.** Build mode resolves tier 4 with the flag-only path so the question stays visible
and unanswered; this is the template for the mode that answers it. `choose_one` appends the
candidate list and the reply schema, so what is committed here is the framing and nothing else —
the options are the engine's and are never written into a file.
"""

TEMPLATES: tuple[PromptId, ...] = (GOAL, CHAT, TIER4)
"""The three, for the tests that hold every template to the shared block.

Three calls and not more: §1.3 lists what a model may return, and everything on that list is one
of these shapes. A fourth template would be a fourth thing a model is asked to author, which is a
design decision rather than a file.
"""


def template(prompt_id: PromptId) -> PromptTemplate:
    """One authoring template, by id.

    Loaded from this package's own directory, so a Forge id cannot resolve here and a builder id
    cannot resolve there. That separation is what keeps *which prompt ran* answerable from the
    id alone.
    """
    return PromptTemplate.load(HERE, prompt_id)
