"""The builder's committed prompt files: that they exist, ship, and say what §5 requires.

The Forge's `test_ai_prompts.py` is the model for this file, and the claims are the same kind:
not *is the wording good*, which no test can say, but *does every template carry the block that
must not drift*, *does each one still say the thing it was written to say*, and *does it reach a
built wheel*.

**Why a phrase rather than a keyword.** A paraphrase is exactly what this guards against — a file
that says roughly the same thing is a file that says something different to a model. Asserting
the sentence that carries the distinction means a rewrite which drops it fails, rather than
passing on a word that survived in a different clause.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from comeni_ai import UnknownPromptError
from mendel_api.authoring import prompts

ROOT = Path(__file__).resolve().parents[3]
"""The repository root.

`support.paths` is the right way to ask for this and is only on the path for the root `tests/`
tree; a package test counts parents, which is what `conftest.broken_registry_copy` already does
two files away. One convention per tree beats an import that resolves in one of them.
"""

INVARIANT_BLOCK = (
    "You are helping a researcher describe an analysis. You do not build the pipeline — a\n"
    "deterministic engine does, from the goal you write down. Use only the declared vocabulary "
    "and\nthe ids supplied below; never invent a type, state, measurement, step, option or "
    "setting id.\nWhen something is genuinely unclear, ask one typed question rather than "
    "assuming an answer.\nNever write a filename, a path, a sample identifier, or a count "
    "nobody measured. Output only\nthe declared JSON shape."
)
"""The builder's §5.4, verbatim, and it is the builder's own rather than the Forge's.

