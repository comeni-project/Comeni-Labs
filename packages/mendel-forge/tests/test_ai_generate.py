"""The generation loop: ask, validate, repair at most twice, record everything.

No provider is reached. The client here is a `Client` over a scripted transport, which is the
same seam CI's recorded transport uses — the loop cannot tell them apart, and that is the point
of the seam existing.
"""

import json

import pytest
from comeni_ai import Client, ModelAccess
from mendel_forge.ai import generate
from mendel_forge.ai.context import Section, Segment, compose
from mendel_forge.ai.generate import Attempt, Outcome, one_dossier_per_run, run
from mendel_forge.ai.schemas import Proposal
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole


class Scripted:
    """A transport that returns prepared bodies in order and records what it was asked.

    Not a mock of `Client` — a `Client` over a scripted *transport*, so the JSON extraction,
    the schema validation and the refusal bookkeeping are all the real ones. A fake client
    would have made every assertion below a claim about the fake.
    """

    def __init__(self, *bodies: str) -> None:
        self.bodies = list(bodies)
        self.prompts: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.bodies.pop(0) if self.bodies else "{}"


def _client(*bodies: str) -> tuple[Client, Scripted]:
    transport = Scripted(*bodies)
    return Client(ModelAccess(model="test/model"), transport), transport


def _hole(hole_id: str = "consumes.reads.type_id", **overrides) -> ScaffoldHole:
    base = {
        "id": hole_id,
        "pointer": "/consumes/0/type_id",
        "kind": HoleKind.TYPE,
        "question": "the semantic type of the input",
        "why_open": "a filename pattern is not a type",
        "legal_values": ("fastq.reads", "alignment.bam"),
    }
    return ScaffoldHole(**{**base, **overrides})


def _dossier(*, evidence: tuple[str, ...] = ("E001",)):
    return compose(
        [
            Segment(section=Section.TASK, key="task", text="answer the holes"),
            *[
                Segment(section=Section.EVIDENCE, key=e, text=f"quoted {e}")
                for e in evidence
            ],
        ],
        budget=100_000,
    )


def _answer(value: str = "fastq.reads", evidence: tuple[str, ...] = ("E001",)) -> str:
    return json.dumps(
        {
            "analysis": {
                "answers": [
                    {
                        "hole_id": "consumes.reads.type_id",
                        "value": value,
                        "evidence_ids": list(evidence),
                        "reason": "the module's meta.yml says so",
                    }
                ],
                "unresolved": [],
            }
        }
    )


def _green(_: Proposal) -> tuple[str, ...]:
    return ()


def test_a_valid_first_answer_ends_the_run_with_one_attempt():
    """No repair is asked for when nothing was wrong. Sending a repair prompt on a green
    proposal would be a second chance to break something that already worked."""
    client, transport = _client(_answer())
    outcome = run(
        client=client, dossier=_dossier(), holes=[_hole()], validate=_green
    )
    assert outcome.succeeded()
    assert len(outcome.attempts) == 1
    assert len(transport.prompts) == 1


def test_a_failing_proposal_is_repaired_and_the_repair_can_succeed():
    """The loop's reason for existing. The second prompt is the repair template, not the
    analysis one asked again — asking the same question twice would get the same answer."""
    client, transport = _client(_answer("alignment.bam"), _answer("fastq.reads"))
    calls = iter([("MD0105: the port is wrong",), ()])
    outcome = run(
        client=client,
        dossier=_dossier(),
        holes=[_hole()],
        validate=lambda _: next(calls),
    )
    assert outcome.succeeded()
    assert [a.ordinal for a in outcome.attempts] == [0, 1]
    assert outcome.attempts[0].prompt_id == "forge.analysis.v1"
    assert outcome.attempts[1].prompt_id == "forge.repair.v1"


def test_the_repair_prompt_carries_the_prior_proposal_and_the_exact_diagnostics():
    """§5.7. A repair prompt that says *it did not validate* without saying what validation
    said asks the model to guess which of its answers was wrong."""
    client, transport = _client(_answer("alignment.bam"), _answer())
    calls = iter([("MD0105: produces[0].name is not an emit",), ()])
    run(client=client, dossier=_dossier(), holes=[_hole()], validate=lambda _: next(calls))
    repair = transport.prompts[1]
    assert "MD0105: produces[0].name is not an emit" in repair
    assert "alignment.bam" in repair


