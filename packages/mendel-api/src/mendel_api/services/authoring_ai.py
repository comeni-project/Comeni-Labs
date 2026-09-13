"""The builder's two model calls: what they are told, what comes back, and what is recorded.

**This file is the whole of the builder's side of egress door 1.** Every call composes an
`AuthoringRequest`, renders it into a committed template, sends it, and admits the answer against
the vocabulary and the ids the engine itself issued. `services/authoring.py` next door holds rows
and knows nothing about providers; that split is what lets its tests run against a database with
no model, and this file's tests run against a fake transport with no database.

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
from enum import StrEnum
from typing import NamedTuple

from comeni_ai import Client, ModelAccess, ModelUnavailableError, Usage
from comeni_core.artifact.egress import (
    AuthoringRequest,
    AuthoringRole,
    AuthoringTurn,
    KnownStep,
)
from comeni_core.diagnostics import coded
from mendel_forge.workflow import InvocationState

from mendel_api.authoring import prompts
from mendel_api.authoring.types import (
    CHAT_TAIL,
    AuthoringIntent,
    GoalUnderstanding,
)
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation
from mendel_api.settings import model_access

AGENT = "builder"
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


class Purpose(StrEnum):
    """Which of the builder's two calls this was — one member per committed prompt id.

    **Scoped by `agent`, not spelled to be globally unique.** The forge declares a `chat` purpose
    too, and `agent='builder' AND purpose='chat'` is what tells them apart, which is precisely
    what that column is for. Inventing `builder_chat` here would put the agent name in two
    columns and let them disagree.
    """

    GOAL = "goal"
    CHAT = "chat"
    TIER4 = "tier4"


class Outcome(NamedTuple):
    """What a call produced, whether or not it produced an answer.

    **The invocation id is present on every path that reached a provider**, including the ones
    that failed — a refused call is exactly the call somebody wants to look up afterwards, and an
    outcome that carried the id only on success would hide the rows worth reading.

    `refusal` is the whole coded sentence for a person; `code` is the bare code for `Notice.code`,
    which renders it as a diagnostic the interface can link. Both, because the block shows one and
    the transcript stores the other.
    """

    reply: GoalUnderstanding | AuthoringIntent | None
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


def _vocabulary_text(stack) -> str:
    """Every declared type with its states, and every measurement. **Whole, never a selection.**

    `mendel_forge.ai.select`'s argument, and it is the one worth restating: a model shown nine of
    eleven values does not know it was shown nine. Its answer then passes every check on the way
    back, because the thing it could not say is the thing nobody asked about.
    """
    lines = ["Types, each with the states declared for it:"]
    for type_id, states in sorted(stack.vocabulary.types.items()):
        spelled = ", ".join(sorted(states)) if states else "(no states)"
        lines.append(f"  {type_id} — {spelled}")
    lines += ["", "Measurements that may appear in the profile:"]
    for measurement_id in sorted(stack.measurements.measurements):
        lines.append(f"  {measurement_id}")
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


def understand(request: AuthoringRequest, *, stack, client: Client | None = None) -> Outcome:
    """Prose in, a typed `Goal` plus a summary out, or a visible coded refusal.

    The first call has no pipeline to talk about, which is why it is a different prompt and a
    different shape from `follow_up` rather than one call with half its fields empty.
    """
    return _call(
        request,
        purpose=Purpose.GOAL,
        prompt_id=prompts.GOAL,
        shape=GoalUnderstanding,
        values={
            "vocabulary": _vocabulary_text(stack),
            "conversation": _conversation_text(request.turns),
            "request": request.prompt,
        },
        admit=lambda reply: _admit_goal(reply, stack),
        client=client,
    )


def follow_up(request: AuthoringRequest, *, client: Client | None = None) -> Outcome:
    """A follow-up turn in, exactly one declared intent out, or a visible coded refusal.

    Takes no stack: an intent names ids the engine issued and never a type id, so the vocabulary
    is not what this call is held to. Asking for one anyway would be a parameter that exists to
    look symmetrical.
    """
    return _call(
        request,
        purpose=Purpose.CHAT,
        prompt_id=prompts.CHAT,
        shape=AuthoringIntent,
        values={
            "pipeline": _pipeline_text(request),
            "options": _options_text(request.options),
            "conversation": _conversation_text(request.turns),
            "request": request.prompt,
        },
        admit=lambda reply: _admit_intent(reply, request),
        client=client,
    )


def _call(
    request: AuthoringRequest,
    *,
    purpose: Purpose,
    prompt_id: str,
    shape: type,
    values: dict[str, str],
    admit,
    client: Client | None,
) -> Outcome:
    """Render, send, admit, record. The one path, so every row is written the same way.

    **The schema is appended by `Client.generate` rather than written into the template.** The
    Forge composes its own prompt and calls `respond` because §5.3 fixes the order of ten
    sections down to which one comes last; here the rendered template *is* the instruction and
    what must come last is the shape, which is exactly what `generate` does with no evidence.
    A schema pasted into a committed `.md` would be a second copy of a Pydantic model, and it
    would go stale the first time a field moved.
    """
    if client is None:
        access = model_access()
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

    rendered = prompts.template(prompt_id).render(values)
    started = datetime.now(UTC)

    try:
        reply = client.generate(rendered.text, shape, [])
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


def _admit_intent(intent: AuthoringIntent, request: AuthoringRequest) -> AuthoringIntent:
    """Every id in the reply against the ids the engine issued. `MI0205`.

    **This is the product claim made mechanical.** *A model cannot produce a value outside the
    candidate set* is a sentence about a comparison, and this is the comparison — against
    `request.options` and `request.steps`, both of which were written down before the call went
    out, so neither can have been widened by the answer.
    """
    offered = set(request.options)
    steps = {step.node for step in request.steps}
    invented: list[str] = []

    if intent.chose and intent.chose not in offered:
        invented.append(f"option {intent.chose}")
    for node in intent.refers_to:
        if node not in steps:
            invented.append(f"step {node}")
    if intent.setting is not None:
        if intent.setting.node not in steps:
            invented.append(f"step {intent.setting.node}")
        if intent.setting.chose and intent.setting.chose not in offered:
            invented.append(f"option {intent.setting.chose}")

    if invented:
        raise ValueError(
            coded("MI0205", "the reply names an option or a step that was never offered")
            + "".join(f"\n  {item}" for item in invented)
            + f"\n  offered: {', '.join(sorted(offered)) or '(none)'}"
            + f"\n  steps: {', '.join(sorted(steps)) or '(none)'}"
        )
    return intent


# ── the audit row ─────────────────────────────────────────────────────────────────────────


def record_calls(calls, *, client: Client, registry: str) -> list[str]:
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
                )
            )
            written.append(invocation_id)
    return written


def _record(
    *,
    purpose: Purpose,
    rendered,
    request: AuthoringRequest,
    client: Client,
    state: InvocationState,
    failure_code: str,
    started: datetime,
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
            )
        )
    return invocation_id
