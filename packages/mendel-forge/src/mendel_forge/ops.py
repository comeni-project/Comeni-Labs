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
from mendel_resolver import layers
from pydantic import BaseModel, ConfigDict

from mendel_forge import assemble, modulegen, sources
from mendel_forge.land import LandResult
from mendel_forge.land import land as _run_land
from mendel_forge.scaffold import FilledValue, Filler, Hole
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
