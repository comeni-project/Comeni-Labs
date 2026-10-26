"""The vocabulary a recorded model call is written in: whose call, for what, and how it ended.

Every model call the builder (and the forge) makes is an `ai_invocation` row, and its check
constraint is built from these three enums, so a value here is a value the database accepts.
"""

from enum import StrEnum


class Agent(StrEnum):
    """Whose model call an `ai_invocation` row records. A purpose is scoped by its agent: the
    forge and the builder both declare a `chat`."""

    FORGE = "forge"
    BUILDER = "builder"


class InvocationPurpose(StrEnum):
    """The forge's purposes, one per committed prompt id; the builder's are its own `Purpose`.

    A purpose with no prompt file is a call nobody can audit, which is what `ai_invocation`
    exists to prevent.
    """

    ANALYSIS = "analysis"
    IMPLEMENTATION = "implementation"
    REPAIR = "repair"
    CHAT = "chat"


class InvocationState(StrEnum):
    """How a call ended. `REFUSED` is separate from `FAILED` on purpose: a provider that timed
    out is retried, while a model whose answer did not validate is a prompt or a model that
    cannot do the job, and folding both into `failed` would hide the second."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUSED = "refused"
