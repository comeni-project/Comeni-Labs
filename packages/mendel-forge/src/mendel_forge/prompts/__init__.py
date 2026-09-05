"""The Forge's committed prompt text, and the only place that knows where it lives.

**Prompt text is here and not in `comeni-ai`.** That package loads, renders and versions a
caller's templates; what those templates *say* about contracts, roles and Nextflow belongs to
the caller. §5.1 puts it plainly — shared infrastructure that accumulates every agent's
prompts has stopped being a boundary and become a pile.

**Changing behaviour means adding a `v2`, never editing a `v1`.** A stored review record cites
a template id, and a reviewer six months later has to be able to read the instruction the model
was actually given. An edited `v1` makes every record that cites it quietly wrong — the same
property `pipeline.yml` buys by pinning contracts to a content digest.

A hole names its fragment through `hole_manifest.HINTS`, and
`test_ai_prompts.py::test_every_hint_a_hole_can_name_is_a_committed_file` holds that every one
of those ids resolves. That is what makes the count of fragments self-enforcing rather than
something somebody has to remember when a `HoleKind` is added.
"""

from pathlib import Path

from comeni_ai import PromptId, PromptTemplate

HERE = Path(__file__).parent
"""The prompt files sit *inside* the package rather than beside it, which is what makes
hatchling carry them into a wheel — the same arrangement `py.typed` already relies on. A
prompts directory at the repository root would work in an editable install and be absent from
every built artifact, and the symptom would be an empty prompt rather than an import error.
"""

HINTS_DIR = HERE / "hints"

ANALYSIS: PromptId = "forge.analysis.v1"
IMPLEMENTATION: PromptId = "forge.implementation.v1"
REPAIR: PromptId = "forge.repair.v1"

REVIEW_CHAT: PromptId = "forge.review-chat.v1"

TEMPLATES: tuple[PromptId, ...] = (ANALYSIS, IMPLEMENTATION, REPAIR, REVIEW_CHAT)
"""§5.2's four.

**`forge.review-chat.v1` waited on a decision rather than on an implementation**, and the
decision was taken on 2026-09-05: it is **egress door 5**, `forge_review`, carrying
`ForgeReviewRequest`. A curator's message is free text typed at request time and sent to a
model — which is the one leg the forge's 2026-08-17 exemption stood on. The other three
templates never touch curator prose, which is why they did not wait.

`GENERATION` below is the set that carries §5.4's shared invariant block *and* takes a dossier;
the chat is held to the same block and composes its context differently, because it is grounded
on a revision rather than on a scaffold.
"""

GENERATION: tuple[PromptId, ...] = (ANALYSIS, IMPLEMENTATION, REPAIR)
"""The templates that put a dossier in front of a model and ask for a `Proposal`."""


def template(prompt_id: PromptId) -> PromptTemplate:
    """One task template, by id."""
    return PromptTemplate.load(HERE, prompt_id)


def hint(prompt_id: PromptId) -> PromptTemplate:
    """One instruction fragment, by the id a `ScaffoldHole` names in `HINTS`.

    Separate directory rather than a naming convention, because the two are loaded for
    different reasons: a template is chosen by the task, a fragment by the question. A flat
    directory would let `template("ports.state.v1")` succeed and produce a prompt consisting
    entirely of a footnote.
    """
    return PromptTemplate.load(HINTS_DIR, prompt_id)
