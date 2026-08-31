"""One typed function per verb. **The only layer with logic.**

The CLI renders these results and the HTTP app serialises them; neither decides anything.
That is what makes `forge draft --json` and `POST /draft` the same payload rather than two
payloads that agree today — and it is what Plan 3's GUI will call, so a screen never has to
reimplement a verb to display it.

**Refusals raise.** A result carrying a maybe-error means both transports have to remember
to check it, and one of them will not. One `ValueError` carrying a coded message, caught in
one place per transport, turns into an exit code or a 4xx.

**No `Context` mixin.** Each request declares exactly the paths its verb touches, so
`CheckRequest` cannot demand a workspace it never writes to. A shared base would make every
request claim every capability, which is the opposite of what a typed surface is for.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from comeni_core.diagnostics import coded
from comeni_core.review import ValueSource
from mendel_compiler import conformance
from mendel_compiler.conformance import Diagnostic
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers
from mendel_resolver.layers import Layers
from pydantic import BaseModel, ConfigDict, Field

from mendel_forge import assemble, candidates, modulegen, sources
from mendel_forge import drift as drift_tables
from mendel_forge.land import LandResult, accept_drift
from mendel_forge.land import land as _run_land
from mendel_forge.observe import Excerpt
from mendel_forge.ports import HoleFiller
from mendel_forge.scaffold import Decision, FilledValue, Hole, Proposal, Scaffold
from mendel_forge.sources import ToolRef
from mendel_forge.verify import Verdict
from mendel_forge.verify import verify as _run_verify
from mendel_forge.workspace import Draft, Workspace

_NO_EXTRAS = ConfigDict(extra="forbid")


def _ident(ref: ToolRef) -> str:
    """The contract-id namespace the shipped registry already uses — `nf-core/fastqc`."""
    return f"{ref.source}/{ref.ident}"


class SourcesResult(BaseModel):
    model_config = _NO_EXTRAS

    names: list[str]


class DiscoverRequest(BaseModel):
    model_config = _NO_EXTRAS

    source_root: Path
    source: str | None = None


class DiscoverResult(BaseModel):
    model_config = _NO_EXTRAS

    refs: list[str]


class DraftRequest(BaseModel):
    model_config = _NO_EXTRAS

    ref: str
    name: str
    registry_root: Path
    source_root: Path
    workspace_root: Path
    version: str = "0.0.0"
    """A source may not know one — nf-core carries it in the container tag and a bare tool
    directory does not. A default that is obviously wrong beats one that looks right."""


class DraftResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    target: str
    holes: list[Hole]
    filled: dict[str, FilledValue]
    generated_module: bool


class ShowRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    registry_root: Path
    source_root: Path
    workspace_root: Path


class ShowResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    target: str
    holes: list[Hole]
    filled: dict[str, FilledValue]
    proposed: dict[str, Proposal] = Field(default_factory=dict)
    """Field -> what it needs declared. Keyed by field because two ports may need the same
    new type and a reviewer should see both places it was wanted."""
    module: str | None = None
    changed_at: datetime | None = None
    """When the draft was last written. `None` where a caller did not ask — the CLI
    prints a draft and does not need it; the queue's "what moved" filter does."""


class FillRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str
    value: Any
    by: str
    why: str
    workspace_root: Path


class FillResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str
    remaining: list[str]


class ProposeRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str
    id: str
    description: str
    why: str
    by: str
    workspace_root: Path


class ProposeResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str
    remaining: list[str]
    """**Still contains `field`.** A proposal is not a fill — the hole stays open, and a
    caller reading `remaining` to decide whether a draft can land must get that answer."""


class DecideRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str
    decision: Decision
    why: str
    by: str
    workspace_root: Path
    id: str | None = None
    """A better id than the one proposed. `None` keeps the proposal's own."""


class DecideResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str
    decision: Decision
    value: str | None
    """What was written, on an approval. `None` on a rejection — the hole is still open."""
    remaining: list[str]


class ModelFillRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str | None = None
    """`None` attempts every candidate-bearing hole."""
    workspace_root: Path
    model: str
    api_key: str | None = None
    base_url: str | None = None
    registry_root: Path | None = None
    """Needed to recompute a dependent hole's candidates once what it depends on is filled.
    `None` skips that, which leaves a name hole with only the module's channel names."""


class ModelFillOutcome(BaseModel):
    model_config = _NO_EXTRAS

    field: str
    filled: bool
    value: Any | None = None
    why: str | None = None
    proposed_id: str | None = None
    """Set when the model answered *nothing declared fits, and here is what would*. The hole
    stays open — a proposal is not a fill. See `notes/specs/2026-08-17-vocabulary-proposals.md`."""
    proposed_description: str | None = None
    declined_because: str | None = None
    """Why a hole was not filled. **Never `None` when `filled` is false** — a hole nobody
    attempted must not look like a hole that does not exist, and 'it has no candidates' and
    'the model declined' are different problems with different fixes."""


class ModelFillResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    outcomes: list[ModelFillOutcome]
    remaining: list[str]


class VerifyRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    registry_root: Path
    source_root: Path
    workspace_root: Path


class VerifyResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    verdicts: list[Verdict]
    refused: bool


def sources_() -> SourcesResult:
    return SourcesResult(names=sources.names())


def discover(req: DiscoverRequest) -> DiscoverResult:
    if req.source is None:
        found = sources.discover_all(req.source_root)
    else:
        found = sources.get(req.source).discover(req.source_root)
    return DiscoverResult(refs=[str(ref) for ref in found])


def draft(req: DraftRequest) -> DraftResult:
    ref = ToolRef.parse(req.ref)
    observation = sources.get(ref.source).ingest(ref, req.source_root)
    stack = layers.load(req.registry_root)
    scaffold = assemble.scaffold_for(observation, stack, ident=_ident(ref), version=req.version)
    module = modulegen.skeleton(scaffold) if modulegen.needs_module(observation) else None

    workspace = Workspace(root=req.workspace_root)
    # **Before saving, because `Workspace.save` overwrites.** `mkdir(exist_ok=True)` then
    # `write_text` replaced every answer, proposal and decision on a draft of the same name
    # and said nothing — true since forge phase 1, and one careless click in a form.
    #
    # `names()` rather than a file check: it is the same list `MF0008` prints when a draft is
    # missing, and two ways of asking *is this a draft* would eventually disagree.
    if req.name in workspace.names():
        raise ValueError(
            coded("MF0010", f"a draft named {req.name!r} already exists")
            + f"\n  drafts: {', '.join(workspace.names())}"
            + "\n  pick another name, or delete that one — `forge show` is what is in it"
        )
    workspace.save(Draft(name=req.name, scaffold=scaffold, module=module))
    return DraftResult(
        name=req.name,
        target=scaffold.target,
        holes=scaffold.holes,
        filled=scaffold.filled,
        generated_module=module is not None,
    )


def show(req: ShowRequest) -> ShowResult:
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    return ShowResult(
        name=found.name,
        target=found.scaffold.target,
        holes=found.scaffold.holes,
        filled=found.scaffold.filled,
        proposed=found.scaffold.proposed,
        module=found.module,
        changed_at=workspace.changed_at(req.name),
    )


def fill(req: FillRequest) -> FillResult:
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    filled = found.scaffold.fill(req.field, req.value, ValueSource.HUMAN, by=req.by, why=req.why)
    workspace.save(found.model_copy(update={"scaffold": filled}))
    return FillResult(
        name=req.name,
        field=req.field,
        remaining=sorted(h.subject for h in filled.holes),
    )


def propose(req: ProposeRequest) -> ProposeResult:
    """Record that nothing declared fits this hole.

    The mirror of `fill`, with one difference that is the entire point: the hole stays open.
    `Scaffold.propose` enforces that the field is a hole and raises `MF0002` otherwise.
    """
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    proposed = found.scaffold.propose(
        req.field,
        Proposal(id=req.id, description=req.description, why=req.why, by=req.by),
    )
    workspace.save(found.model_copy(update={"scaffold": proposed}))
    return ProposeResult(
        name=req.name,
        field=req.field,
        remaining=sorted(h.subject for h in proposed.holes),
    )


