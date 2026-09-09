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
from comeni_core.plan.tiers import Tier
from comeni_core.review.answer import ValueSource
from comeni_core.spell.marks import (
    ContractId,
    DecisionKey,
    HumanParamValue,
    Line,
    NfIdentifier,
    NodeId,
    PortName,
    SocketKey,
)

__all__ = [
    "ChannelSettled",
    "DraftChannel",
    "DraftProvenance",
    "DraftEdge",
    "DraftGraph",
    "DraftLabel",
    "DraftNode",
    "NodeSettled",
    "ParamSettled",
    "Settled",
    "DraftParam",
]


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
    door payload and `tests/guards/test_egress.py` is untouched by this change, which is the
    assertion rather than an aside. If a later change wants a label in `pipeline.yml`, that is a
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


class DraftChannel(BaseModel):
    """Which sockets share one channel. **A decision only a person can make.**

    Whether two GTF ports are fed by one file or by two is not derivable from the drawing: both
    are legal pipelines and they analyse different experiments. So the drawing carries it.

    **The default is one channel per type**, which is today's behaviour and the right answer for
    the spine's shared reference annotation — an empty `channels` list means exactly that, so no
    existing draft changes and nobody has to declare anything to keep working.

    Splitting is the canvas control the operator asked for (*"a pipeline needs to have two same
    type inputs"*), and merging two back is the same control in reverse.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: str | None = None
    """`run` or `sample`, when a person wants this channel to differ from its type's default.

    **`None` is the type's default and is not an override.** A reference genome is `run` because
    it is one file for the whole analysis, and saying so again on every draft would be noise —
    the artifact would then carry a `Why` for a decision nobody made, which is the failure mode
    §12.2 already refuses for channel *names*.

    An override is a genuine judgement about an experiment. Per-sample annotations over a shared
    one is a different analysis, not a different spelling, so it exits at **tier 4** and carries
    the reason the person gave: the product's claim is that no such judgement is silent.
    """

    why: Line = ""
    """Why this scope, in the words of whoever chose it. Read only when `scope` overrides.

    Empty is legal and is said in those words rather than replaced with the resolver's
    boilerplate — audits A77 and A111, and the same rule `DraftParam.why` follows.
    """

    ports: tuple[SocketKey, ...]
    """`<node>.<port>`, the sockets this channel feeds. **A tuple, so the model is hashable and
    frozen** — a draft is compared for equality on every render.

    Only ports a person has *moved off* the default need naming: an unlisted port keeps the
    one-channel-per-type behaviour. That keeps a draft's `channels` proportional to how much
    somebody has customised rather than to how large the pipeline is.
    """


class DraftNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    params: list[DraftParam] = Field(default_factory=list)


class DraftGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[DraftNode] = Field(default_factory=list)
    edges: list[DraftEdge] = Field(default_factory=list)
    channels: list[DraftChannel] = Field(default_factory=list)
    """Sockets a person has grouped into their own channel. **Empty is one channel per type**,
    which is what every draft meant before this field existed — see `DraftChannel`."""
    labels: list[DraftLabel] = Field(default_factory=list)
    """What a person called each socket. **Read by the canvas and by nothing else** — see
    `DraftLabel`, which carries the argument for why that boundary is worth a guard."""
    profile: DataProfile = Field(default_factory=DataProfile)
    """Carried because an advisory check may want to say *the rule that would have fired here
    read a measurement you have not supplied*. `validate` never resolves; it only reports."""


class Settled(BaseModel):
    """One decision somebody already made, kept so that redrawing does not re-attribute it.

    **The whole of §1.8 in one shape.** A resolver-settled step must keep its tier and its reason
    merely because Build paused to explain it; a person choosing a different candidate becomes the
    author of *that* choice and of nothing else; and a later manual edit must not relabel the
    untouched rest of a spawned pipeline as human.

    `source` is `ValueSource` rather than a new enum, because that vocabulary already draws
    exactly this line — resolver, goal, human, model — and a second one would be two answers to
    *who decided this*. `by` carries the model id when `source` is `MODEL`, which is what keeps
    `model_override_by` fillable: A130's point is that a pipeline an agent assembled must not
    read as one a person drew by hand.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: ValueSource
    tier: Tier
    reason: Line = ""
    axis_reason: Line = ""
    by: Line = ""
    """The model id, when `source` is `MODEL`. Empty otherwise, and empty is not a sentinel —
    a person has no id here, because `who` on the draft is attribution and not authentication."""


