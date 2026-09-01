"""A graph somebody drew, before anything has been decided about it.

**Not `PipelineIR`.** An `IREdge` carries `type_id` and `states` because the resolver computed
them from the source port while searching; an `IRNode` carries a `selection` and a `presence`
saying at which tier it was chosen. A person dragging a wire has computed nothing and chosen
nothing at any tier, and a draft carrying those fields could *disagree* with the contract it
points at — which would make the validator's first job checking the input against itself.

Four names per edge, two per node. Everything else is derived by `mendel_resolver.validate`.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.goal.profile import DataProfile
from comeni_core.spell.marks import (
    ContractId,
    EdgeRef,
    HumanParamValue,
    Line,
    NfIdentifier,
    NodeId,
    PortName,
)

__all__ = ["DraftEdge", "DraftGraph", "DraftLabel", "DraftNode", "DraftParam"]


class DraftParam(BaseModel):
    """A setting somebody typed into the builder.

    **Not a `ParamBinding`.** That carries a `ResolvedValue` — a tier, a source, a reason, the
    premises a rule read — and a client must not be the thing that says at which tier its own
    answer sits. A browser claiming `tier: 1` on a value a person typed would put a lie in
    `pipeline.yml` that nothing downstream could catch, which is A130's shape exactly.

    So a draft carries the answer and the reason, and `materialise` stamps the tier: **4, human
    or model**, because a person who typed a value had a choice and made it (invariant 6).

    `HumanParamValue` rather than `ParamValue`: it is the type guarded against path-shaped
    values by a blocklist (audit A3), and a value typed into a browser is exactly the untrusted
    input that guard exists for.
    """

    model_config = ConfigDict(extra="forbid")

    name: NfIdentifier
    value: HumanParamValue = None
    why: Line = ""
    """Why this value. Empty is legal and is said in those words rather than replaced with the
    resolver's boilerplate — audits A77 and A111."""


class DraftLabel(BaseModel):
    """A name somebody typed onto an input or an output socket, for their own reading.

    **Draft-only, and that is the whole design.** Nothing in `materialise` reads it: it does not
    become a `params.<name>`, it does not reach `pipeline.yml`, and no resolver ever sees it. The
    operator's constraint was *"yes it's a label, does not change the actual keys"*, and
    `test_labels_reach_nothing` is what holds it — two drafts differing only in labels emit
    byte-identical Nextflow and identical artifacts.

    It exists because a pipeline can legitimately take several inputs of one type, and
    `fastq.reads` twice tells a person nothing about which is which. Naming them *tumour* and
    *normal* is a reading aid over a graph whose identity is unchanged.

    **`key` is `<node>.<port>` and deliberately not a `NodeId`.** A port is not a node: several
    ports on one step can each carry a label, and a label should survive its node being dragged
    (which changes no key) while not surviving its port being rewired (which changes what the
    label was about).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: EdgeRef
    """`<node>.<port>` — the same shape `DraftEdge` addresses a port with, and the same alias
    the IR uses for *which upstream output feeds this consumer's port*. Validated, so a label
    cannot carry a path or a newline into a draft that is stored and read back."""

    label: Line
    """What a person calls it. Free text, single line — and it is **not** a new egress author:
    a `DraftGraph` is not a door payload, `tests/test_egress.py` is untouched, and the count of
    free-text fields on the surface is still fourteen."""


class DraftEdge(BaseModel):
    """One wire: where it starts, where it ends. Nothing derived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: NodeId
    from_port: PortName
    to_node: NodeId
    to_port: PortName


class DraftNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    params: list[DraftParam] = Field(default_factory=list)


class DraftGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[DraftNode] = Field(default_factory=list)
    edges: list[DraftEdge] = Field(default_factory=list)
    labels: list[DraftLabel] = Field(default_factory=list)
    """What a person called each input and output socket. Read by the browser and by nothing
    else — see `DraftLabel`."""

    profile: DataProfile = Field(default_factory=DataProfile)
    """Carried because an advisory check may want to say *the rule that would have fired here
    read a measurement you have not supplied*. `validate` never resolves; it only reports."""