def decide(req: DecideRequest) -> DecideResult:
    """Approve or reject a proposal. `Scaffold.decide` holds the asymmetry."""
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    settled = found.scaffold.decide(req.field, req.decision, by=req.by, why=req.why, id=req.id)
    workspace.save(found.model_copy(update={"scaffold": settled}))
    return DecideResult(
        name=req.name,
        field=req.field,
        decision=req.decision,
        value=settled.filled[req.field].value if req.decision is Decision.APPROVED else None,
        remaining=sorted(h.subject for h in settled.holes),
    )


def _with_fresh_candidates(hole: Hole, scaffold: Scaffold, stack: "Layers | None") -> Hole:
    """Recompute a dependent hole's candidates now that what it depends on is settled.

    Holes were independent and never should have been: a port's name comes from its type, so
    asking both from the same fixed candidate list produced a model that answered `gtf` for one
    and `genome.index.hisat2` for the other — the same port, contradicted across two calls.
    """
    siblings = _settled_ports(scaffold)
    if hole.after is None or stack is None:
        # **Still gains its siblings.** Only a name hole declares `after`, and the port whose
        # type was answered `alignment.bai` for a BAM input is a type hole — the one that most
        # needs to know what the tool's other ports already are.
        return hole.model_copy(update={"evidence": [*hole.evidence, *siblings]})
    settled = scaffold.filled.get(hole.after)
    if settled is None:
        return hole.model_copy(update={"evidence": [*hole.evidence, *siblings]})
    return hole.model_copy(
        update={
            "evidence": [*hole.evidence, *siblings],
            "candidates": candidates.for_field(
                hole.subject,
                stack,
                type_id=str(settled.value),
                channels=hole.channels,
                excluding=scaffold.filled["id"].value.split("@")[0]
                if "id" in scaffold.filled
                else None,
            )
        }
    )


def _settled_ports(scaffold: Scaffold) -> list[Excerpt]:
    """What this tool's other ports have already been decided to be.

    **The same defect as asking about a port by index, one level up.** `samtools/index`'s own
    documentation for its input port reads `"input file"` — no signal at all — so a model falls
    back on the tool description, which says *index*, and answers `alignment.bai`. The tool does
    produce a `.bai`; just not there.

    Meanwhile the answer sits in the same scaffold: the *output* port is already settled. Saying
    so turns "what type is this port" into "what type is this port, given the others", which is
    the question a person answers.

    Recomputed per hole rather than baked in at draft time, because what is settled changes as
    the draft is filled — the first hole sees nothing and the last sees everything.
    """
    decided = [
        (field.removesuffix(".type_id"), str(value.value))
        for field, value in sorted(scaffold.filled.items())
        if field.endswith(".type_id")
    ]
    return [
        Excerpt(locator="this draft", text=f"{port} has already been settled as {type_id}")
        for port, type_id in decided
    ]


