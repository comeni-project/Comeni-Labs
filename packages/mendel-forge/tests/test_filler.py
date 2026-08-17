"""A model fills a hole, or declines it. Nothing in between.

Every test injects a transport — no test in this repository may reach a live model, and
`tests/test_no_live_model.py` is what holds that.
"""

from mendel_ai.access import ModelAccess
from mendel_ai.client import Client
from mendel_forge.filler import ModelFiller
from mendel_forge.observe import Excerpt, Observation
from mendel_forge.scaffold import Candidate, Filler, Hole

ACCESS = ModelAccess(model="test/model")

OBSERVATION = Observation(
    source="nf-core",
    ref_id="nf-core:fastqc",
    facts={},
    prose=[Excerpt(locator="meta.yml:description", text="Runs FastQC on sequencing reads")],
)


class Fixed:
    def __init__(self, body: str) -> None:
        self.body = body
        self.prompts: list[str] = []

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.body


def _filler(body: str) -> ModelFiller:
    return ModelFiller(Client(ACCESS, transport=Fixed(body)), model_id="test/model")


ROLES = Hole(
    field="roles",
    what="what this tool is for",
    why_open="a judgement",
    candidates=[Candidate(value="qc_per_sample", note="declared role")],
    evidence=[Excerpt(locator="main.nf:3", text="process FASTQC {")],
)

TYPE_ID = Hole(
    field="produces[0].type_id",
    what="what the port carries",
    why_open="not derivable",
    candidates=[Candidate(value="qc.report"), Candidate(value="alignment.bam")],
)

PROSE = Hole(field="priority_because", what="why it ranks", why_open="a judgement")


def test_a_single_valued_hole_is_filled() -> None:
    filled = _filler('{"value": "qc.report", "why": "it emits a report"}').fill(
        TYPE_ID, OBSERVATION
    )
    assert filled is not None
    assert filled.value == "qc.report"
    assert filled.filler is Filler.MODEL
    assert filled.by == "test/model"
    assert filled.why == "it emits a report"


def test_a_list_valued_hole_gets_a_list() -> None:
    """`roles` takes several members from one closed set — the reason `choose_many` exists."""
    filled = _filler('{"values": ["qc_per_sample"], "why": "it QCs a sample"}').fill(
        ROLES, OBSERVATION
    )
    assert filled is not None
    assert filled.value == ["qc_per_sample"]


def test_a_state_field_is_treated_as_list_valued() -> None:
    """`produces[].state` is the other list-valued shape, and it is suffix-matched rather than
    named — a fixture for it is what stops the suffix rule from being untested."""
    hole = Hole(
        field="produces[0].state",
        what="what states the port carries",
        why_open="not derivable",
        candidates=[Candidate(value="coordinate_sorted")],
    )
    filled = _filler('{"values": ["coordinate_sorted"], "why": "the tool sorts"}').fill(
        hole, OBSERVATION
    )
    assert filled is not None
    assert filled.value == ["coordinate_sorted"]


def test_a_hole_with_no_candidates_is_declined_without_asking() -> None:
    """#70 gates prose. Asking anyway is the one thing this design says it does not do."""
    transport = Fixed('{"value": "x", "why": "w"}')
    filler = ModelFiller(Client(ACCESS, transport=transport), model_id="test/model")
    assert filler.fill(PROSE, OBSERVATION) is None
    assert transport.prompts == [], "a prose hole was sent to a model"


def test_a_value_outside_the_candidates_is_declined() -> None:
    assert _filler('{"value": "invented", "why": "w"}').fill(TYPE_ID, OBSERVATION) is None


def test_a_declined_model_leaves_the_hole_open() -> None:
    assert _filler("not json").fill(TYPE_ID, OBSERVATION) is None


def test_the_evidence_and_prose_reach_the_prompt() -> None:
    transport = Fixed('{"values": ["qc_per_sample"], "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        ROLES, OBSERVATION
    )
    prompt = transport.prompts[0]
    assert "main.nf:3" in prompt
    assert "Runs FastQC on sequencing reads" in prompt


def test_the_field_name_reaches_the_prompt() -> None:
    """`what` alone does not say which field is being answered."""
    transport = Fixed('{"value": "qc.report", "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        TYPE_ID, OBSERVATION
    )
    assert "produces[0].type_id" in transport.prompts[0]


def test_the_answer_is_legal_for_the_hole() -> None:
    """The second validation. `hole.legal` is the check a person's fill already goes through."""
    filled = _filler('{"values": ["qc_per_sample"], "why": "w"}').fill(ROLES, OBSERVATION)
    assert filled is not None
    assert ROLES.legal(filled.value)


def test_it_has_the_shape_the_port_declares() -> None:
    """`HoleFiller` is a plain Protocol, so this checks the signature by calling it rather
    than by isinstance — which would only see the method name anyway."""
    from mendel_forge.ports import HoleFiller

    filler: HoleFiller = _filler('{"value": "qc.report", "why": "w"}')
    assert filler.fill(TYPE_ID, OBSERVATION) is not None