class NodeSettled(BaseModel):
    """What was already decided about one step: whether it exists, and which contract fills it.

    Two axes rather than one, because they are answered separately and can have different
    authors. The resolver can settle *that a trimmer belongs here* while a person settles *which
    trimmer* — and collapsing them would attribute both to whoever answered last.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: NodeId
    selection: Settled | None = None
    presence: Settled | None = None


class ParamSettled(BaseModel):
    """One setting, keyed exactly as the artifact keys it.

    `key` is `<node>.<param>` — the same spelling `ParamDecision.key` uses, because `Pipeline`'s
    MD0220 check looks a decision up by it. A second spelling here would be a sidecar the
    artifact cannot match, and the value would then be a review cleared by assertion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: DecisionKey
    settled: Settled


class ChannelSettled(BaseModel):
    """One channel's scope override, keyed by the sockets it feeds.

    **By ports rather than by name**, because a channel's *name* is derived — `channels_of`
    computes it from the registry — and the draft service diffs two graphs without loading a
    registry at all. Keying on the derived thing would make every edit pay for a registry load to
    answer a question the draft already contains.

    The ports are what a person actually chose when they split or merged a channel, so they are
    also the honest identity: rename the derivation tomorrow and this entry still names the same
    decision.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ports: tuple[SocketKey, ...]
    settled: Settled


class DraftProvenance(BaseModel):
    """Who settled what, per decision — **server-owned, and never accepted from a browser.**

    §1.8: *never put trusted provenance fields into browser-writable `DraftGraph` merely because
    that is the easiest payload to send.* A client that can post provenance can post
    `source: resolver` on a value it typed, and the product claim — nothing was guessed silently
    — becomes a claim the client makes about itself. `DraftIn` does not carry this; the service
    writes it, and `PipelineDraft.provenance` stores its JSON dump.

    **Lists rather than mappings**, keyed by declared aliases. A `dict[str, ...]` accepts any key
    and orders by insertion; a list of typed entries makes the key a validated `NodeId`,
    `DecisionKey` or `ChannelName`, and can be sorted into a stable order — which matters here
    because byte-identical emission is a hard requirement and this feeds the IR.

    **Empty means "nobody has recorded anything", which is what every existing draft is.**
    `ir_of` treats an absent sidecar as today's all-human behaviour, byte for byte.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    nodes: list[NodeSettled] = Field(default_factory=list)
    params: list[ParamSettled] = Field(default_factory=list)
    channels: list[ChannelSettled] = Field(default_factory=list)

    def node(self, node_id: str) -> NodeSettled | None:
        return next((n for n in self.nodes if n.node == node_id), None)

    def param(self, key: str) -> Settled | None:
        return next((p.settled for p in self.params if p.key == key), None)

    def channel(self, ports: tuple[str, ...]) -> Settled | None:
        return next((c.settled for c in self.channels if tuple(c.ports) == tuple(ports)), None)

    def retaining(
        self, *, nodes: set[str], params: set[str], channels: set[tuple[str, ...]]
    ) -> "DraftProvenance":
        """This sidecar with every entry whose subject is no longer in the graph dropped.

        **The removal half of the diff**, and it is separate from the stamping half on purpose:
        deciding what survives an edit is a question about the *graph*, and deciding who authored
        a change is a question about the *edit*. A node deleted and a node replaced are the same
        `nodes` set from here, and the caller is what tells them apart.
        """
        return DraftProvenance(
            nodes=[n for n in self.nodes if n.node in nodes],
            params=[p for p in self.params if p.key in params],
            channels=[c for c in self.channels if tuple(c.ports) in channels],
        )
