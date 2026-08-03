"""What the user has, what they want, and what the data actually looks like.

Invariant 15: Mendel does not receive patient data. A `Goal` describes a *shape* —
type ids, states, and four measurements. "Paired, 150bp, reverse-stranded, twelve
samples" is true of thousands of studies and identifies nobody. There is no filename
field, no sample identifier field and no path, and `extra="forbid"` on both models is
what stops one being added by accident: an unrecognised key is a loud error rather
than a quietly carried payload.

Sample identity enters at run time, in the laboratory's own environment, through the
`params.input` placeholder the emitted pipeline declares. It never reaches Mendel's
process. See the clinical data-protection spec, §3.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DataProfile(BaseModel):
    """Measured properties of the input data. Pure computation, no inference."""

    model_config = ConfigDict(extra="forbid")

    read_length: int | None = None
    strandedness: str | None = None
    n_samples: int | None = None
    paired: bool | None = None


class GoalInput(BaseModel):
    type_id: str
    states: frozenset[str] = frozenset()


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    have: list[GoalInput] = Field(default_factory=list)
    want: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    profile: DataProfile = Field(default_factory=DataProfile)
