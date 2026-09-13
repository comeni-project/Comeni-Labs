"""The builder's tier-4 adapter — egress door 2, and the one place a model picks a module.

**Spawn's resolver, and Build's is unchanged.** §1.2 is two policies over one engine: Build
resolves tier 4 with `FlagOnlyResolver` so the question stays visible and unanswered, Spawn
resolves it here. Nothing else differs, which is why this is a resolver rather than a second
builder — the `AmbiguityResolver` port already existed for exactly this, declared in Plan 1 and
unimplemented until now.

**It can only choose what it was offered.** `choose_one` checks membership and refuses a value
outside the set, and a refusal falls through to the flag-only path — so a model that answers
badly leaves the pipeline exactly as Build mode would have left it, rather than leaving it
wrong. That is the difference between *never fabricate* and *never fail*.

**Nothing here writes to a database.** `resolve()` is called from inside the resolver's own
loop, which must stay replayable and free of I/O; every call is appended to `calls` instead, and
whoever drove the build writes the audit rows afterwards. A resolver that opened a transaction
per decision would put storage in the one path `same goal in → same pipeline out` rests on.

**No confidence is reported, and that is deliberate rather than an omission.** `choose_one`
returns a value and a sentence; a model's self-rated certainty is not a measurement, and putting
a number in `Resolution.confidence` would put an unmeasured figure beside values whose tiers are
derived from declared data. It stays `0.0` — the value meaning *nothing measured this* — and
what distinguishes a model's answer from the flag-only path is `how` and `by`, which are facts.
Invariant 6 makes the point moot downstream anyway: tier 4 is flagged at any confidence.
"""

import hashlib
import re
from typing import NamedTuple

from comeni_ai import Client, Option, choose_one
from comeni_core.artifact.egress import AmbiguityRequest
from comeni_core.plan.decision import Ambiguity, Resolution
from comeni_core.plan.tiers import ValueSource
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver, NoCandidatesError

from mendel_api.authoring import prompts

_WHITESPACE = re.compile(r"\s+")


def request_for(ambiguity: Ambiguity) -> AmbiguityRequest:
    """Project a tier-4 question onto door 2's declared payload.

    **`model_dump()` minus `kind`, which is exactly how the guard builds one.**
    `test_every_tier_four_question_can_actually_cross_the_door` constructs all three `*Asked`
    kinds this way and asserts each one fits, so writing the projection any other way would mean
    the shape a guard proves and the shape production sends are two different shapes.

    Door 2 has been declared since Plan 1 and nothing has ever crossed it — this is its first
    producer, which is why that guard was the only construction site in the repository.
    """
    payload = ambiguity.model_dump()
    payload.pop("kind", None)
    return AmbiguityRequest(**payload)


class Call(NamedTuple):
    """One model call, kept in memory for whoever drove the build to record.

    Not written here, for the module docstring's reason. Carries what an `ai_invocation` row
    needs and nothing a row would not: no prompt text, because the digest is what a stored row
    is compared against, and no provider object.
    """

    subject: str
    chosen: str | None
    """`None` when the model declined or answered outside the offered set."""
    model: str
    prompt_id: str
    prompt_digest: str
    refusal: str | None
    """The coded refusal, when there was one. `None` on success."""


class ModelResolver:
    """Answers a tier-4 question with one of its own candidates, or defers to the flag.

    Satisfies `mendel_resolver.ports.AmbiguityResolver` structurally; the protocol is not
    imported as a base because it is a `Protocol` and inheriting would add nothing a type
    checker does not already do.
    """

    def __init__(
        self,
        client: Client,
        *,
        model: str = "",
        fallback: AmbiguityResolver | None = None,
    ) -> None:
        self._client = client
        self._model = model or client.access.model
        self._fallback = fallback or FlagOnlyResolver()
        self.calls: list[Call] = []
        """Every call made, in order, for the caller to turn into audit rows."""

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        if not ambiguity.candidates:
            # **The same refusal `FlagOnlyResolver` makes**, rather than a gentler one. Nothing
            # in the resolver catches this today, so softening it here would change when a build
            # fails depending on which mode it ran in — and a question with no candidates is not
            # a question a model could help with anyway.
            raise NoCandidatesError(f"no candidates for {ambiguity.key()}")

        request = request_for(ambiguity)
        options = [
            Option(value=str(candidate))
            for candidate in request.candidates
            if candidate is not None
        ]
        if not options:
            # A parameter question whose only candidate is `null` — legal, and `str(None)` would
            # offer the model the literal string "None" to choose. Left to the flag.
            return self._fallback.resolve(ambiguity)

        rendered = prompts.template(prompts.TIER4).render(
            {"asking": _asking(request), "evidence": _evidence(request)}
        )
        answer = choose_one(self._client, rendered.text, options, [])
        # Over what crossed the wire — the framing plus the options and schema `choose_one`
        # appended — for `authoring_ai._record`'s reason: a stored row is compared against a
        # re-render, and a digest of less than was sent cannot be.
        sent = self._client.last_prompt or rendered.text

        self.calls.append(
            Call(
                subject=request.subject,
                chosen=answer.value if answer else None,
                model=self._model,
                prompt_id=rendered.prompt_id,
                prompt_digest=hashlib.sha256(sent.encode()).hexdigest(),
                refusal=None if answer else self._client.last_refusal,
            )
        )
        if answer is None:
            # Declined, or answered outside the set. **The question stays exactly as open as
            # Build mode leaves it** — flagged, tier 4, first candidate, reason saying nobody
            # judged it. Falling through rather than raising is what keeps a provider outage
            # from turning a Spawn into a failed build.
            return self._fallback.resolve(ambiguity)

        return Resolution(
            value=answer.value,
            why=_one_line(answer.why),
            confidence=0.0,
            by=self._model,
            how=ValueSource.MODEL,
        )


def _asking(request: AmbiguityRequest) -> str:
    """What is being decided, from the door payload and nothing else.

    Composed from the payload rather than from the `Ambiguity` so that what a guard inspects and
    what a model reads are the same object — `forge_jobs._record_text`'s rule, one door over.
    """
    lines = [f"The question is about `{request.subject}`, at step `{request.node_id}`."]
    if request.what:
        lines.append(request.what)
    if request.why_open:
        lines.append(f"It could not be settled because: {request.why_open}")
    wanted = getattr(request, "type_id", "") or ""
    if wanted:
        lines.append(f"It must produce `{wanted}`.")
    if request.states:
        lines.append(f"It must carry these states: {', '.join(request.states)}.")
    if not request.closed:
        lines.append(
            "The candidates below are the likely ones rather than the whole of what is legal."
        )
    return "\n".join(lines)


def _evidence(request: AmbiguityRequest) -> str:
    """What the answer rests on, quoted with its locator.

    **An empty section says so in words.** A heading with nothing under it is a model inferring
    that something was withheld, and the forge measured what happens when a question arrives
    without readable evidence: 69% against 88%.
    """
    if not request.evidence:
        return "(the record carries no evidence for this one — say so if it decides the answer)"
    return "\n\n".join(f"{item.locator}\n  {item.text}" for item in request.evidence)


def _one_line(reason: str) -> str:
    """`Resolution.why` is a `Line`, and a model writes paragraphs.

    Collapsed rather than truncated: the sentence reaches `pipeline.yml` as the reason a value is
    what it is, and cutting it at a newline would keep the half that says *what* and drop the
    half that says *why*.
    """
    return _WHITESPACE.sub(" ", reason).strip()
