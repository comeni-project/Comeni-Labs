"""The builder's two model calls: what they are told, what comes back, and what is recorded.

**This file is the whole of the builder's side of egress door 1.** Every call composes an
`AuthoringRequest`, renders it into a committed template, sends it, and admits the answer against
the vocabulary and the ids the engine itself issued. The stage modules (`mendel_api/stages/`)
hold rows and know nothing about providers; that split is what lets their tests run against a
database with no model, and this file's tests run against a fake transport with no database.

**Three things are checked on the way back in, and they are different checks.** The shape is
checked by `comeni-ai`, which will not hand over an answer that does not validate. The
*vocabulary* is checked here (`MI0204`): a type id that no layer declares is the most convincing
thing a model produces — it validates as a string and routes to nothing. The *ids* are checked
here too (`MI0205`), and that one is the product claim itself: a model answers by id and cannot
name a value outside the candidate set, which is only true because this compares the answer
against the set that was stored before the call was made.

**Nothing is repaired.** An answer that cannot be admitted is refused, recorded as refused, and
surfaced as a `notice` block carrying the code. A half-admitted goal — the two ids we recognised,
with the third dropped — would be a goal that is quietly *missing* what somebody asked for, and
they would find out when the pipeline came back without the step.

**It is the first writer of `ai_invocation`.** The table, its migration and its `agent` column
have existed since the forge's workflow landed, and until now nothing wrote a row: the forge's
chat path calls a provider and records nothing. `agent="builder"` is what that column was built
for, and the forge joining it is a separate piece of work rather than something to do from here.
"""

import hashlib
import re
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

from comeni_ai import Client, ModelAccess, ModelUnavailableError, Usage
from comeni_core.diagnostics import coded
from comeni_core.egress.authoring import AuthoringRequest, AuthoringRole, AuthoringTurn, KnownStep
from comeni_core.egress.characterisation import CharacteriseRequest
from mendel_forge.workflow import Agent, InvocationState

from mendel_api.authoring import prompts
from mendel_api.authoring.types import (
    CHAT_TAIL,
    AskedGap,
    AuthoringIntent,
    CharacteriseFamilies,
    CharacteriseReply,
    ChatReply,
    FamilyChoice,
    GapReply,
    GoalUnderstanding,
    Purpose,  # noqa: F401 (re-exported: it lived here; models.py needs it without a cycle)
    ReadBack,
    Understanding,
    WantUnderstanding,
)
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation
from mendel_api.services import registry, replies
from mendel_api.settings import model_access

AGENT = Agent.BUILDER
"""What goes in `ai_invocation.agent` for every row this file writes.

The column exists because the transport is shared and an audit table named `forge_*` would be a
lie the second time. This is the second time.
"""

_CODE = re.compile(r"\b(M[A-Z]\d{4})\b")
"""How a declared code is recovered from a coded message.

`comeni-ai` reports a refusal as `coded()` prose — the code *and* the sentence — and
`ai_invocation.failure_code` holds a code and never a provider's own words. Reading the code back
out of our own message is not parsing somebody else's error: the alternative is every call site
passing the code beside the message it already contains, which is two things to keep in step.
"""


class Outcome(NamedTuple):
    """What a call produced, whether or not it produced an answer.

    **The invocation id is present on every path that reached a provider**, including the ones
    that failed — a refused call is exactly the call somebody wants to look up afterwards, and an
    outcome that carried the id only on success would hide the rows worth reading.

    `refusal` is the whole coded sentence for a person; `code` is the bare code for `Notice.code`,
    which renders it as a diagnostic the interface can link. Both, because the block shows one and
    the transcript stores the other.
    """

    reply: (
        WantUnderstanding | GoalUnderstanding | AuthoringIntent | GapReply | AskedGap | ReadBack
        | CharacteriseFamilies | CharacteriseReply | None
    )
    invocation_id: str | None
    refusal: str | None
    code: str | None

    @property
    def admitted(self) -> bool:
        return self.reply is not None


