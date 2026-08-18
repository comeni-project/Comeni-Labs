"""A model fills a hole, or declines it. Nothing in between.

Every test injects a transport — no test in this repository may reach a live model, and
`tests/test_no_live_model.py` is what holds that.
"""

from comeni_core.review import ValueSource
from mendel_ai.access import ModelAccess
from mendel_ai.client import Client
from mendel_forge.filler import ModelFiller
from mendel_forge.observe import Excerpt, Observation
from mendel_forge.scaffold import Candidate, Hole

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
    subject="roles",
    what="what this tool is for",
    why_open="a judgement",
    candidates=[Candidate(value="qc_per_sample", note="declared role")],
    evidence=[Excerpt(locator="main.nf:3", text="process FASTQC {")],
)

TYPE_ID = Hole(
    subject="produces[0].type_id",
    what="what the port carries",
    why_open="not derivable",
    candidates=[Candidate(value="qc.report"), Candidate(value="alignment.bam")],
)

PROSE = Hole(subject="priority_because", what="why it ranks", why_open="a judgement")


def test_a_single_valued_hole_is_filled() -> None:
    filled = _filler('{"value": "qc.report", "why": "it emits a report"}').fill(
        TYPE_ID, OBSERVATION
    )
    assert filled is not None
    assert filled.value == "qc.report"
    assert filled.how is ValueSource.MODEL
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
        subject="produces[0].state",
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


def test_the_holes_evidence_reaches_the_prompt() -> None:
    transport = Fixed('{"values": ["qc_per_sample"], "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        ROLES, OBSERVATION
    )
    assert "main.nf:3" in transport.prompts[0]


def test_the_observations_prose_is_not_appended_on_top_of_it() -> None:
    """**The hole's evidence is already scoped.** `assemble` narrows a port's evidence to that
    port's own documentation; appending `observation.prose` again puts every other port back,
    which is how one `star/align` question came to carry ~13,000 characters and get answered
    with an essay about YAML instead of a choice."""
    transport = Fixed('{"values": ["qc_per_sample"], "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        ROLES, OBSERVATION
    )
    assert "Runs FastQC on sequencing reads" not in transport.prompts[0]


def test_why_open_reaches_the_prompt() -> None:
    """It did not, and it is where the scaffold explains the judgement being asked for —
    three of the misses measured on 2026-08-17 were a distinction this sentence draws."""
    transport = Fixed('{"values": ["qc_per_sample"], "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        ROLES, OBSERVATION
    )
    assert ROLES.why_open in transport.prompts[0]


def test_a_list_valued_hole_is_told_to_choose_the_smallest_true_set() -> None:
    """Two of three role misses were over-selection — a plausible extra value added on top of
    the right one."""
    transport = Fixed('{"values": ["qc_per_sample"], "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        ROLES, OBSERVATION
    )
    assert "smallest set" in transport.prompts[0]


def test_a_single_valued_hole_is_not_told_that() -> None:
    transport = Fixed('{"value": "qc.report", "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        TYPE_ID, OBSERVATION
    )
    assert "smallest set" not in transport.prompts[0]


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


class Proposes:
    """A transport whose model always declines and proposes instead."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.prompts.append(prompt)
        return (
            '{"value": null, "proposed_id": "star.log", '
            '"proposed_description": "a STAR run log", "why": "no declared type is a log"}'
        )


def test_a_type_hole_may_be_answered_with_a_proposal() -> None:
    """The measured failure: star/align emits nineteen channels and the vocabulary can type
    one. Forcing a pick there produces a wrong type, and a wrong type routes."""
    from mendel_forge.scaffold import Proposal

    filler = ModelFiller(Client(ACCESS, transport=Proposes()), model_id="test/model")
    answered = filler.fill(TYPE_ID, OBSERVATION)
    assert isinstance(answered, Proposal)
    assert answered.id == "star.log"
    assert answered.by == "test/model"


def test_the_prompt_offers_the_proposal_route() -> None:
    transport = Proposes()
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        TYPE_ID, OBSERVATION
    )
    assert "none of them fits" in transport.prompts[0]
    assert "a new declared type" in transport.prompts[0]


def test_a_name_hole_may_not_propose() -> None:
    """A port name is not a vocabulary, and since its candidates now come from the type_id
    there is always a reachable right answer."""
    hole = Hole(
        subject="consumes[0].name",
        what="what to call it",
        why_open="a choice",
        candidates=[Candidate(value="bam")],
    )
    transport = Proposes()
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        hole, OBSERVATION
    )
    assert "none of them fits" not in transport.prompts[0]


OPEN_NAME = Hole(
    subject="consumes[0].name",
    what="what to call it",
    why_open="a choice",
    candidates=[Candidate(value="zip", note="what other contracts call a qc.report port")],
    closed=False,
)


def test_an_open_hole_accepts_an_answer_that_was_not_offered() -> None:
    """**A port name is not a vocabulary.** `PortName` is a shape alias and ModuleContract
    accepts any valid identifier, so binding the answer to a list this codebase invented made
    multiqc's `reports` — a perfectly legal name — unreachable."""
    filled = _filler('{"value": "reports", "why": "it carries qc reports"}').fill(
        OPEN_NAME, OBSERVATION
    )
    assert filled is not None
    assert filled.value == "reports"


def test_an_open_hole_still_shows_what_the_registry_calls_it() -> None:
    transport = Fixed('{"value": "reports", "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        OPEN_NAME, OBSERVATION
    )
    assert "zip" in transport.prompts[0]
    assert "you may" in transport.prompts[0]


def test_a_closed_hole_still_refuses_what_was_not_offered() -> None:
    """Invariant 7 is unchanged: a type is a vocabulary and stays one."""
    assert _filler('{"value": "invented", "why": "w"}').fill(TYPE_ID, OBSERVATION) is None
