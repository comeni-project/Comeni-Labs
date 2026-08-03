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

from comeni_core.marks import ParamValue, PortName, StateName, TypeId
from pydantic import BaseModel, ConfigDict, Field


class DataProfile(BaseModel):
    """Measured properties of the input data. Pure computation, no inference."""

    model_config = ConfigDict(extra="forbid")

    read_length: int | None = None
    strandedness: str | None = None
    n_samples: int | None = None
    paired: bool | None = None


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_id: TypeId
    states: frozenset[StateName] = frozenset()


class ParamOverride(BaseModel):
    """A parameter the user pinned. Closed, so it cannot carry a path.

    Previously these lived as arbitrary keys in an open `dict[str, Any]`, which meant
    `constraints: {seq_platform: /data/patients/PT-4471023/S1_R1.fastq.gz}` validated,
    reached `main.nf`, was labelled tier 1 with review `none`, and *suppressed* the
    tier-4 flag it replaced. Invariant 15 says no input accepts a path; it did.
    """

    model_config = ConfigDict(extra="forbid")

    name: PortName
    value: ParamValue


class Constraints(BaseModel):
    """Everything a goal may pin. `extra="forbid"` is the whole point of the type."""

    model_config = ConfigDict(extra="forbid")

    required_states: dict[TypeId, list[StateName]] = Field(default_factory=dict)
    params: list[ParamOverride] = Field(default_factory=list)


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    have: list[GoalInput] = Field(default_factory=list)
    want: list[TypeId] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    profile: DataProfile = Field(default_factory=DataProfile)
