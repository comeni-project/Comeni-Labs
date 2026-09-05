"""One attempt at one adaptation: compose, ask, validate, repair at most twice, record.

**Everything that crossed the wire is stored, both directions, with its digest.** §5 asks for
that and the reason is `pipeline.yml`'s: a review six months later has to be answerable from
the record alone. The digest is what makes it checkable rather than merely present — a stored
prompt nobody can compare against a re-render is a stored prompt nobody can trust.

**The dossier is built once and reused across repairs.** §5.7 says the repair prompt carries
the *unchanged* dossier, and the only way to be sure of that is to hand it the same object.
Rebuilding it would make the two attempts differ in two ways at once, and neither would be
attributable. `Attempt.dossier_digest` is asserted equal across every attempt in a run.

**No provider is reached from here.** A `Client` is handed in, and in CI it is a client over a
recorded transport — `comeni_ai.recorded` keys a recording on the whole prompt, so a prompt
edit invalidates every recording rather than silently replaying an answer to a question that
is no longer being asked. That is the correct behaviour and it is why §5.9 requires a
before/after evaluation report when a prompt changes.
"""

from collections.abc import Callable, Sequence

from comeni_ai import Client, Usage
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.ai.context import Dossier, digest_of
from mendel_forge.ai.schemas import Proposal, admit, owed
from mendel_forge.hole_manifest import ScaffoldHole
from mendel_forge.prompts import ANALYSIS, REPAIR, template

_FROZEN = ConfigDict(extra="forbid", frozen=True)

REPAIRS = 2
"""§5.7: *stop after two repairs and send the inspectable failure to review*.

A bound rather than a budget. Three attempts that each fix one diagnostic and break another
are not converging, and the fourth will not either — what a reviewer needs at that point is the
failure, the diagnostics and the proposal that produced them, which is exactly what
`Outcome.attempts` carries.
"""


class Attempt(BaseModel):
    """One request and its answer, as the audit row for it.

    Stored whether it succeeded or not. A discarded failed attempt is the half of the record
    that explains why the successful one says what it says — a value that appeared in attempt
    three and not in attempt one was repaired into existence, and a reviewer who cannot see
    that reads it as a first-pass reading of the source.
    """

    model_config = _FROZEN

    ordinal: int
    """0 is the first ask; 1 and 2 are repairs."""
    prompt_id: str
    prompt_digest: str
    response_digest: str
    dossier_digest: str
    """Asserted equal across every attempt in one outcome — §5.7's *unchanged dossier* as a
    check rather than a promise."""
    refusal: str | None = None
    """Coded, when the model declined or its answer would not validate. `None` on success."""
    diagnostics: tuple[str, ...] = ()
    """What validation said about the proposal this attempt produced, empty when it passed."""
    usage: Usage | None = None


class Outcome(BaseModel):
    """What one generation run produced, and everything it took to get there."""

    model_config = _FROZEN

    proposal: Proposal | None = None
    attempts: tuple[Attempt, ...] = ()
    unresolved_holes: tuple[str, ...] = ()
    """Required holes still not addressed when the run stopped.

    Not an error. A model that declines with `needed_evidence` has given the answer §5.4 asks
    for, and a proposal carrying them goes to review as *inspectable* rather than as *failed* —
    the whole point of the unresolved item existing.
    """

    def succeeded(self) -> bool:
        return self.proposal is not None

    def last_diagnostics(self) -> tuple[str, ...]:
        return self.attempts[-1].diagnostics if self.attempts else ()


Validate = Callable[[Proposal], tuple[str, ...]]
"""What validation looks like from here: a proposal in, diagnostics out, empty meaning green.

A callable rather than an import of `verify`, because the ladder needs a registry and a
workspace and this module needs neither — and because the evaluation corpus (§5.9) substitutes
a validator that compares against a known answer. Keeping the seam is what lets the same
orchestration be measured.
"""


def run(
    *,
    client: Client,
    dossier: Dossier,
    holes: Sequence[ScaffoldHole],
    validate: Validate,
    repairs: int = REPAIRS,
) -> Outcome:
    """Ask, validate, and repair up to `repairs` times.

    Returns rather than raises on every outcome a reviewer could act on — a refusal, a
    proposal that never validated, a proposal with holes left open. The one thing that raises
    is `admit()` finding a response that is not about the question that was asked, because
    there is nothing to review in that: a response citing invented evidence or answering
    invented holes is not a weaker proposal, it is a different document.
    """
    attempts: list[Attempt] = []
    legal_evidence = dossier.evidence_ids()
    dossier_text = dossier.render()
    dossier_digest = dossier.manifest.prompt_digest

    previous: Proposal | None = None
    diagnostics: tuple[str, ...] = ()

    for ordinal in range(repairs + 1):
        if ordinal == 0:
            rendered = template(ANALYSIS).render({"dossier": dossier_text})
        else:
            rendered = template(REPAIR).render(
                {
                    "previous": _dump(previous),
                    "diagnostics": "\n".join(diagnostics) or "(none recorded)",
                    "dossier": dossier_text,
                }
            )

        answer = client.respond(rendered.text, Proposal)
        attempt = Attempt(
            ordinal=ordinal,
            prompt_id=rendered.prompt_id,
            prompt_digest=digest_of(rendered.text),
            response_digest=digest_of(_dump(answer)),
            dossier_digest=dossier_digest,
            refusal=client.last_refusal,
            usage=client.last_usage,
        )

        if answer is None:
            attempts.append(attempt)
            continue

        admit(answer, holes=holes, evidence_ids=legal_evidence)
        diagnostics = tuple(validate(answer))
        attempts.append(attempt.model_copy(update={"diagnostics": diagnostics}))
        previous = answer

        if not diagnostics:
            return Outcome(
                proposal=answer,
                attempts=tuple(attempts),
                unresolved_holes=owed(answer, holes),
            )

    return Outcome(proposal=None, attempts=tuple(attempts))


def _dump(proposal: Proposal | None) -> str:
    """A proposal as the text that goes into a repair prompt and into a digest.

    Sorted and indented, so two runs over the same proposal digest the same — the argument
    every JSON writer in this repository makes, and the one that made `bundle._dumps` exist.
    """
    if proposal is None:
        return ""
    return proposal.model_dump_json(indent=2)


def one_dossier_per_run(outcome: Outcome) -> None:
    """§5.7's *unchanged dossier*, checked rather than trusted.

    Called by the tests and by anything that stores an outcome. It is a function rather than a
    validator on `Outcome` because the claim is about a *sequence* of attempts, and a model
    that reads well as `attempts: tuple[Attempt, ...]` should not also be the place that
    refuses one.
    """
    digests = {attempt.dossier_digest for attempt in outcome.attempts}
    if len(digests) > 1:
        raise ValueError(
            coded("MF0404", "a repair was given a different dossier than the attempt it repairs")
            + f"\n  digests seen: {sorted(digests)}"
        )