def fill_with_model(req: ModelFillRequest, filler: HoleFiller | None = None) -> ModelFillResult:
    """Attempt each hole, persisting after each one.

    **Per fill, not per batch.** A provider dying after eight of fifteen holes must cost
    nothing — the draft is what the forge accumulates, and an all-or-nothing batch makes a
    flaky network expensive.

    `filler` is injected by tests; `None` builds a `ModelFiller` from the request. This is a
    separate verb from `fill` rather than a mode on it because `FillRequest`'s `value`, `by`
    and `why` are all required and a model fill supplies none of them up front — sharing one
    request model would mean weakening the hand-fill path to suit the model one.
    """
    # **Imported here rather than at module scope.** `mendel-ai` is an optional extra of this
    # package (`mendel-forge[model]`): the served API cannot reach this verb, and the model
    # client is 152MB of the image. A top-level import made an opt-in path a mandatory
    # dependency, which is the same mistake `--no-ai` not being a flag exists to avoid.
    from mendel_ai.access import ModelAccess
    from mendel_ai.client import Client

    from mendel_forge.filler import ModelFiller

    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    if filler is None:
        filler = ModelFiller(
            Client(ModelAccess(model=req.model, api_key=req.api_key, base_url=req.base_url)),
            model_id=req.model,
        )

    targets = [h for h in found.scaffold.holes if req.field is None or h.subject == req.field]
    if req.field is not None and not targets:
        raise ValueError(coded("MF0002", f"{req.field} is not a hole in {req.name}"))
    # **Dependencies first.** A port's name candidates come from its type, so a hole carrying
    # `after` must be asked once that field is settled — otherwise its right answer may not be
    # among the candidates at all, which is how `multiqc` was offered one option and it was
    # wrong. Stable within each group, so the order stays deterministic.
    targets = sorted(targets, key=lambda h: h.after is not None)
    stack = layers.load(req.registry_root) if req.registry_root else None

    outcomes: list[ModelFillOutcome] = []
    for hole in targets:
        # **The refreshed hole replaces the stored one.** Handing the filler a copy with fresh
        # candidates while the scaffold kept the stale list meant `Scaffold.fill` looked the
        # hole up by field and refused its own model's answer with MF0003 — and the raise took
        # down the whole draft, not the one hole. `hisat2/align` and `star/align` both died
        # that way on a legal answer.
        hole = _with_fresh_candidates(hole, found.scaffold, stack)
        found = found.model_copy(update={"scaffold": found.scaffold.replacing(hole)})
        answer = filler.fill(hole, found.scaffold.observation)
        if isinstance(answer, Proposal):
            found = found.model_copy(
                update={"scaffold": found.scaffold.propose(hole.subject, answer)}
            )
            workspace.save(found)
            outcomes.append(
                ModelFillOutcome(
                    field=hole.subject,
                    filled=False,
                    proposed_id=answer.id,
                    proposed_description=answer.description,
                    why=answer.why,
                    declined_because="nothing declared fits; a new entry is proposed",
                )
            )
            continue
        if answer is None:
            outcomes.append(
                ModelFillOutcome(
                    field=hole.subject,
                    filled=False,
                    declined_because=(
                        "no candidates — free text, and a person answers it"
                        if not hole.candidates
                        else "the model declined or its answer did not validate"
                    ),
                )
            )
            continue
        found = found.model_copy(
            update={
                "scaffold": found.scaffold.fill(
                    hole.subject, answer.value, ValueSource.MODEL, by=answer.by, why=answer.why
                )
            }
        )
        workspace.save(found)
        outcomes.append(
            ModelFillOutcome(field=hole.subject, filled=True, value=answer.value, why=answer.why)
        )

    return ModelFillResult(
        name=req.name,
        outcomes=outcomes,
        remaining=sorted(h.subject for h in found.scaffold.holes),
    )


def verify_(req: VerifyRequest) -> VerifyResult:
    found = Workspace(root=req.workspace_root).load(req.name)
    verdicts = _run_verify(
        found.scaffold, registry_root=req.registry_root, source_root=req.source_root
    )
    return VerifyResult(
        name=req.name, verdicts=verdicts, refused=any(v.refused for v in verdicts)
    )


class Drift(BaseModel):
    model_config = _NO_EXTRAS

    contract_id: str
    field: str
    registry_says: str
    source_says: str
    code: str | None = None
    """The conformance diagnostic that found it. `None` means a value comparison did —
    `registry_says` and `source_says` are then two values rather than a summary and a fix.

    **Two checkers, one list.** A reader asking *does this contract still describe its
    module* does not care which check noticed; before phase 5 a renamed `emit:` label —
    which breaks emission — reported as `matching`, because `Status` read the value half
    only. Spec §3.5."""


class CheckRequest(BaseModel):
    model_config = _NO_EXTRAS

    registry_root: Path
    source_root: Path
    """No workspace: `check` reads and reports, and writes nothing anywhere."""
    stack: Layers | None = None
    """A layer stack the caller already loaded. `None` loads one.

    The CLI never passes it. `mendel-api` does, because this is one of the two verbs behind the
    slowest endpoints, and a cache the endpoint's own work bypasses measures nothing (phase 7,
    audit A132)."""


