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

from mendel_resolver import layers
from pydantic import BaseModel, ConfigDict

from mendel_forge import assemble, modulegen, sources
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
