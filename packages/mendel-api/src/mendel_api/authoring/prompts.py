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

GOAL: PromptId = "builder.goal.v8"
"""Prose in, what the person wants and what they said about their data out, as **changes**, each
quoting their words (`Understanding`). Egress door 1.

**v8 (2026-10-13, #307)** replaces `stated` candidates with lists of changes — `wants`, `inputs`,
`facts`, `requires`, `not_offered` — each carrying the person's own words; the engine records a
change whose quote checks and offers the rest as suggestions. It is told what is known
(`{{memory}}`), and it is also the one-step call (`GOAL_ONE_STEP`), shown every type.

**v7 (2026-09-29, #194)** is shown only the types of the families `builder.family.v1` chose,
each family whole, and writes no acknowledgement: the family call wrote it. With the family step
switched off, `GOAL_ONE_STEP` runs instead.

**v4 (2026-09-28, #170)** may report what the person stated as candidates the engine asks them
to confirm: v3 dropped them, and the person was asked again what they had just said.

**v3 (2026-09-28, 14.7.3)** asks for the want only. v2 asked for the whole goal, and a model had
nowhere legal to put *paired-end* and nobody asked for the genome (#105, #114); the engine now
computes what the want needs and asks the person itself. **v2 (2026-09-28)** had fixed v1's
`have` name collision. Both stay on disk because rows cite them; `RETIRED` is how a test holds
that.
"""

RETIRED: tuple[PromptId, ...] = (
    # Superseded by the change lists and the memory (#307): goal.v6 and v7 by goal.v8, chat.v2
    # and gap.v2 by chat.v3, ask.v1 by ask.v2, readback.v1 by readback.v2, family.v3 by v4.
    # chat.v3 by chat.v4 (#324), chat.v4 by chat.v5 (#336).
    "builder.goal.v6",
    "builder.goal.v7",
    "builder.chat.v2",
    "builder.chat.v3",
    "builder.chat.v4",
    "builder.gap.v2",
    "builder.ask.v1",
    "builder.readback.v1",
    "builder.family.v3",
    "builder.goal.v1",
    "builder.goal.v2",
    "builder.goal.v3",
    "builder.goal.v4",
    "builder.goal.v5",
    "builder.chat.v1",
    "builder.gap.v1",
    "builder.tier4.v1",
    "builder.family.v1",
    "builder.family.v2",
    "builder.characterise.v1",
)
"""Superseded templates that stay loadable. An `ai_invocation` row citing one must still reach
the text it ran under, so a retired file is kept, never edited and never deleted."""

GOAL_ONE_STEP: PromptId = GOAL
"""The want call shown **every** type, acknowledging as it goes — what runs when the family step
is switched off (`MENDEL_FAMILY_STEP_FROM`, #194), so the benchmark (#198) compares one step with
two exactly as each shipped."""

FAMILY: PromptId = "builder.family.v4"
"""Prose in, the **families** what the person wants belongs to and the acknowledgement out, or a
question when none fits (#194). Egress door 1, the same payload as the goal call. **v2 (#202):
the verdict first** — `fits` is answered before any family is listed, because v1's empty list was
a way out gemma3:12b skipped past to write the nearest family. **v3 (#202, #208):** `yes` means
a family holds the result itself, never a step on the way (ChIP-seq peaks were read as
`alignment.bam`); the question for a `no` does not steer toward what exists; and it opens with
the shared block, as every template does."""

CHAT: PromptId = "builder.chat.v5"
"""Typed words anywhere after the want is read, in; something to say and the changes they ask
for out (`ChatReply`), each quoting the person (#307).

**v5 (2026-10-15, #336)** has no `proceed`: Continue is the person's. v4's settled two steps
in the second walk, recorded as the person's choice.

**v4 (2026-10-15, #324)** is shown the vocabulary, every measurement with what it holds, and
which subject the waiting question asks about. Never shown a measurement id, v3 answered *"so
100 bp"* on the read-length question with an invented setting, `sequenced_read_length`.

**v3 (2026-10-13, #307)** replaced chat.v2's six intents, which changed nothing, and `gap.v2`: a
typed answer to the open question is a `fact`."""

TIER4: PromptId = "builder.tier4.v2"
"""One tier-4 ambiguity in, one of its own candidates out. Egress door 2.

**Unwired since 14.7.8.3b**: tier 4 stops for a person; this is the template a later *Tier-4
answers* fork will send. `choose_one` appends the
candidate list and the reply schema, so what is committed here is the framing and nothing else —
the options are the engine's and are never written into a file.
"""

GAP: PromptId = "builder.gap.v2"
"""A person's typed answer to one gap in, one offered option id or a typed value out, or
*unsure*. Egress door 1. Clicking an option never reaches this: it needs no model (14.7.3)."""

ASK: PromptId = "builder.ask.v2"
"""One gathering question in, the question in the person's words out, and any answer they
already gave (#167). Prose only: the options and the fact stay the engine's."""

READBACK: PromptId = "builder.readback.v2"
"""The composed goal in, one or two plain sentences out, for the goal card (#176). Written from
what will be built, never from the first sentence."""

CHARACTERISE_FAMILY: PromptId = "builder.characterise-family.v1"
"""The start of a sample in, the families it could belong to out (14.7.7). Egress door 6.
The first of the characteriser's two calls, the family step goal extraction takes (#194)."""

CHARACTERISE: PromptId = "builder.characterise.v2"
"""The start of a sample in, its declared type, the states and measurements it states, and
what it states that nothing declares (`unmatched`, stored only) out (14.7.7). Egress door 6.
**v2 (#244):** each state and measurement quotes the line that states it, and the engine checks
the quote; walked live, v1's model listed states no line showed."""

TEMPLATES: tuple[PromptId, ...] = (
    GOAL,
    FAMILY,
    CHAT,
    TIER4,
    ASK,
    READBACK,
    CHARACTERISE_FAMILY,
    CHARACTERISE,
)
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