class CheckResult(BaseModel):
    model_config = _NO_EXTRAS

    checked: int
    skipped: list[str]
    """Contracts no registered source could re-read — a `comeni/` contract over a vendored
    module, or a namespace with no adapter. Reported rather than silently passed, because a
    contract nothing checks looks exactly like a contract that agrees."""
    drift: list[Drift]


class UpdateRequest(BaseModel):
    model_config = _NO_EXTRAS

    contract_id: str
    name: str
    registry_root: Path
    source_root: Path
    workspace_root: Path


def _ref_for(contract_id: str) -> ToolRef | None:
    """`nf-core/samtools/sort@1.21.0` -> `nf-core:samtools/sort`, when that source exists.

    Keyed on the contract-id **namespace** rather than on `provenance.source`, which the
    shipped registry spells `nf-core-meta-yml` — a note about what was read, not the name
    of an adapter. The namespace is what `_ident` wrote, so this is its inverse.
    """
    source, _, tool = contract_id.partition("/")
    ident = tool.partition("@")[0]
    if not ident or source not in sources.names():
        return None
    return ToolRef(source=source, ident=ident)


def check(req: CheckRequest) -> CheckResult:
    """Does the registry still say what its sources say?

    Offline by decision — whether *upstream* has moved is issue #64. This asks the narrower
    question that needs no network: does what is on this disk still agree with itself.
    """
    stack = req.stack if req.stack is not None else layers.load(req.registry_root)
    found: list[Drift] = []
    skipped: list[str] = []
    checked = 0
    for contract in stack.registry.all():
        # **Conformance runs over every contract, including the skipped ones.** `skipped` is
        # about a missing source *adapter*; a module file is a separate fact, and the two
        # `comeni/` contracts have a readable module and nothing that can re-draft them
        # (phase 4 §3.4). So the structural half covers twelve where the value half covers ten.
        module = conformance.module_path(contract, stack.modules)
        if module is not None and module.exists():
            found += [
                Drift(
                    contract_id=contract.id,
                    field=drift_tables.field_for(diagnostic.code) or "",
                    registry_says=diagnostic.summary,
                    source_says=diagnostic.fix,
                    code=diagnostic.code,
                )
                for diagnostic in conformance.against(contract, ModuleSpec.parse(module), module)
            ]

        ref = _ref_for(contract.id)
        if ref is None:
            skipped.append(contract.id)
            continue
        try:
            observation = sources.get(ref.source).ingest(ref, req.source_root)
        except (FileNotFoundError, ValueError):
            skipped.append(contract.id)
            continue
        checked += 1
        for fact_name, field in assemble.DERIVED_FIELDS:
            says = observation.fact(fact_name)
            declared = getattr(contract, field, None)
            if says is None or declared == says:
                continue
            found.append(
                Drift(
                    contract_id=contract.id,
                    field=field,
                    registry_says=str(declared),
                    source_says=str(says),
                )
            )
    return CheckResult(
        checked=checked,
        skipped=sorted(skipped),
        drift=sorted(found, key=lambda d: (d.contract_id, d.field, d.code or "")),
    )


class FieldCheck(BaseModel):
    model_config = _NO_EXTRAS

    field: str
    impact: drift_tables.Impact
    registry_says: str
    source_says: str
    agrees: bool
    locator: str | None
    """Where the source states it — `file:line`, relative to the source root.

    `None` for `nf_include`, whose fact is **synthesised from the convention** rather than read
    off a line. The screen must not present that one as a quotation."""
    excerpt: str | None


class Unchecked(BaseModel):
    model_config = _NO_EXTRAS

    field: str
    impact: drift_tables.Impact
    why: str


class DriftReport(BaseModel):
    model_config = _NO_EXTRAS

    contract_id: str
    verifiable: bool
    """A registered source could re-read the tool. `False` is phase 4's `unverifiable`."""
    module_read: bool
    """The vendored `main.nf` parsed. A DIFFERENT condition from `verifiable` — phase 4 §3.4."""
    checks: list[FieldCheck]
    conformance: list[Diagnostic]
    unchecked: list[Unchecked]
    verdict: drift_tables.Verdict
    says: str


