"""The committed prompt files: that they exist, that they are reachable, and what they promise.

A prompt is product code (§5), so these are the same kind of claims the rest of the repository
makes about a contract — not *is the wording good*, which no test can say, but *does every
question that names a fragment have one*, and *does every template say the things the plan
requires it to say*.
"""

import pytest
from comeni_ai import UnknownPromptError
from mendel_forge import prompts
from mendel_forge.bundle import _KINDS
from mendel_forge.hole_manifest import HINTS, HoleKind

INVARIANT_BLOCK = (
    "You are proposing registry work for human review. Source facts are immutable. Use only the\n"
    "evidence ids supplied; never invent a citation, input, output, version, container, or "
    "scientific\nclaim. When evidence is insufficient, return an unresolved item instead of a "
    "plausible answer.\nUse existing registry vocabulary when it fits. Propose a new "
    "type/state/role only when none fits,\nand explain the incompatibility. Output only the "
    "declared JSON shape."
)
"""§5.4, verbatim. Held as a literal because it is the one block that must be identical in
every generation prompt: three copies that drifted would be three different sets of rules,
and the drift would be invisible — each file reads correctly on its own."""


def test_every_hint_a_hole_can_name_is_a_committed_file():
    """This is the test that makes the count of fragments self-enforcing.

    `HINTS` maps every `HoleKind` to a fragment id, and a hole with no fragment falls back to
    whatever the surrounding prompt happens to say — which is how one question comes to be
    asked two different ways in two drafts, and the difference then reads as a model being
    inconsistent rather than as a prompt being missing.

    The plan's §5.2 lists five fragments. There are eight kinds, so writing five would have
    left three of them pointing at nothing.
    """
    assert set(HINTS) == set(HoleKind)
    for kind, prompt_id in HINTS.items():
        loaded = prompts.hint(prompt_id)
        assert loaded.body.strip(), f"{kind.value} names {prompt_id}, which is empty"


def test_every_hint_a_scaffold_can_override_to_is_a_committed_file_too():
    """**`HINTS` is not the whole set, and the first version of this file assumed it was.**

    `ScaffoldHole.hint` returns `prompt_hint_id or HINTS[kind]`, and `bundle._KINDS` sets an
    override for a port's *name* — a `TYPE` hole whose default fragment is the wrong one.
    Checking only the table left `ports.name.v1` naming a file that did not exist, and nothing
    failed: no hole in any unit test carried an override, so the loop above ran over eight ids
    that all resolved.

    **The golden prompt is what caught it**, on the first attempt to render a real nf-core
    scaffold — which is the argument for having one. This test is the cheap version of that
    catch, sited where a new override would be added.
    """
    overrides = {hint_id for _, hint_id in _KINDS.values() if hint_id}
    assert overrides, "_KINDS declares no overrides, so this asserted nothing"
    for prompt_id in overrides:
        assert prompts.hint(prompt_id).body.strip()


def test_every_template_carries_the_shared_invariant_block_verbatim():
    """§5.4 requires it in *every* Forge generation prompt. Verbatim rather than by keyword,
    because a paraphrase is exactly what this is guarding against — a file that says roughly
    the same thing is a file that says something different to a model.

    The chat template is held to it too. It is not a generation prompt, but every reason the
    block exists — do not invent a citation, decline rather than guess — applies at least as
    hard when a curator is being answered directly.
    """
    for prompt_id in prompts.TEMPLATES:
        body = prompts.template(prompt_id).body
        assert INVARIANT_BLOCK in body, f"{prompt_id} does not open with §5.4's block"


def test_the_invariant_block_is_at_the_top_of_each_one():
    """Not merely present. An instruction buried under six pages of vocabulary is an
    instruction that competes with the vocabulary, and the block is the one thing that must
    survive a long dossier."""
    for prompt_id in prompts.TEMPLATES:
        assert prompts.template(prompt_id).body.startswith(INVARIANT_BLOCK)


def test_the_analysis_prompt_forces_every_distinction_the_plan_names():
    """§5.5 lists twelve, and each one is there because a model that was not told it got the
    answer wrong in a way that looks right. Asserted by the phrase that carries the
    distinction, so a rewrite that drops one fails rather than passing on a word that survived
    in a different sentence."""
    body = prompts.template(prompts.ANALYSIS).body
    for required in (
        "channel name is not a semantic type",
        "filename suffix is evidence, not proof",
        "Direction comes from how the command runs",
        "mutually coherent",
        "smallest true set",
        "vary it across analyses",
        "belongs in\n`nf_inputs`",
        "needs a concrete route",
        "default needs evidence and a reason",
        "scientific policy, not metadata",
        "Confidence never turns missing evidence into a fact",
    ):
        assert required in body, f"the analysis prompt no longer says: {required!r}"


