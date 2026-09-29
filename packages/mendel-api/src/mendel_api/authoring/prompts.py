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

GOAL: PromptId = "builder.goal.v6"
"""Prose in, the typed **want**, a one-sentence summary, and what was **stated** out. Egress
door 1.

**v4 (2026-09-28, #170)** may report what the person stated as candidates the engine asks them
to confirm: v3 dropped them, and the person was asked again what they had just said.

**v3 (2026-09-28, 14.7.3)** asks for the want only. v2 asked for the whole goal, and a model had
nowhere legal to put *paired-end* and nobody asked for the genome (#105, #114); the engine now
computes what the want needs and asks the person itself. **v2 (2026-09-28)** had fixed v1's
`have` name collision. Both stay on disk because rows cite them; `RETIRED` is how a test holds
that.
"""

RETIRED: tuple[PromptId, ...] = (
    "builder.goal.v1",
    "builder.goal.v2",
    "builder.goal.v3",
    "builder.goal.v4",
    "builder.goal.v5",
    "builder.chat.v1",
    "builder.gap.v1",
    "builder.tier4.v1",
)
"""Superseded templates that stay loadable. An `ai_invocation` row citing one must still reach
the text it ran under, so a retired file is kept, never edited and never deleted."""

CHAT: PromptId = "builder.chat.v2"
"""A follow-up turn in, exactly one declared authoring intent out."""

TIER4: PromptId = "builder.tier4.v2"
"""One tier-4 ambiguity in, one of its own candidates out. Egress door 2.

**Spawn only.** Build mode resolves tier 4 with the flag-only path so the question stays visible
and unanswered; this is the template for the mode that answers it. `choose_one` appends the
candidate list and the reply schema, so what is committed here is the framing and nothing else —
the options are the engine's and are never written into a file.
"""

GAP: PromptId = "builder.gap.v2"
"""A person's typed answer to one gap in, one offered option id or a typed value out, or
*unsure*. Egress door 1. Clicking an option never reaches this: it needs no model (14.7.3)."""

TEMPLATES: tuple[PromptId, ...] = (GOAL, CHAT, TIER4, GAP)
"""**Every current template is split** at `comeni_ai.prompts.DIVIDER` (14.7.4, #183): what never
changes between calls first, as a system message a provider caches, and what does after it.
The v4/v1 files they replace stay loadable, whole, through `RETIRED`."""
"""The four, for the tests that hold every template to the shared block.

§1.3 lists what a model may return, and everything on that list is one of these shapes. The
fourth, `GAP`, was that design decision (spec §6, *Gap questions*): a model reads a person's words
back into an id the engine offered, and authors nothing.
"""


def template(prompt_id: PromptId) -> PromptTemplate:
    """One authoring template, by id.

    Loaded from this package's own directory, so a Forge id cannot resolve here and a builder id
    cannot resolve there. That separation is what keeps *which prompt ran* answerable from the
    id alone.
    """
    return PromptTemplate.load(HERE, prompt_id)