class DriftRequest(BaseModel):
    model_config = _NO_EXTRAS

    contract_id: str
    registry_root: Path
    source_root: Path
    stack: Layers | None = None
    """A layer stack the caller already loaded. `None` loads one — see `CheckRequest.stack`."""


def _observe(contract_id: str, source_root: Path):
    """The source's own account of a tool, or `None` when nothing can re-read it."""
    ref = _ref_for(contract_id)
    if ref is None:
        return None
    try:
        return sources.get(ref.source).ingest(ref, source_root)
    except (FileNotFoundError, ValueError):
        return None


def drift(req: DriftRequest) -> DriftReport:
    """Everything anything can say about one contract against its source.

    Three groups, and every one of `ModuleContract`'s fields is in exactly one — spec §3.2. The
    third group is on the report rather than left out of it, because the fields nothing can
    check include three of the five the router reads.
    """
    stack = req.stack if req.stack is not None else layers.load(req.registry_root)
    contract = stack.registry.contracts.get(req.contract_id)
    if contract is None:
        known = ", ".join(sorted(stack.registry.contracts)[:5])
        raise ValueError(
            coded("MF0106", f"no contract in this registry is {req.contract_id!r}")
            + f"\n  known: {known}…"
        )

    checks: list[FieldCheck] = []
    observation = _observe(req.contract_id, req.source_root)
    if observation is not None:
        for fact_name, field in assemble.DERIVED_FIELDS:
            says = observation.fact(fact_name)
            if says is None:
                continue
            declared = getattr(contract, field, None)
            evidence = observation.facts[fact_name].evidence
            locator = evidence.locator if ":" in evidence.locator else None
            checks.append(
                FieldCheck(
                    field=field,
                    impact=drift_tables.FIELDS[field].impact,
                    registry_says=str(declared),
                    source_says=str(says),
                    agrees=declared == says,
                    locator=locator,
                    excerpt=evidence.text if locator else None,
                )
            )

    module = conformance.module_path(contract, stack.modules)
    module_read = module is not None and module.exists()
    found = conformance.against(contract, ModuleSpec.parse(module), module) if module_read else []

    checked = {c.field for c in checks} | {
        field for field, facts in drift_tables.FIELDS.items() if facts.codes
    }
    unchecked = [
        Unchecked(
            field=field,
            impact=facts.impact,
            why="no source states it, and no conformance check reads it",
        )
        for field, facts in sorted(drift_tables.FIELDS.items())
        if field not in checked
    ]

    disagreeing = [c.field for c in checks if not c.agrees]
    refusing = drift_tables.refusing_of(d.code for d in found)
    verdict = drift_tables.verdict_for(disagreeing=disagreeing, refusing=refusing)
    return DriftReport(
        contract_id=req.contract_id,
        verifiable=observation is not None,
        module_read=module_read,
        checks=sorted(checks, key=lambda c: (c.agrees, c.field)),
        conformance=found,
        unchecked=unchecked,
        verdict=verdict,
        says=drift_tables.sentence_for(verdict, disagreeing=disagreeing, refusing=refusing),
    )


class AcceptRequest(BaseModel):
    model_config = _NO_EXTRAS

    contract_id: str
    field: str
    registry_root: Path
    source_root: Path
    by: str
    why: str
    """Required. A value changed with no reason recorded is the one thing this project is
    against — and `land()` has `approved_by` for the same reason one field over."""
    branch: str = "forge/drift"


class AcceptResult(BaseModel):
    model_config = _NO_EXTRAS

    contract_id: str
    field: str
    was: str
    now: str
    path: str
    branch: str
    commit: str


def _file_declaring(registry_root: Path, contract_id: str) -> Path:
    """Which file in the layer declares this contract.

    A `Registry` deliberately records no path — a contract is content-addressed (audit A10) and
    a field recording where it was found would make its digest depend on the machine that read
    it. So this looks, and refuses anything other than exactly one hit.
    """
    found = [
        path
        for path in sorted(registry_root.rglob("*.yml"))
        if f"id: {contract_id}" in path.read_text()
    ]
    if len(found) != 1:
        raise ValueError(
            coded("MF0106", f"{len(found)} files declare {contract_id!r} — expected exactly one")
        )
    return found[0]


