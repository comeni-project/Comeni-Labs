"""The chat may propose a tool's optional input switched (#460), held to what the tool allows.

What the person's own words say, quoted, is taken as theirs; the model's own reading is offered
as a suggestion and waits for a click — the rule every chat change follows.
"""

import pytest
from comeni_core.egress.authoring import AuthoringRequest, KnownStep
from comeni_core.goal.asked import Constraints, Goal, InputChoice, InputState
from mendel_api.authoring import prompts
from mendel_api.authoring.types import ChatReply
from mendel_api.services import authoring_ai, replies
from mendel_authoring.payloads import source_subject
from mendel_resolver import layers
from support.paths import ROOT

QUAST = "nf-core/quast@5.3.0"
STAR = "nf-core/star/align@2.7.11b"


@pytest.fixture
def stack(tmp_path):
    layer = tmp_path / "overlay"
    layer.mkdir()
    quast = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
    for name, body in {
        "assembly.family.yml": "declares: family\nid: assembly\ndescription: assemblies\n",
        "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\n",
        "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\n",
        "quast.contract.yml": "declares: contract\n" + quast,
    }.items():
        (layer / name).write_text(body)
    return layers.load([ROOT / "registry", layer])


def _reply(tool: str, port: str, quote: str | None = None) -> ChatReply:
    return ChatReply.model_validate({"optional_inputs": [
        {"tool": tool, "port": port, "state": "optional", "quote": quote}]})


def test_an_optional_input_item_becomes_the_optional_input_change(stack):
    sifted = replies.sift(_reply(QUAST, "fasta", "use my K-12 reference"), stack)
    assert sifted.set_aside == []
    [(change, quote)] = replies._changes(sifted.reply, stack, frozenset())
    assert (change.kind, change.subject, change.value) == (
        "optional_input", source_subject(QUAST, "fasta"), "optional")
    assert quote == "use my K-12 reference"


def test_a_required_input_is_set_aside(stack):
    sifted = replies.sift(_reply(STAR, "reads"), stack)
    assert sifted.reply.optional_inputs == []
    assert any("reads" in line for line in sifted.set_aside)


def test_the_model_is_shown_each_steps_optional_inputs_and_their_state(stack):
    request = AuthoringRequest(
        prompt="check my assemblies against K-12", steps=[KnownStep(node="quast", contract=QUAST)],
        goal=Goal(want=["qc.report"], constraints=Constraints(inputs=[
            InputChoice(contract=QUAST, port="gff", state=InputState.OPTIONAL)])))
    text = authoring_ai._pipeline_text(request, stack)
    assert "quast · fasta (genome.fasta): off; adds transcriptome, misassemblies, unaligned" in text
    assert "quast · gff (annotation.gff): optional" in text


def test_the_chat_prompt_teaches_optional_inputs():
    assert prompts.CHAT == "builder.chat.v8"
    prompt = ROOT / "packages/mendel-api/src/mendel_api/authoring/prompts/builder.chat.v8.md"
    text = prompt.read_text()
    assert "**`optional_inputs`**" in text