def test_the_repair_prompt_carries_the_same_dossier_text():
    """*Unchanged*, which is the word §5.7 uses. If the context also moved, a difference
    between two attempts is no longer attributable to the model's answer."""
    client, transport = _client(_answer("alignment.bam"), _answer())
    calls = iter([("something",), ()])
    dossier = _dossier()
    run(client=client, dossier=dossier, holes=[_hole()], validate=lambda _: next(calls))
    assert dossier.render() in transport.prompts[0]
    assert dossier.render() in transport.prompts[1]


def test_the_loop_stops_after_two_repairs():
    """§5.7: *stop after two repairs and send the inspectable failure to review*. Three
    attempts that each fix one diagnostic and break another are not converging."""
    client, transport = _client(_answer(), _answer(), _answer(), _answer(), _answer())
    outcome = run(
        client=client,
        dossier=_dossier(),
        holes=[_hole()],
        validate=lambda _: ("still wrong",),
    )
    assert not outcome.succeeded()
    assert len(transport.prompts) == 3
    assert [a.ordinal for a in outcome.attempts] == [0, 1, 2]


def test_a_failed_run_keeps_every_attempt_and_the_last_diagnostics():
    """*Inspectable* is the plan's word, and it means the reviewer gets the proposal, the
    diagnostics and the history — not a status."""
    client, _ = _client(_answer(), _answer(), _answer())
    outcome = run(
        client=client,
        dossier=_dossier(),
        holes=[_hole()],
        validate=lambda _: ("MD0105: still wrong",),
    )
    assert outcome.last_diagnostics() == ("MD0105: still wrong",)
    assert all(a.response_digest.startswith("sha256:") for a in outcome.attempts)


def test_every_attempt_records_both_directions_with_digests():
    """A stored prompt nobody can compare against a re-render is a stored prompt nobody can
    trust — the argument `pipeline.yml` already makes about its own values."""
    client, transport = _client(_answer())
    outcome = run(client=client, dossier=_dossier(), holes=[_hole()], validate=_green)
    (attempt,) = outcome.attempts
    assert attempt.prompt_digest == generate.digest_of(transport.prompts[0])
    assert attempt.response_digest != attempt.prompt_digest
    assert attempt.refusal is None


def test_a_refused_answer_is_recorded_and_the_loop_tries_again():
    """A model that returns nothing usable has not answered, and the record has to say that
    rather than showing a gap. `Client` codes the refusal; this only has to keep it."""
    client, _ = _client("not json at all", _answer())
    outcome = run(client=client, dossier=_dossier(), holes=[_hole()], validate=_green)
    assert outcome.succeeded()
    assert outcome.attempts[0].refusal is not None
    assert outcome.attempts[1].refusal is None


def test_a_response_citing_invented_evidence_raises_rather_than_repairing():
    """`admit()` refuses before validation, and the loop does not catch it.

    A response citing evidence that does not exist is not a weaker proposal to be repaired —
    it is a different document, and offering it a second chance would be treating a broken
    audit trail as a formatting problem.
    """
    client, _ = _client(_answer(evidence=("E404",)))
    with pytest.raises(ValueError, match="MF0401"):
        run(client=client, dossier=_dossier(), holes=[_hole()], validate=_green)


def test_a_proposal_that_leaves_a_required_hole_open_still_succeeds():
    """A model that declines with `needed_evidence` has given the answer §5.4 asks for. Failing
    the run would make the honest move look identical to the negligent one, and the next
    repair pass would push against it."""
    client, _ = _client(_answer())
    outcome = run(
        client=client,
        dossier=_dossier(),
        holes=[_hole(), _hole("produces.html.type_id")],
        validate=_green,
    )
    assert outcome.succeeded()
    assert outcome.unresolved_holes == ("produces.html.type_id",)


def test_one_dossier_per_run_refuses_a_mixed_history():
    """`MF0404`. The promise is easy to keep by accident and easy to break by a refactor that
    pushes dossier construction one call deeper, so it is a check with a code."""
    mixed = Outcome(
        attempts=(
            Attempt(
                ordinal=0,
                prompt_id="forge.analysis.v1",
                prompt_digest="a",
                response_digest="b",
                dossier_digest="one",
            ),
            Attempt(
                ordinal=1,
                prompt_id="forge.repair.v1",
                prompt_digest="c",
                response_digest="d",
                dossier_digest="two",
            ),
        )
    )
    with pytest.raises(ValueError, match="MF0404"):
        one_dossier_per_run(mixed)


def test_a_real_run_passes_its_own_dossier_check():
    """The check above is only worth having if the loop it guards actually satisfies it."""
    client, _ = _client(_answer("alignment.bam"), _answer())
    calls = iter([("wrong",), ()])
    outcome = run(
        client=client, dossier=_dossier(), holes=[_hole()], validate=lambda _: next(calls)
    )
    one_dossier_per_run(outcome)