# ── composing the door payload ────────────────────────────────────────────────────────────


def compose(
    *,
    prompt: str,
    turns: Sequence[tuple[str, str]] = (),
    goal=None,
    steps: Sequence[tuple[str, str]] = (),
    options: Sequence[str] = (),
    registry: str | None = None,
) -> AuthoringRequest:
    """Build the declared door-1 payload, with the conversation tail bounded.

    **The bound is applied here rather than by the caller**, because a caller that forgets it
    produces a call that works for the first ten turns and then quietly stops being grounded on
    anything but the conversation — which is the failure the Forge's `CHAT_TAIL` exists to
    prevent, and the reason §2 says to follow that precedent.

    Takes plain tuples rather than the declared types so that the one place which knows how to
    spell an `AuthoringTurn` is this function. A service assembling the payload itself is a
    second place where the tail can be forgotten.
    """
    return AuthoringRequest(
        prompt=prompt,
        turns=[
            AuthoringTurn(role=AuthoringRole(role), content=content)
            for role, content in list(turns)[-CHAT_TAIL:]
        ],
        goal=goal,
        steps=[KnownStep(node=node, contract=contract) for node, contract in steps],
        options=list(options),
        registry=registry,
    )


def _conversation_text(turns: Sequence[AuthoringTurn]) -> str:
    """The tail, labelled, oldest first — or a sentence saying there is none.

    An empty section would leave the heading above it dangling, and a model reading a heading
    with nothing under it is a model inferring that something was withheld.
    """
    if not turns:
        return "(this is the first thing they have said)"
    return "\n\n".join(f"{turn.role.value}: {turn.content}" for turn in turns)


def _vocabulary_text(stack, types: Sequence[str] | None = None) -> str:
    """Every declared type with its states, and every measurement. **Whole, never a selection.**

    `types`, when given, is **each chosen family whole** (#194) — never a hand-picked subset. The
    prompt says so, and a model shown one family is told it is seeing all of it.

    `mendel_forge.ai.select`'s argument, and it is the one worth restating: a model shown nine of
    eleven values does not know it was shown nine. Its answer then passes every check on the way
    back, because the thing it could not say is the thing nobody asked about.
    """
    lines = ["Types, each with the states declared for it:"]
    shown = stack.vocabulary.types if types is None else set(types)
    for type_id, states in sorted(stack.vocabulary.types.items()):
        if type_id not in shown:
            continue
        spelled = ", ".join(sorted(states)) if states else "(no states)"
        lines.append(f"  {type_id} — {spelled}")
    # **Each measurement with what it can hold and what it means** (#170): a bare `paired` gave a
    # model nothing to connect *paired-end* to, and `stated` came back empty.
    lines += ["", "Measurements, each with what it can hold (what a person may state):"]
    for measurement_id, m in sorted(stack.measurements.measurements.items()):
        holds = ", ".join(str(v) for v in m.values) if m.values else m.kind.value
        unit = f" {m.unit}" if m.unit else ""
        about = f" — {m.description}" if m.description else ""
        lines.append(f"  {measurement_id} ({holds}{unit}){about}")
    return "\n".join(lines)


def _pipeline_text(request: AuthoringRequest) -> str:
    """The steps that exist and the goal that was confirmed, as the model may refer to them.

    Ids first and contracts beside them, because an explanation is admitted by comparing the ids
    it cites against this list — so what the model is shown and what it is held to are one list.
    """
    lines = ["Steps in the draft, by the id you must use to refer to them:"]
    if request.steps:
        lines += [f"  {step.node} — {step.contract}" for step in request.steps]
    else:
        lines.append("  (none yet)")
    if request.goal is not None:
        have = ", ".join(entry.type_id for entry in request.goal.have) or "(nothing stated)"
        want = ", ".join(request.goal.want) or "(nothing stated)"
        lines += ["", f"The confirmed goal: they have {have}; they want {want}."]
    return "\n".join(lines)


