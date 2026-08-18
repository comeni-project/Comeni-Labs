"""Does this draft hold up? Five questions, cheapest first.

**Four of the five rungs are machinery that already exists**, pointed at a draft instead of
at a build. That is the argument for this shape over a bespoke validator: a second
implementation of *"is this contract sound"* would disagree with the first one inside a plan.

Two weaknesses, recorded rather than left to be found:

- **Rung 4 is a transcription check for a generated module, not an independent one.** The
  contract and the module descend from one `Observation`, so agreement proves the two code
  paths match, not that either is right. It is still worth running — it catches real bugs —
  and it is not the guarantee it is for a vendored nf-core module, where the module is
  foreign ground truth.
- **Rung 5 warns rather than refuses**, because a tool added before the goal that needs it
  is a reasonable thing to do.
"""

import re
from enum import StrEnum
from pathlib import Path

from comeni_core import diagnostics
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.roles import UnknownRoleError
from comeni_core.declared.vocabulary import UnknownStateError, UnknownTypeError
from mendel_compiler import conformance
from mendel_compiler.conformance import Diagnostic
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers
from mendel_resolver.layers import Layers
from pydantic import BaseModel, ConfigDict, ValidationError

from mendel_forge import assemble
from mendel_forge.scaffold import Scaffold

_CODE = re.compile(r"\b([A-Z]{2}\d{4})\b")


class Rung(StrEnum):
    """The five questions, in the order they are asked — which is cheapest first.

    Order is load-bearing: `verify` stops at the first refusal, so a reviewer sees the
    one refusal that caused the rest to be skipped rather than a wall of consequences.
    """

    COMPLETE = "complete"
    CONSTRUCTS = "constructs"
    LOADS = "loads"
    CONFORMS = "conforms"
    ROUTES = "routes"


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rung: Rung
    diagnostics: list[Diagnostic] = []
    refused: bool = False


def refuses(verdicts: list[Verdict]) -> bool:
    return any(v.refused for v in verdicts)


def verify(scaffold: Scaffold, *, registry_root: Path, source_root: Path) -> list[Verdict]:
    verdicts: list[Verdict] = []

    complete = _complete(scaffold)
    verdicts.append(complete)
    if complete.refused:
        return verdicts

    constructs = _constructs(scaffold)
    verdicts.append(constructs)
    if constructs.refused:
        return verdicts

    stack = layers.load(registry_root)
    contract = assemble.contract_from(scaffold, approved_by="(unapproved)", approved_at="")

    loads = _loads(contract, stack)
    verdicts.append(loads)
    if loads.refused:
        return verdicts

    verdicts.append(_conforms(contract, source_root))
    verdicts.append(_routes(contract, stack))
    return verdicts


def _reused_code(message: str) -> str | None:
    """The code the loader already used, if it used one.

    Reusing it is the Global Constraint: a draft failing the load rung fails it for
    exactly the reason a build would, so `mendel explain MD0009` answers both. `MF0009`
    is the fallback for the sites issue #18 has not reached — `UnknownTypeError` is
    raised bare, while `UnknownStateError` carries MD0009 and `UnknownRoleError` MD0302.
    """
    found = _CODE.search(message)
    return found.group(1) if found else None


def _load_failure(contract_id: str, message: str, *, code: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        where=contract_id,
        summary="the layer stack does not declare something this contract names",
        detail=f"    {message}",
        fix="declare it in a layer below this one, or correct the id",
    )


def _complete(scaffold: Scaffold) -> Verdict:
    if scaffold.is_complete():
        return Verdict(rung=Rung.COMPLETE)
    open_fields = sorted(h.subject for h in scaffold.holes)
    return Verdict(
        rung=Rung.COMPLETE,
        refused=True,
        diagnostics=[
            Diagnostic(
                code="MF0004",
                where=scaffold.target,
                summary=f"{len(open_fields)} field(s) still open",
                detail="    " + "\n    ".join(open_fields),
                fix="run `forge show` for what each hole wants, then `forge fill` for each",
            )
        ],
    )


def _constructs(scaffold: Scaffold) -> Verdict:
    try:
        assemble.contract_from(scaffold, approved_by="(unapproved)", approved_at="")
    except ValidationError as exc:
        return Verdict(
            rung=Rung.CONSTRUCTS,
            refused=True,
            diagnostics=[
                Diagnostic(
                    code="MF0007",
                    where=scaffold.target,
                    summary="every hole is filled and the contract still does not construct",
                    detail="\n".join(
                        f"    {'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                        for error in exc.errors()
                    ),
                    fix="correct the value at each field path above; they are the model's own",
                )
            ],
        )
    except (KeyError, ValueError) as exc:
        # A missing `filled` key reaches here as a `KeyError` from `contract_from`. It is a
        # refusal for the same reason: the scaffold claims completeness it does not have.
        return Verdict(
            rung=Rung.CONSTRUCTS,
            refused=True,
            diagnostics=[
                Diagnostic(
                    code=_reused_code(str(exc)) or "MF0007",
                    where=scaffold.target,
                    summary="the filled scaffold does not construct a contract",
                    detail=f"    {exc}",
                    fix="check that every field the contract requires has been filled",
                )
            ],
        )
    return Verdict(rung=Rung.CONSTRUCTS)


def _loads(contract: ModuleContract, stack: Layers) -> Verdict:
    found: list[Diagnostic] = []
    for check in (
        lambda: contract.check_against(stack.vocabulary),
        lambda: stack.roles.check(contract.id, contract.roles),
    ):
        try:
            check()
        except (UnknownTypeError, UnknownStateError, UnknownRoleError) as exc:
            message = str(exc)
            reused = _reused_code(message)
            if reused is not None:
                found.append(_load_failure(contract.id, message, code=reused))
            else:
                found.append(_load_failure(contract.id, message, code="MF0009"))
    return Verdict(rung=Rung.LOADS, diagnostics=found, refused=bool(found))


def _conforms(contract: ModuleContract, source_root: Path) -> Verdict:
    path = conformance.module_path(contract, source_root)
    if not path.exists():
        return Verdict(
            rung=Rung.CONFORMS,
            diagnostics=[
                Diagnostic(
                    code="MD0100",
                    where=contract.id,
                    summary="unverified: no module source to check this contract against",
                    detail=f"    looked for {path}",
                    fix="vendor the module, or accept that this contract cannot be curated",
                )
            ],
        )
    found = conformance.against(contract, ModuleSpec.parse(path), path)
    refused = any(diagnostics.spec_for(d.code).refuses for d in found)
    return Verdict(rung=Rung.CONFORMS, diagnostics=found, refused=refused)


def _routes(contract: ModuleContract, stack: Layers) -> Verdict:
    """Can anything in the layer consume what this produces?

    Asked over `consumes` rather than through `producers_of`, which answers the opposite
    question. A leaf is legitimate, so this warns — see `MF0006`.
    """
    wanted = {
        alternative.type_id
        for other in stack.registry.all()
        if other.id != contract.id
        for port in other.consumes
        for alternative in port.alternatives()
    }
    found = [
        Diagnostic(
            code="MF0006",
            where=contract.id,
            summary=f"nothing in this layer consumes {port.type_id}",
            detail=f"    {contract.nf_process}.out.{port.name} reaches no other contract",
            fix="check the type id, or accept it as a leaf if this is a terminal step",
        )
        for port in contract.produces
        if port.type_id not in wanted
    ]
    return Verdict(rung=Rung.ROUTES, diagnostics=found, refused=False)