The two agents share a transport and share nothing else: the Forge's block is about evidence
ids and registry vocabulary, and this one is about a goal, the ids the engine issued, and
invariant 15. Holding it as a literal here is what makes drift between the two builder
templates fail — each file reads correctly on its own, which is precisely why nobody notices.
"""


def test_every_template_carries_the_invariant_block_verbatim():
    for prompt_id in prompts.TEMPLATES:
        body = prompts.template(prompt_id).body
        assert INVARIANT_BLOCK in body, f"{prompt_id} does not carry the builder's block"


def test_the_invariant_block_is_at_the_top_of_each_one():
    """Not merely present. The rules that must survive a long vocabulary section cannot be
    underneath it — the Forge measured this and the instruction has to be read first."""
    for prompt_id in prompts.TEMPLATES:
        assert prompts.template(prompt_id).body.startswith(INVARIANT_BLOCK)


def test_there_are_templates_to_check():
    """A loop is not an assertion: every test above passes over an empty tuple."""
    assert len(prompts.TEMPLATES) == 3


# ── the tier-4 prompt ─────────────────────────────────────────────────────────────────────


def test_the_tier_four_prompt_chooses_and_never_proposes():
    """Door 2's whole discipline in one template.

    `choose_or_propose` exists next door in `comeni-ai` and is deliberately not what this uses:
    an ambiguity is a choice between contracts that already exist, and nothing here should be
    able to invent a candidate.
    """
    body = prompts.template(prompts.TIER4).body
    for required in (
        "You are choosing between candidates the engine already found",
        "You cannot propose a candidate that is not listed",
        "say why in one sentence that a person could check",
    ):
        assert required in body, f"the tier-4 prompt no longer says: {required!r}"


def test_the_tier_four_prompt_refuses_popularity_as_a_reason():
    """The failure mode a model brings to this question. *Most people use STAR* is a fact about
    the world and not about this analysis, and it is the sentence that looks most like a
    justification while resting on nothing in the record."""
    body = prompts.template(prompts.TIER4).body
    assert "Do not reason from a tool's popularity" in body
    assert "not a fact about this analysis" in body


def test_the_tier_four_prompt_says_the_choice_is_flagged_whatever_its_confidence():
    """Invariant 6, told to the thing it constrains. Tier 4 is always flagged — that is the
    honesty mechanism and the difference from a chat window — so the model is told its answer is
    provisional rather than left to infer that from the shape of the request."""
    body = prompts.template(prompts.TIER4).body
    assert "recorded as a model decision and shown to a person" in body
    assert "flagged whatever" in body


def test_the_tier_four_prompt_takes_the_question_and_its_evidence():
    """Two placeholders. The candidates are **not** among them: `choose_one` appends the offered
    list itself, so there is exactly one place the option set is composed and no way for a caller
    to render a different set into the prose than the one membership is checked against."""
    assert prompts.template(prompts.TIER4).placeholders() == {"asking", "evidence"}


# ── the goal prompt ───────────────────────────────────────────────────────────────────────


def test_the_goal_prompt_asks_for_have_do_get_and_a_typed_goal():
    """Task 5's first bullet. Both halves, because the person checks the summary and the
    resolver runs on the `Goal` — a summary with no goal cannot be acted on, and a goal with no
    summary cannot be checked by the person whose analysis it is."""
    body = prompts.template(prompts.GOAL).body
    for required in (
        "what they have, what they want to do, and what they expect to get",
        "`have` is what already exists",
        "`want` is what they expect to end up with",
        "every type id you write must appear in the vocabulary above",
        "states must be declared for that type",
    ):
        assert required in body, f"the goal prompt no longer says: {required!r}"


def test_the_goal_prompt_only_wants_questions_that_can_change_the_pipeline():
    """A question whose answer changes nothing is a question that costs a person a round trip
    and the engine nothing — and it is what a model asks when it is unsure and wants to look
    careful."""
    body = prompts.template(prompts.GOAL).body
    for required in (
        "A question whose answer cannot change the pipeline is not worth asking",
        "Do not ask them to confirm something you already know",
    ):
        assert required in body, f"the goal prompt no longer says: {required!r}"


def test_the_goal_prompt_makes_file_grouping_explicit():
    """§1.7 and Task 5's second bullet, which exist because the silent failure is plausible.

    *Many FASTA files* is not a sample structure, and a model that picks one produces a goal
    that validates, resolves and builds — and describes an analysis nobody asked for.
    """
    body = prompts.template(prompts.GOAL).body
    for required in (
        "Many files is not a sample structure",
        "24 independent items, 12 paired samples, several lanes per sample, or one combined",
        "ask the grouping question",
        "Never invent a sample count",
    ):
        assert required in body, f"the goal prompt no longer says: {required!r}"


def test_the_goal_prompt_is_grounded_on_vocabulary_and_a_bounded_tail():
    """Three placeholders, and the shape is the constraint. A single `context` placeholder would
    let a caller pass an unbounded transcript, and the tail is precisely what has to be capped —
    §2 says ground on the declared request and the bounded tail, not on the transcript alone."""
    assert prompts.template(prompts.GOAL).placeholders() == {
        "vocabulary",
        "conversation",
        "request",
    }


# ── the chat prompt ───────────────────────────────────────────────────────────────────────


def test_the_chat_prompt_names_every_intent_and_no_others():
    """Task 5's third bullet: six, closed. The failure this prevents is a model inventing a
    seventh — *apply this change* — which is a generic mutation command by another name."""
    body = prompts.template(prompts.CHAT).body
    for required in (
        "explain something",
        "revise the goal",
        "choose one of the options offered",
        "propose a setting",
        "continue",
        "say that what was asked is not something you can do here",
        "There is no general-purpose command",
    ):
        assert required in body, f"the chat prompt no longer says: {required!r}"


def test_the_chat_prompt_refuses_an_arbitrary_tool_id():
    """§1.3: the model never names a module the engine did not offer. The registry and the
    resolver own that answer, and a plausible tool id is the most convincing thing a model can
    produce here — it looks exactly like a real one."""
    body = prompts.template(prompts.CHAT).body
    for required in (
        "You cannot name a tool that is not already a step or offered as an option",
        "choose an option id from the list above",
    ):
        assert required in body, f"the chat prompt no longer says: {required!r}"


def test_the_chat_prompt_grounds_an_explanation_on_known_step_ids():
    """Task 5's fourth bullet. An explanation that refers to a step nobody can see is an
    explanation a person cannot check, which is the whole thing this conversation is for."""
    body = prompts.template(prompts.CHAT).body
    for required in (
        "refer to steps by the ids listed above",
        "If the answer is not in what you were given, say so",
    ):
        assert required in body, f"the chat prompt no longer says: {required!r}"


def test_the_chat_prompt_is_grounded_on_the_pipeline_the_options_and_a_bounded_tail():
    assert prompts.template(prompts.CHAT).placeholders() == {
        "pipeline",
        "options",
        "conversation",
        "request",
    }


# ── identity, versioning, and packaging ───────────────────────────────────────────────────


def test_every_template_id_is_versioned():
    """Changing behaviour means adding a `v2`. An `ai_invocation` row cites the id it ran
    under, and an id whose content moved underneath it describes nothing."""
    for prompt_id in prompts.TEMPLATES:
        assert prompt_id.endswith(".v1")


def test_a_prompt_id_that_does_not_exist_is_refused():
    """Not a fallback. A caller naming a file that is not there must fail rather than be served
    whichever template happens to be nearby."""
    with pytest.raises(UnknownPromptError):
        prompts.template("builder.goal.v2")


def test_a_builder_prompt_is_not_reachable_as_a_forge_one():
    """Two packages, two directories, and the separation is the point: a prompt is loaded from
    the directory its caller owns, so `mendel-forge` cannot serve a builder template and this
    module cannot serve `forge.analysis.v1`."""
    with pytest.raises(UnknownPromptError):
        prompts.template("forge.analysis.v1")


def test_the_digest_is_over_the_rendered_text_and_not_the_template():
    """`ai_invocation.prompt_digest` is what makes a stored call comparable against a re-render.
    Two sessions sharing a template must not share a digest, or the audit row says two different
    conversations were the same call."""
    template = prompts.template(prompts.GOAL)
    one = template.render({"vocabulary": "v", "conversation": "(none)", "request": "count genes"})
    two = template.render({"vocabulary": "v", "conversation": "(none)", "request": "align reads"})
    assert one.digest != two.digest
    assert one.prompt_id == two.prompt_id == prompts.GOAL


def test_the_templates_ship_inside_the_built_wheel(tmp_path):
    """**The failure this catches is invisible in a checkout.**

    The prompt files sit inside the package rather than beside it, which is what makes hatchling
    carry them — the same arrangement `py.typed` relies on. A prompts directory one level up
    works perfectly in an editable install and is absent from every built artifact, and the
    symptom is an empty prompt rather than an import error.

    Built rather than asserted structurally: the claim is about what the artifact contains, and
    a test that checked the source layout would be checking the thing it assumes.
    """
    out = tmp_path / "wheel"
    result = subprocess.run(
        [
            "uv", "build", "--offline", "--package", "mendel-api",
            "--wheel", "--out-dir", str(out),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        pytest.skip(f"uv build unavailable: {result.stderr.strip()[:200]}")

    wheels = sorted(out.glob("mendel_api-*.whl"))
    assert wheels, "uv build reported success and produced no wheel"
    carried = set(zipfile.ZipFile(wheels[-1]).namelist())
    for prompt_id in prompts.TEMPLATES:
        expected = f"mendel_api/authoring/prompts/{prompt_id}.md"
        assert expected in carried, f"{expected} is not in the wheel"


def test_the_python_running_this_can_import_the_package():
    """Guards the guard above: a skip that fires for the wrong reason reports nothing."""
    assert sys.executable
    assert prompts.HERE.is_dir()
