"""An answer, and the provenance of it.

**One vocabulary, where there were two.** The forge's `Filler` was `DERIVED / HAND / MODEL`
and this was `RESOLVER / GOAL / HUMAN / MODEL / MEASURED`. `HAND` and `HUMAN` were the same
fact under two names; `MODEL` was in both. They are one enum now, and `DERIVED` joins it.

**This module lives here rather than in `plan/` to break a cycle.** `plan/decision.py` imports
`Question` from `review/`, so `review/` importing `plan/` would be circular. `plan.tiers`
re-exports `ValueSource` so no call site moves. See the spec's §9.1.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ValueSource(StrEnum):
    """Who decided a value, recorded separately from how well it was decided.

    A tier says *how* something was settled; it should not also have to say *who*. A user
    who pins a parameter has legitimately removed the ambiguity, so the tier is still
    structural — but a reviewer needs to see that Mendel did not derive it. Same shape as
    measured-versus-asserted in the profiling spec, and for the same reason.

    **Not `PremiseOrigin`, which also has a `DERIVED`.** That enum answers *how good is this
    as evidence*; this one answers *who settled it*. Its own docstring draws the same line,
    and the two `DERIVED`s mean different things: there, a fact computed from other facts;
    here, a fact read straight off a source file.
    """

    RESOLVER = "resolver"
    GOAL = "goal"
    HUMAN = "human"
    """A person answered an ambiguity **after** resolution had faced it and flagged it.

    Deliberately not the same as `GOAL`, and the tier is what makes the difference visible.
    A goal pin is tier 1: the user removed the ambiguity before anything looked at it, so no
    choice existed to be made. An override is tier 4 that stayed tier 4 — resolution met a
    real ambiguity, could not settle it, and a human settled it in the artifact.

    Collapsing the two would erase that the pipeline contains a question somebody had to
    answer, and it would erase it precisely on the pipelines most worth reviewing. So the
    tier is kept and the *review* is what clears: see `PipelineIR.overrides()`.

    **The forge's `Filler.HAND` folded into this** in Plan 2.5. Same fact — a person typed
    it — under a second name, which is the clearest single win in that refactor.
    """
    MODEL = "model"
    """A model answered an ambiguity the deterministic ladder could not settle.

    Distinct from `HUMAN` for the reason `HUMAN` is distinct from `GOAL`: *who* settled a
    thing is what a reviewer needs, and the three answers oblige different amounts of trust.

    **Nothing writes this until Plan 2.** It is declared now rather than then so that a model
    adapter has somewhere truthful to write on the day it exists, instead of the enum arriving
    alongside the first thing that needs it — which is the moment a shortcut gets taken.

    **It is a claim, not a proof.** A resolver sets its own `source`, and an adapter that
    writes `resolver` here is indistinguishable from the deterministic ladder. Same standing as
    `confidence` and `reason`, and recorded as such in round three's inheritance notes. What
    *is* provable is the negative, and that lives on `Pipeline.ai` — see `AiProvenance`. A130.
    """
    MEASURED = "measured"
    """A tool produced this value by looking at the data, and named itself.

    The distinction that matters clinically: a measured 150bp read length is a fact a
    profiling run established, while an asserted one is a claim by whoever typed the goal
    file. Both are legitimate; only one is checkable. The `sealed` protection profile is
    meant to refuse a tier-3 decision resting on an assertion — issue #2, once Plan 2
    builds `ProfilePolicy`. Recording provenance here is what makes that check possible.
    """
    DERIVED = "derived"
    """A fact read directly off a source file — a process name in `main.nf`, an emit channel.

    Was the forge's `Filler.DERIVED`, and kept separate from both neighbours it resembles:
    `MEASURED` is a tool reporting on *data*, and `RESOLVER` is the ladder *choosing* between
    options. Reading a declaration is neither. A reviewer asking *why does this value say what
    it says* gets three different answers, and collapsing them would lose exactly the
    distinction `pipeline.yml` exists to carry.
    """


class Answer(BaseModel):
    """What was answered, by whom, by what means, and why.

    **Inert, like `Question`.** Whether an unanswered question blocks lives in the container
    and the port, never here — `HoleFiller.fill()` may return `None` and
    `AmbiguityResolver.resolve()` may not, and that is the whole of the difference.

    `Resolution` narrows `value` to `ParamValue`; `FilledValue` leaves it `Any`. That is the
    one place the base is intentionally looser than a subclass, and it is why
    `test_a_resolution_still_narrows_its_value` exists.
    """

    model_config = ConfigDict(extra="forbid")

    value: Any
    by: str
    """A username, a model id, or the name of the source a fact was read from."""
    how: ValueSource
    why: str