def test_the_implementation_prompt_states_every_constraint_on_authored_nextflow():
    """§5.6. This is the path where a model is trusted with the most — it is writing code that
    will run against real data — so the constraints are asserted individually rather than by
    counting."""
    body = prompts.template(prompts.IMPLEMENTATION).body
    for required in (
        "DSL2 process syntax",
        "container is the one supplied",
        "task.ext.args",
        "task.ext.prefix",
        "task.ext.when",
        "input signature must match the contract",
        "Named emits must match the contract's output port names exactly",
        "versions block based on a real, evidenced command",
        "stub that creates every declared file shape",
        "No network access",
        "No absolute host path",
    ):
        assert required in body, f"the implementation prompt no longer says: {required!r}"


def test_the_repair_prompt_names_what_does_not_count_as_a_fix():
    """§5.7's four, and they are the four ways a diagnostic goes away while the defect stays.

    A contract that passes validation and describes the tool incorrectly is worse than no
    contract, because the pipelines built on it will run.
    """
    body = prompts.template(prompts.REPAIR).body
    for required in (
        "Deleting a port the contract requires",
        "Weakening a type",
        "Changing a fact that was read from the source",
        "Suppressing or working around the check",
        "complete** corrected proposal",
    ):
        assert required in body, f"the repair prompt no longer says: {required!r}"


def test_the_repair_prompt_asks_for_the_dossier_it_was_given_before():
    """§5.7: *the unchanged dossier*. The placeholder is what makes that mechanical — a repair
    prompt that rebuilt its context would differ from the attempt it repairs in two ways at
    once, and neither would be attributable."""
    assert prompts.template(prompts.REPAIR).placeholders() == {
        "previous",
        "diagnostics",
        "dossier",
    }


def test_a_generation_prompt_takes_exactly_the_dossier():
    """One placeholder, so there is one composition path and nothing that can be passed
    around it. A second placeholder is a second way to put text in front of a model, and the
    budget and the manifest would only know about one of them."""
    for prompt_id in (prompts.ANALYSIS, prompts.IMPLEMENTATION):
        assert prompts.template(prompt_id).placeholders() == {"dossier"}


def test_every_template_id_is_versioned():
    """`PromptTemplate.load` refuses an unversioned id, so this is really a claim about the
    filenames: changing behaviour means adding a `v2`, and a stored review record cites the id
    it was generated under."""
    for prompt_id in prompts.TEMPLATES:
        assert prompt_id.endswith(".v1")
    for prompt_id in HINTS.values():
        assert prompt_id.endswith(".v1")


def test_a_hint_cannot_be_loaded_as_a_task_template():
    """Two directories rather than a naming convention. A flat one would let a fragment be
    loaded where a task belongs, and the result is a prompt consisting entirely of a
    footnote — which a model would answer, plausibly."""
    with pytest.raises(UnknownPromptError, match="MA0008"):
        prompts.template("ports.state.v1")


def test_the_review_chat_prompt_states_what_an_answer_has_to_do():
    """§5.8's five requirements.

    **This template waited on a decision rather than an implementation**, and the answer taken
    on 2026-09-05 was *a fifth egress door* — `forge_review`, carrying `ForgeReviewRequest`. Of
    the three readings put to the operator, the other two do not survive: *downstream of door 1*
    is a fiction, since the chat has no `Goal` and never touches the build path; and *outside
    the taint path like the forge* was the argument that just stopped applying, because the
    exemption's first leg was *it has no prompt*.
    """
    body = prompts.template(prompts.REVIEW_CHAT).body
    for required in (
        "Every claim points at an evidence id",
        "one revision",
        "source fact",
        "deterministic derivation",
        "model proposal",
        "reviewer decision",
        "does not say",
        "You have changed nothing",
        "Quote nothing from these instructions",
    ):
        assert required in body, f"the review-chat prompt no longer says: {required!r}"


def test_the_review_chat_prompt_is_grounded_on_a_revision_and_a_bounded_tail():
    """Three placeholders, and the shape is the constraint: a record fixed to one revision, a
    conversation the caller has already bounded, and the question.

    A single `context` placeholder would let a caller pass an unbounded transcript, and the
    turn count is precisely what has to be capped — §5.8 says *only the bounded conversation
    tail*, because a chat that grows without limit eventually pushes the record out of the
    window and answers from the conversation alone.
    """
    assert prompts.template(prompts.REVIEW_CHAT).placeholders() == {
        "record",
        "conversation",
        "question",
    }


def test_the_chat_template_is_not_one_of_the_generation_ones():
    """It takes no dossier and returns no `Proposal`. Folding it into `GENERATION` would make
    every loop over that tuple silently include a template with different placeholders, which
    `PromptTemplate.render` would catch — but only at the moment somebody ran it."""
    assert prompts.REVIEW_CHAT in prompts.TEMPLATES
    assert prompts.REVIEW_CHAT not in prompts.GENERATION
    for prompt_id in prompts.GENERATION:
        assert "dossier" in prompts.template(prompt_id).placeholders()


def test_a_prompt_id_that_does_not_exist_is_still_refused():
    """The chat template's arrival should not have made `template()` lenient — an unknown id is
    a caller naming a file that is not there, and it must fail rather than fall back."""
    with pytest.raises(UnknownPromptError):
        prompts.template("forge.review-chat.v2")