def _file_declaring(registry_root: Path, contract_id: str) -> Path:
    """Which file in the layer declares this contract.

    A `Registry` deliberately records no path — a contract is content-addressed (audit A10) and
    a field recording where it was found would make its digest depend on the machine that read
    it. So this looks, and refuses anything other than exactly one hit.
    """
    found = [
        path
        for path in sorted(registry_root.rglob("*.yml"))
        if f"id: {contract_id}" in path.read_text()
    ]
    if len(found) != 1:
        raise ValueError(
            coded("MF0106", f"{len(found)} files declare {contract_id!r} — expected exactly one")
        )
    return found[0]


def _source_value(report: DriftReport, field: str) -> str:
    moved = [c for c in report.checks if c.field == field and not c.agrees]
    if not moved:
        raise ValueError(
            coded("MF0104", f"{field!r} on {report.contract_id} is not a value drift")
            + "\n  only a field a source states outright can be taken; a structural"
            " disagreement is settled by a re-draft through the queue"
        )
    return moved[0].source_says


def accept(req: AcceptRequest) -> AcceptResult:
    """Take the source's value for one field: patch, validate, commit.

    **The write itself lives in `land.py`**, which is the one module in this package that may
    write under a registry root — invariant 2's boundary, held by
    `test_only_land_and_the_workspace_write_to_disk`. What is here is the reading half:
    which field moved, what the source says it should be, and which file declares it.
    """
    report = drift(
        DriftRequest(
            contract_id=req.contract_id,
            registry_root=req.registry_root,
            source_root=req.source_root,
        )
    )
    now = _source_value(report, req.field)
    was = next(c.registry_says for c in report.checks if c.field == req.field)
    path = _file_declaring(req.registry_root, req.contract_id)

    branch, commit = accept_drift(
        registry=req.registry_root,
        path=path,
        contract_id=req.contract_id,
        field=req.field,
        value=now,
        vocabulary=layers.load(req.registry_root).vocabulary,
        by=req.by,
        why=req.why,
        branch=req.branch,
    )
    return AcceptResult(
        contract_id=req.contract_id,
        field=req.field,
        was=was,
        now=now,
        path=str(path.relative_to(req.registry_root)),
        branch=branch,
        commit=commit,
    )


def update(req: UpdateRequest) -> DraftResult:
    """Re-draft one contract from its source. **Writes a draft, never the registry.**"""
    ref = _ref_for(req.contract_id)
    if ref is None:
        raise ValueError(
            coded("MF0001", f"no registered source can re-read {req.contract_id!r}")
            + f"\n  known sources: {', '.join(sources.names()) or '(none)'}"
        )
    version = req.contract_id.partition("@")[2] or "0.0.0"
    return draft(
        DraftRequest(
            ref=str(ref),
            name=req.name,
            registry_root=req.registry_root,
            source_root=req.source_root,
            workspace_root=req.workspace_root,
            version=version,
        )
    )


class LandRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    registry: Path
    """Required and never defaulted — see `land.py`'s module docstring."""
    branch: str
    approved_by: str
    approved_at: str
    workspace_root: Path


def land(req: LandRequest) -> LandResult:
    found = Workspace(root=req.workspace_root).load(req.name)
    return _run_land(
        found,
        registry=req.registry,
        branch=req.branch,
        approved_by=req.approved_by,
        approved_at=req.approved_at,
    )


class ListRequest(BaseModel):
    model_config = _NO_EXTRAS

    workspace_root: Path


class ListResult(BaseModel):
    model_config = _NO_EXTRAS

    names: list[str]


def list_(req: ListRequest) -> ListResult:
    """The queue. A verb rather than a bare `Workspace.names()` call in each transport,
    because the CLI printing a list and the HTTP app returning one must be the same list."""
    return ListResult(names=Workspace(root=req.workspace_root).names())
