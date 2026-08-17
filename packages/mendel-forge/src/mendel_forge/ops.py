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

from pathlib import Path
from typing import Any

from comeni_core.diagnostics import coded
from mendel_ai.access import ModelAccess
from mendel_ai.client import Client
from mendel_resolver import layers
from mendel_resolver.layers import Layers
from pydantic import BaseModel, ConfigDict

from mendel_forge import assemble, candidates, modulegen, sources
from mendel_forge.filler import ModelFiller
from mendel_forge.land import LandResult
from mendel_forge.land import land as _run_land
from mendel_forge.observe import Excerpt
from mendel_forge.ports import HoleFiller
from mendel_forge.scaffold import FilledValue, Filler, Hole, Proposal, Scaffold
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
    module: str | None = None


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
    Workspace(root=req.workspace_root).save(
        Draft(name=req.name, scaffold=scaffold, module=module)
    )
    return DraftResult(
        name=req.name,
        target=scaffold.target,
        holes=scaffold.holes,
        filled=scaffold.filled,
        generated_module=module is not None,
    )


def show(req: ShowRequest) -> ShowResult:
    found = Workspace(root=req.workspace_root).load(req.name)
    return ShowResult(
        name=found.name,
        target=found.scaffold.target,
        holes=found.scaffold.holes,
        filled=found.scaffold.filled,
        module=found.module,
    )


def fill(req: FillRequest) -> FillResult:
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    filled = found.scaffold.fill(req.field, req.value, Filler.HAND, by=req.by, why=req.why)
    workspace.save(found.model_copy(update={"scaffold": filled}))
    return FillResult(
        name=req.name,
        field=req.field,
        remaining=sorted(h.field for h in filled.holes),
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
                hole.field,
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
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    if filler is None:
        filler = ModelFiller(
            Client(ModelAccess(model=req.model, api_key=req.api_key, base_url=req.base_url)),
            model_id=req.model,
        )

    targets = [h for h in found.scaffold.holes if req.field is None or h.field == req.field]
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
                update={"scaffold": found.scaffold.propose(hole.field, answer)}
            )
            workspace.save(found)
            outcomes.append(
                ModelFillOutcome(
                    field=hole.field,
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
                    field=hole.field,
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
                    hole.field, answer.value, Filler.MODEL, by=answer.by, why=answer.why
                )
            }
        )
        workspace.save(found)
        outcomes.append(
            ModelFillOutcome(field=hole.field, filled=True, value=answer.value, why=answer.why)
        )

    return ModelFillResult(
        name=req.name,
        outcomes=outcomes,
        remaining=sorted(h.field for h in found.scaffold.holes),
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


class CheckRequest(BaseModel):
    model_config = _NO_EXTRAS

    registry_root: Path
    source_root: Path
    """No workspace: `check` reads and reports, and writes nothing anywhere."""


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
    stack = layers.load(req.registry_root)
    found: list[Drift] = []
    skipped: list[str] = []
    checked = 0
    for contract in stack.registry.all():
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
        drift=sorted(found, key=lambda d: (d.contract_id, d.field)),
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
