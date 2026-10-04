"""The session's vocabulary: where a session is, what happens to it, what became of a proposal.

**No behaviour.** The protocol (`protocol`) draws its nodes and arrows with these names, the
machine (`state`) is derived from them, and the shell (`mendel_api.authoring.types`) re-exports
them for its own readers. They live here because the diagram is the program (14.7.8.1), and a
diagram that imported its words from the shell would point the arrow the wrong way.
"""

from enum import StrEnum


class Phase(StrEnum):
    """Where a session is in §2's diagram.

    Transcribed from that diagram rather than derived from what the code happens to need, so the
    picture stays the specification. `failed` is a phase and not a flag, because a session that
    failed to reach a provider must be able to retry *into a named place* — §2 draws two arrows
    out of it, back to `understanding` and to `resolving`.
    """

    UNDERSTANDING = "understanding"
    GATHERING = "gathering"
    """The engine asks for what the want still needs (14.7.3)."""
    GOAL_REVIEW = "goal_review"
    RESOLVING = "resolving"
    BUILDING = "building"
    COMPLETE = "complete"
    FAILED = "failed"
    STOPPED = "stopped"
    """An honest end: an input the analysis needs does not exist. Terminal, and not a failure."""


class Event(StrEnum):
    """What happens to a session.

    One member per labelled arrow in §2's diagram. Named for the *fact* rather than for the
    destination — `WANT_RETURNED`, not `TO_GATHERING` — because the same fact leads somewhere
    different depending on where it arrives: `GOAL_ACCEPTED` reaches `resolving` from
    `goal_review`, from `building` and from `complete`, and naming it for the target would make
    those read as three events.
    """

    GOAL_ACCEPTED = "goal_accepted"
    """The person accepted the goal — including a revised one, later in the session."""
    GOAL_REVISED = "goal_revised"
    """The person answered the goal summary in prose instead of accepting it."""
    BLUEPRINT_STORED = "blueprint_stored"
    """The resolver produced a whole blueprint and it was written down (§1.4)."""
    PROPOSAL_SETTLED = "proposal_settled"
    """A proposal was accepted or rejected. `building` loops on itself."""
    NOTHING_LEFT = "nothing_left"
    """The reveal reached the end of the blueprint with no proposal outstanding."""
    PROVIDER_FAILED = "provider_failed"
    """A model call failed or was refused, past retrying."""
    BUILD_FAILED = "build_failed"
    """The resolver could not produce a blueprint."""
    RETRY = "retry"
    """Leave `failed` for whichever phase failed."""
    WANT_RETURNED = "want_returned"
    """The model read what the person wants; the engine takes over to gather what it needs."""
    FACT_ADDED = "fact_added"
    """A gap was answered: a fact recorded, or deliberately left open."""
    NOTHING_MISSING = "nothing_missing"
    """Every gap is closed or open; the goal card can be shown."""
    INPUT_UNAVAILABLE = "input_unavailable"
    """The person does not have an input the analysis cannot do without."""
    WANT_UNREACHABLE = "want_unreachable"
    """Nothing can make the want a model chose (#202): the person is asked again, never failed."""


class ProposalState(StrEnum):
    """What became of a proposal.

    **`stale` is the member that earns the enum.** A proposal made against revision 4 and
    answered after revision 5 landed was not rejected — nobody rejected it — and it is not
    pending, because applying it would write over work the person did in between. Without a name
    for that, the service layer has to encode it as "pending but the revision does not match",
    which is a rule living in whichever caller remembered it.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"


class Command(StrEnum):
    """What a person (or, from 1b, a job) can do to a session: each is an arrow out of a
    waiting node (spec §3.2). Refused with MI0216 wherever no arrow names it."""

    DESCRIBE = "describe"
    ANSWER_GAP = "answer_gap"
    UPLOAD_SAMPLE = "upload_sample"
    CONFIRM_GOAL = "confirm_goal"
    REVISE_GOAL = "revise_goal"
    CHOOSE_PACING = "choose_pacing"
    CONTINUE = "continue"
    ANSWER_FACT = "answer_fact"
    CHOOSE = "choose"
    ASK = "ask"
    KEEP = "keep"
    RETRY = "retry"
    REPLY_IN_WORDS = "reply_in_words"
    """Typed words answering a question: a model reads them into a suggestion. Nothing moves."""
    SETTLE_STEP = "settle_step"
    """Accept or reject a step's proposal, as today. Part 3 replaces it with `continue`,
    `choose` and `answer_fact`."""
    # **A job's completion is a command** (spec §3.2): each names an arrow out of where the job's
    # session waits, and is refused, so ignored, once the session has moved on.
    UNDERSTOOD = "understood"
    ASKED_BACK = "asked_back"
    REVISED = "revised"
    PROVIDER_FAILED = "provider_failed"