def _options_text(options: Sequence[str]) -> str:
    """The option ids currently on the table.

    **Ids and not labels**, because this section is what `chose` is checked against and a model
    shown labels would answer with one. The labels live in the blocks the person is reading; the
    two lists are the same set seen from the two sides of the boundary.
    """
    if not options:
        return "(nothing is currently on offer — there is no option to choose)"
    return "\n".join(f"  {option}" for option in options)


# ── the two calls ─────────────────────────────────────────────────────────────────────────


def choose_families(
    request: AuthoringRequest,
    *,
    stack,
    memory: str = "",
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """Prose in, the families what the person wants belongs to and an acknowledgement out (#194).

    The first of the two type-choice calls. It is shown every family with its description.
    **`fits` first** (#202): anything but `yes` with a family listed makes the engine ask.
    """
    return _call(
        request,
        purpose=Purpose.FAMILY,
        prompt_id=prompts.FAMILY,
        shape=FamilyChoice,
        values={
            "families": _families_text(stack),
            "memory": memory or "(nothing is known yet)",
            "conversation": _conversation_text(request.turns),
            "request": request.prompt,
        },
        admit=lambda reply: _admit_families(reply, stack),
        client=client,
        session_id=session_id,
        choices={"families": sorted(stack.families.families)},
    )


def _families_text(stack) -> str:
    return "\n".join(
        f"  {family.id} — {family.description}"
        for family in sorted(stack.families.families.values(), key=lambda f: f.id)
    )


def _admit_families(reply: FamilyChoice | CharacteriseFamilies, stack):
    """Every family id declared, or `MI0204` — the vocabulary check, one level up."""
    unknown = sorted(set(reply.families) - set(stack.families.families))
    if unknown:
        raise ValueError(
            coded("MI0204", f"the answer names families nothing declares: {', '.join(unknown)}")
        )
    return reply


def understand(
    request: AuthoringRequest,
    *,
    stack,
    families: Sequence[str] | None = None,
    memory: str = "",
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """Prose in, what the person wants and what they said as changes out (`Understanding`,
    `goal.v8`, #307), or a visible coded refusal.

    **`families` given** (#194): `goal.v7`, shown every type of those families and held to them.
    **`None`**, the family step switched off: `goal.v6`, shown every type, acknowledging as it
    goes. The first call has no pipeline to talk about, which is why it is a different prompt
    and a different shape from `follow_up` rather than one call with half its fields empty.
    """
    shown = (
        sorted(stack.vocabulary.types)
        if families is None
        else stack.families.types_of(families, stack.vocabulary.types)
    )
    return _call(
        request,
        purpose=Purpose.GOAL,
        prompt_id=prompts.GOAL_ONE_STEP if families is None else prompts.GOAL,
        shape=Understanding,
        values={
            "vocabulary": _vocabulary_text(stack, None if families is None else shown),
            "memory": memory or "(nothing is known yet)",
            "conversation": _conversation_text(request.turns),
            "request": request.prompt
            + ("\n\n(Acknowledge them in `say`: nothing has yet.)" if families is None else ""),
        },
        admit=lambda reply: _admit_wanted(replies.admit(reply, stack), shown),
        client=client,
        session_id=session_id,
        choices={
            "wants.type": shown,
            "inputs.type": sorted(stack.vocabulary.types),
            "requires.type": shown,
            # A fact names a measurement, or a type the person said they hold.
            "facts.subject": _subjects(stack),
        },
    )


def _subjects(stack) -> list[str]:
    return sorted(set(stack.vocabulary.types) | set(stack.measurements.measurements))


def _admit_wanted(understanding, shown: Sequence[str]):
    """A want outside the families it was shown is refused (`MI0204`), as `_admit_shown` holds
    for the older shape."""
    outside = sorted({w.type for w in understanding.wants} - set(shown))
    if outside:
        raise ValueError(
            coded("MI0204", f"the want names types it was not shown: {', '.join(outside)}")
        )
    return understanding


def follow_up(
    request: AuthoringRequest,
    *,
    stack=None,
    memory: str = "",
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """A follow-up turn in, exactly one declared intent out, or a visible coded refusal.

    Takes no stack: an intent names ids the engine issued and never a type id, so the vocabulary
    is not what this call is held to. Asking for one anyway would be a parameter that exists to
    look symmetrical.
    """
    stack = stack if stack is not None else registry.stack()
    return _call(
        request,
        purpose=Purpose.CHAT,
        prompt_id=prompts.CHAT,
        shape=ChatReply,
        values={
            "memory": memory or "(nothing is known yet)",
            "pipeline": _pipeline_text(request),
            "options": _options_text(request.options),
            "conversation": _conversation_text(request.turns),
            "request": request.prompt,
        },
        admit=lambda reply: replies.admit(reply, stack),
        client=client,
        session_id=session_id,
        choices={
            "wants.type": sorted(stack.vocabulary.types),
            "inputs.type": sorted(stack.vocabulary.types),
            "requires.type": sorted(stack.vocabulary.types),
            "pins.type": sorted(stack.vocabulary.types),
            "pins.tool": sorted(c.id for c in stack.registry.all()),
            "facts.subject": _subjects(stack),
            "retract.subject": _subjects(stack),
        },
    )


def phrase_gap(
    request: AuthoringRequest,
    *,
    gap: dict,
    stack,
    memory: str = "",
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """One gathering question, phrased for this person (#167; `ask.v2`, words only, #307).

    `gap` carries `subject`, `kind`, `asks` (the engine's wording), `description` and `options`
    (id → label); `request.prompt` is the person's first sentence and `request.options` the
    gap's option ids, so admission compares `already_option` against what was written down
    before the call went out.
    """
    return _call(
        request,
        purpose=Purpose.ASK,
        prompt_id=prompts.ASK,
        shape=AskedGap,
        values={
            "gap": gap["asks"],
            "description": gap.get("description") or gap["subject"],
            "options": _options_text([f"{k} — {v}" for k, v in gap["options"].items()]),
            "first_sentence": request.prompt,
            "memory": memory or gap.get("facts") or "(nothing is known yet)",
        },
        admit=lambda reply: _admit_asked(reply, gap, stack),
        client=client,
        session_id=session_id,
    )


def read_back(
    request: AuthoringRequest,
    *,
    goal: str,
    memory: str = "",
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """What is known, read back in plain words for the card (#176; `readback.v2`, #307)."""
    return _call(
        request,
        purpose=Purpose.READBACK,
        prompt_id=prompts.READBACK,
        shape=ReadBack,
        values={"memory": memory or goal},
        admit=lambda reply: reply,
        client=client,
        session_id=session_id,
    )


# ── the characteriser (14.7.7) ─────────────────────────────────────────────────────────────


def compose_characterise(
    excerpt: str, *, binary_before: bool, registry: str | None
) -> CharacteriseRequest:
    """Door 6's payload. The excerpt is bounded by its own type (`marks.SampleText`)."""
    return CharacteriseRequest(excerpt=excerpt, binary_before=binary_before, registry=registry)


def _excerpt_values(request: CharacteriseRequest) -> dict[str, str]:
    return {
        "excerpt": request.excerpt,
        "binary_before": (
            "binary bytes came before this text"
            if request.binary_before
            else "no binary bytes before this text"
        ),
    }


def offered(stack, type_id: str) -> tuple[set[str], set[str]]:
    """The states a type declares, and the measurements whose `describes:` names it (spec §2:
    the registry decides which facts a model may read; a bench fact can never be offered)."""
    states = set(stack.vocabulary.types.get(type_id, ()))
    measurements = {
        m_id for m_id, m in stack.measurements.measurements.items() if m.describes == type_id
    }
    return states, measurements


def _types_text(stack, types: Sequence[str]) -> str:
    """Each type with its states, then the measurements describing it. **Each family whole.**"""
    lines = []
    for type_id in sorted(types):
        states, measured = offered(stack, type_id)
        lines.append(f"  {type_id} — states: {', '.join(sorted(states)) or '(none)'}")
        for m_id in sorted(measured):
            m = stack.measurements.get(m_id)
            holds = ", ".join(str(v) for v in m.values) if m.values else m.kind.value
            unit = f" {m.unit}" if m.unit else ""
            lines.append(f"      {m_id} ({holds}{unit}) — {m.description}")
    return "\n".join(lines)


def characterise_families(
    request: CharacteriseRequest,
    *,
    stack,
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """The start of a sample in, the families it could be out (14.7.7). An empty list is an
    answer: none fits, or the model cannot tell."""
    return _call(
        request,
        purpose=Purpose.CHARACTERISE_FAMILY,
        prompt_id=prompts.CHARACTERISE_FAMILY,
        shape=CharacteriseFamilies,
        values={"families": _families_text(stack), **_excerpt_values(request)},
        admit=lambda reply: _admit_families(reply, stack),
        client=client,
        session_id=session_id,
        choices={"families": sorted(stack.families.families)},
    )


def characterise(
    request: CharacteriseRequest,
    *,
    stack,
    families: Sequence[str] | None,
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """The start of a sample in, its type, states and facts out, admitted (14.7.7).

    `families` from the first call shows each family whole; `None`, with the family step off,
    shows every type. A value outside its declaration is dropped, as an inspector's would be;
    an id outside what was offered refuses the whole reply.
    """
    shown = sorted(
        stack.vocabulary.types
        if families is None
        else stack.families.types_of(families, stack.vocabulary.types)
    )
    measured = sorted({m for t in shown for m in offered(stack, t)[1]})
    return _call(
        request,
        purpose=Purpose.CHARACTERISE,
        prompt_id=prompts.CHARACTERISE,
        shape=CharacteriseReply,
        values={"types": _types_text(stack, shown), **_excerpt_values(request)},
        admit=lambda reply: _admit_characterised(reply, shown, stack, request.excerpt),
        client=client,
        session_id=session_id,
        # **Every id list held at the server** (issue 243): walked live, a model wrote free-text
        # states and states into `undetermined`. The union over the types shown; admission still
        # holds each to the chosen type's own. An empty list is left unconstrained by `_call`.
        choices={
            "type_id": list(shown),
            # On a state's `id`, never on the state itself (issue 245).
            "states.id": sorted({s for t in shown for s in offered(stack, t)[0]}),
            "undetermined": measured,
            "measurements.id": measured,
        },
    )


EVIDENCE_FLOOR = 8
"""The shortest quote that can prove anything (#244, raised in #246): `@HD` is in every BAM and
`@r1` in many FASTQs, so a quote must be long enough to tell one file from another."""


def _evidenced(quote: str, excerpt: str) -> bool:
    """Whether `quote` is within **one line** of the excerpt, runs of whitespace compared as one
    space (#244). One line, because squashing newlines let a quote join two (#246)."""

    def squash(text: str) -> str:
        return " ".join(text.split())

    found = squash(quote)
    return len(found) >= EVIDENCE_FLOOR and any(
        found in squash(line) for line in excerpt.splitlines()
    )


def _admit_characterised(
    reply: CharacteriseReply, shown: Sequence[str], stack, excerpt: str
) -> CharacteriseReply:
    """MI0204 for a type not shown; MI0205 for a state or measurement that type does not offer.
    A value outside its declaration is dropped, never refused (spec §7). **A property whose
    quoted line is not in the excerpt is dropped**, and the rest stands (spec §14, #244)."""
    if reply.type_id is None:
        return reply.model_copy(update={"states": [], "measurements": [], "undetermined": []})
    if reply.type_id not in shown:
        raise ValueError(
            coded("MI0204", f"the answer names a type it was not shown: {reply.type_id}")
        )
    states, measured = offered(stack, reply.type_id)
    read = [m.id for m in reply.measurements]
    # **Each list against its own set** (issue 237): a measurement id is not a state, and one
    # reply cannot read a measurement twice.
    foreign = sorted(({s.id for s in reply.states} - states) | (set(read) - measured))
    if foreign:
        raise ValueError(
            coded("MI0205", f"{reply.type_id} offers none of these there: {', '.join(foreign)}")
        )
    twice = sorted({m for m in read if read.count(m) > 1})
    if twice:
        raise ValueError(coded("MI0205", f"the answer reads {', '.join(twice)} more than once"))
    # What records nothing is dropped, never refused (#244): an `undetermined` id nothing
    # offered, or one that was read.
    undetermined = [m for m in reply.undetermined if m in measured and m not in read]
    proven = [s for s in reply.states if _evidenced(s.evidence, excerpt)]
    kept = []
    for m in reply.measurements:
        try:
            stack.measurements.check(m.id, m.value)
        except (ValueError, KeyError):
            continue
        if _evidenced(m.evidence, excerpt):
            kept.append(m)
    return reply.model_copy(
        update={"states": proven, "measurements": kept, "undetermined": undetermined}
    )


def _admit_asked(asked: AskedGap, gap: dict, stack) -> AskedGap:
    """`asks` is prose and kept; an `already` the gap did not offer, or a value its measurement
    refuses, is **dropped, not refused** — the phrasing is still worth having (#167)."""
    option, value = asked.already_option, asked.already_value
    if option is not None and option not in gap["options"]:
        option = None
    if value is not None:
        try:
            if "value" not in gap["options"]:
                raise ValueError("no value was offered")
            stack.measurements.check(gap["subject"], value)
        except (ValueError, KeyError, TypeError):
            value = None
    return asked.model_copy(update={"already_option": option, "already_value": value})


def _call(
    request: AuthoringRequest | CharacteriseRequest,
    *,
    purpose: Purpose,
    prompt_id: str,
    shape: type,
    values: dict[str, str],
    admit,
    client: Client | None,
    session_id: str | None = None,
    choices: dict[str, list] | None = None,
) -> Outcome:
    """Render, send, admit, record. The one path, so every row is written the same way.

    `choices` names the ids each field may hold, and **it is exactly what the prompt shows**
    (#194): enforced by the server where it can be, and checked by `admit` either way.

    **The schema is appended by `Client.generate` rather than written into the template.** The
    Forge composes its own prompt and calls `respond` because §5.3 fixes the order of ten
    sections down to which one comes last; here the rendered template *is* the instruction and
    what must come last is the shape, which is exactly what `generate` does with no evidence.
    A schema pasted into a committed `.md` would be a second copy of a Pydantic model, and it
    would go stale the first time a field moved.
    """
    if client is None:
        access = model_access("builder", purpose)
        if access is None:
            return Outcome(
                None,
                None,
                coded("MI0106", "no model is configured, so nothing can be generated")
                + "\n  set COMENI_AI_MODEL, and COMENI_AI_BASE_URL or COMENI_AI_API_KEY"
                + "\n  the builder needs one; the manual builder does not",
                "MI0106",
            )
        client = Client(access)

    template = prompts.template(prompt_id)
    rendered = template.render(values)
    # **Sent split** (#183): the fixed part as a system message a provider caches, the per-call
    # part after it. `rendered` stays for the row's prompt id.
    system, user = template.render_split(values)
    started = datetime.now(UTC)

    try:
        # An empty list is sent too (#244): `with_choices` turns it into *no items* on an array,
        # and leaves a scalar unconstrained, since an `enum` of nothing is a schema a server may
        # reject. Admission refuses any id that was not offered either way.
        held = dict(choices) if choices else None
        reply = client.chat(system, user, shape, choices=held)
    except (ModelUnavailableError, TimeoutError) as failure:
        # The provider is broken rather than the answer being wrong, and the two are separate
        # findings: this one is retried, a refusal is a prompt or a model that cannot do the job.
        # The exception's own text does not go in — it carries an endpoint and sometimes a key
        # prefix, and `failure_code` is a declared code for exactly that reason.
        return Outcome(
            None,
            _record(
                purpose=purpose,
                rendered=rendered,
                request=request,
                client=client,
                state=InvocationState.FAILED,
                failure_code=_code_in(str(failure)) or "MA0007",
                started=started,
                session_id=session_id,
            ),
            coded("MA0007", "the model could not be reached"),
            _code_in(str(failure)) or "MA0007",
        )

    if reply is None:
        refusal = client.last_refusal or coded("MA0004", "the model declined")
        return Outcome(
            None,
            _record(
                purpose=purpose,
                rendered=rendered,
                request=request,
                client=client,
                state=InvocationState.REFUSED,
                failure_code=_code_in(refusal) or "MA0004",
                started=started,
                session_id=session_id,
            ),
            refusal,
            _code_in(refusal) or "MA0004",
        )

    try:
        admitted = admit(reply)
    except ValueError as refused:
        # **Recorded as refused, not failed.** The call worked and the answer came back whole;
        # what it said was not ours to accept. Folding the two would hide the number §5.9 wants.
        return Outcome(
            None,
            _record(
                purpose=purpose,
                rendered=rendered,
                request=request,
                client=client,
                state=InvocationState.REFUSED,
                failure_code=_code_in(str(refused)) or "MI0205",
                started=started,
                session_id=session_id,
            ),
            str(refused),
            _code_in(str(refused)),
        )

    return Outcome(
        admitted,
        _record(
            purpose=purpose,
            rendered=rendered,
            request=request,
            client=client,
            state=InvocationState.SUCCEEDED,
            failure_code="",
            started=started,
            session_id=session_id,
        ),
        None,
        None,
    )


def _code_in(message: str) -> str | None:
    """The declared code a coded message opens with, or `None`."""
    found = _CODE.search(message)
    return found.group(1) if found else None


# ── admission ─────────────────────────────────────────────────────────────────────────────


def _admit_goal(understanding: GoalUnderstanding, stack) -> GoalUnderstanding:
    """A model's goal, held to the vocabulary. See `admit_goal`."""
    admit_goal(understanding.goal, stack)
    return understanding


def admit_goal(goal, stack) -> None:
    """Every id in the goal against what the registry declares. `MI0204`.

    **One check for a model's goal and a person's edit of it.** A goal typed into the card is held
    to exactly the vocabulary a model's is, because the resolver cannot tell who wrote a type id
    and should not have to.

    **The measurement half routes through `MeasurementRegistry.check`** rather than comparing
    keys here, because that is the declared validating path and it checks the *value* as well as
    the id — `tests/guards/test_construction.py` exists to stop a second one being written, and a
    hand-rolled `in` test beside it is that second one arriving by another name.
    """
    declared = stack.vocabulary.types
    unknown: list[str] = []

    def _type(type_id: str, states=()) -> None:
        if type_id not in declared:
            unknown.append(f"type {type_id}")
            return
        for state in sorted(states):
            if state not in declared[type_id]:
                unknown.append(f"state {state} on {type_id}")

    for entry in goal.have:
        _type(entry.type_id, entry.states)
    for wanted in goal.want:
        _type(wanted)
    for required in goal.constraints.required_states:
        _type(required.type_id, required.states)

    for measured in goal.profile.measurements:
        try:
            stack.measurements.check(measured.measurement, measured.value)
        except (ValueError, KeyError) as refused:
            unknown.append(f"measurement {measured.measurement} ({refused})")

    if unknown:
        raise ValueError(
            coded("MI0204", "the goal names something this registry does not declare")
            + "".join(f"\n  {item}" for item in unknown)
            + "\n  nothing was applied — say it in different words, or add it through the forge"
        )


# ── the audit row ─────────────────────────────────────────────────────────────────────────


def record_calls(
    calls, *, client: Client, registry: str, session_id: str | None = None
) -> list[str]:
    """One `ai_invocation` row per tier-4 call a blueprint made. Returns their ids.

    **Written after the build, not during it.** `ModelResolver` runs inside the resolver's own
    loop, which must stay free of I/O, so it keeps its calls in memory and this writes them once
    the pipeline exists. The timing columns are therefore the row's, not the call's: no duration
    is claimed for a call nobody timed, and `duration_ms` stays null rather than zero.

    A call whose answer was refused or declined is recorded as `refused` with its code — the
    rows worth reading afterwards are precisely the ones where a model kept naming something
    that was not on offer.
    """
    written: list[str] = []
    access: ModelAccess = client.access
    now = datetime.now(UTC)
    with session_scope() as session:
        for call in calls:
            invocation_id = secrets.token_hex(16)
            session.add(
                AiInvocation(
                    id=invocation_id,
                    agent=AGENT,
                    purpose=Purpose.TIER4.value,
                    model=call.model,
                    provider="local" if access.base_url else "",
                    prompt_id=call.prompt_id,
                    prompt_version=call.prompt_id.rsplit(".", 1)[-1],
                    prompt_digest=call.prompt_digest,
                    input_digests={"registry": registry, "subject": call.subject},
                    temperature=access.temperature,
                    state=(
                        InvocationState.SUCCEEDED if call.chosen else InvocationState.REFUSED
                    ).value,
                    failure_code="" if call.chosen else (_code_in(call.refusal or "") or "MA0004"),
                    started_at=now,
                    finished_at=now,
                    duration_ms=None,
                    input_tokens=None,
                    output_tokens=None,
                    response=call.response,
                    session_id=session_id,
                )
            )
            written.append(invocation_id)
    return written


def _record(
    *,
    purpose: Purpose,
    rendered,
    request: AuthoringRequest | CharacteriseRequest,
    client: Client,
    state: InvocationState,
    failure_code: str,
    started: datetime,
    session_id: str | None = None,
) -> str:
    """One `ai_invocation` row, written once, after the call.

    **Written once rather than moved through `queued → running → succeeded`.** The forge's states
    describe a row a queue owns for the length of a job; this call is made inside one, so a row
    that existed in `running` would only ever be read after it had stopped being true.

    `prompt_digest` is over **what crossed the wire** — `client.last_prompt`, which is the
    rendered template plus the schema `generate` appends — rather than over the template render
    alone. The field exists so a stored row can be compared against a re-render, and a digest of
    something slightly smaller than what was sent cannot do that.
    """
    finished = datetime.now(UTC)
    usage: Usage | None = client.last_usage
    access: ModelAccess = client.access
    invocation_id = secrets.token_hex(16)

    with session_scope() as session:
        session.add(
            AiInvocation(
                id=invocation_id,
                agent=AGENT,
                purpose=purpose.value,
                model=usage.model if usage else access.model,
                provider="local" if access.base_url else "",
                prompt_id=rendered.prompt_id,
                prompt_version=rendered.prompt_id.rsplit(".", 1)[-1],
                prompt_digest=hashlib.sha256((client.last_prompt or "").encode()).hexdigest(),
                input_digests={"registry": request.registry or ""},
                temperature=access.temperature,
                state=state.value,
                failure_code=failure_code,
                started_at=started,
                finished_at=finished,
                duration_ms=(
                    usage.duration_ms
                    if usage
                    else int((finished - started).total_seconds() * 1000)
                ),
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                cached_tokens=usage.cached_tokens if usage else None,
                response=client.last_response,
                session_id=session_id,
                reply_format=client.last_format,
            )
        )
    return invocation_id
