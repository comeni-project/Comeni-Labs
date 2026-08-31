"""A graph somebody drew, before anything has been decided about it.

**Not `PipelineIR`.** An `IREdge` carries `type_id` and `states` because the resolver computed
them from the source port while searching; an `IRNode` carries a `selection` and a `presence`
saying at which tier it was chosen. A person dragging a wire has computed nothing and chosen
nothing at any tier, and a draft carrying those fields could *disagree* with the contract it
points at — which would make the validator's first job checking the input against itself.

Four names per edge, two per node, and one label per socket. Everything else is derived by
`mendel_resolver.validate` — and the label is derived by nothing, which is `DraftLabel`'s
whole subject.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.goal.profile import DataProfile
from comeni_core.spell.marks import (
    ContractId,
    HumanParamValue,
    Line,
    NfIdentifier,
    NodeId,
    PortName,
    SocketKey,
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


class DraftEdge(BaseModel):
    """One wire: where it starts, where it ends. Nothing derived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: NodeId
    from_port: PortName
    to_node: NodeId
    to_port: PortName


class DraftLabel(BaseModel):
    """What a person calls one socket. **On the draft, and nowhere else.**

    ═══ WHAT IS DERIVED AND WHAT IS TYPED ════════════════════════════════════════════════════

    The operator's constraint on 2026-08-31 was one sentence — *"yes it's a label, does not
    change the actual keys"* — and the table it implies is the whole safety argument:

    | | derived | typed by a person |
    |---|---|---|
    | the channel name (`gtf_2`) | ✓ | |
    | the param (`params.gtf_2`) | ✓ | |
    | the samplesheet column | ✓ | |
    | the Nextflow variable | ✓ | |
    | what the canvas shows | | ✓ |

    So `materialise` does not read this field, nothing derived from it reaches `pipeline.yml`,
    and no resolver sees it. A guard holds that rather than this docstring:
    `test_a_label_reaches_nothing` builds two drafts differing only in their labels and asserts
    the emitted `.nf` and the artifact are identical.

    ═══ WHY A LABEL IS WORTH THIS MUCH CARE ══════════════════════════════════════════════════

    **Invariant 15.** A field a person types into, which names an input, is one rename away
    from `/data/patients/PT-4471023/`. Keeping it off the key and out of the artifact means the
    worst case is a private note in a Postgres row rather than a patient identifier in a
    published pipeline.

    It also adds nothing to invariant 14's list of free-text fields: a `DraftGraph` is not a
    door payload and `tests/test_egress.py` is untouched by this change, which is the assertion
    rather than an aside. If a later change wants a label in `pipeline.yml`, that is a
    fifteenth entry on that list and it gets the argument the tenth one got, in writing, first.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: SocketKey
    """Which socket. **Two shapes, because the two sides of a pipeline have different
    identities**, and this is what Plan 5B phase 2.5 changed:

    - an **input** is a `ChannelName` — `gtf`, `reads`. A channel may feed three ports, so
      keying its label on a port would give one socket three competing labels and no rule for
      which wins. `BuiltPipeline.channels` is the server's list and the canvas draws one socket
      per entry on it.
    - an **output** is `<node>.<port>` — `counts.counts`. `Goal.want` is a list of type ids and
      gives an output no identity of its own, so the port is the only thing there is to name.
      When phase 4 gives outputs one, this becomes symmetric.

    **Not a `NodeId` in either case**, which is the property worth keeping: a label survives its
    node being dragged and does not survive the socket it names ceasing to exist.

    `SocketKey` admits both without widening for the occasion — it is identifier segments joined
    by dots, and a bare `gtf` is one segment.

    **A channel name is derived, so it can move.** Add a second `annotation.gtf` channel in phase
    3 and one of them becomes `gtf_2`; a label keyed on the old name detaches. That is a real
    cost and it is smaller than the alternative it replaced, where three ports of one channel
    could carry three different names on one box. Phase 3's `DraftChannel` gives a channel an
    identity on the *draft*, which is where a stable key for this belongs.
    """

    label: Line = ""


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
    """What a person called each socket. **Read by the canvas and by nothing else** — see
    `DraftLabel`, which carries the argument for why that boundary is worth a guard."""
    profile: DataProfile = Field(default_factory=DataProfile)
    """Carried because an advisory check may want to say *the rule that would have fired here
    read a measurement you have not supplied*. `validate` never resolves; it only reports."""
