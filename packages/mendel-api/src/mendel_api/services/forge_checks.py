"""The engine's findings on an adaptation's questions (#452) and contract (#460), from the
current items.

Recomputed on every read and never stored: advice describes what is there now. Read by the
adaptation view (collapsed rows), the question context (the open card) and the prompts.
"""

from comeni_core.declared.constraints import check_constraints
from comeni_core.declared.contract import Provenance
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.checks import QuestionFinding, contract_findings, findings
from mendel_forge.forging.model import Adaptation, Piece, Status
from mendel_forge.forging.values import contract_of
from mendel_forge.nfcore.parse import parse_module

from mendel_api.services import forging, registry


def asked_questions(state: Adaptation) -> dict[str, dict]:
    """Each live question's latest asking (options and suggestion); an answer replaces only
    the item's value."""
    out = {}
    for key, item in state.items.items():
        if item.piece is not Piece.QUESTIONS or item.status is Status.REMOVED:
            continue
        asked = next((r.value for r in reversed(item.revisions)
                      if isinstance(r.value, dict) and "asks" in r.value), None)
        if asked is not None:
            out[key] = asked
    return out


def for_adaptation(source: str, path: str, state: Adaptation) -> dict[str, list[QuestionFinding]]:
    asked = {k: v for k, v in asked_questions(state).items()
             if k.startswith("questions:input_type:")}
    items = {k: i.value for k, i in state.items.items() if i.status is not Status.REMOVED}
    drafted = any(k.startswith("contract:") for k in items)
    if not asked and not drafted:
        return {}
    folder = forging.module_folder(source, path)
    main_nf = folder / "main.nf"
    if not main_nf.is_file():
        return {}
    spec = ModuleSpec.parse(main_nf)
    found: dict[str, list[QuestionFinding]] = {}
    if asked:
        channels = {c.name: c for c in parse_module(folder, path, source).inputs}
        found.update(findings(items, dict(registry.stack().vocabulary.scopes), spec, channels,
                              asked))
    if drafted:
        for key, more in contract_findings(items, spec, main_nf.read_text()).items():
            found.setdefault(key, []).extend(more)
        found = _with_constraint_checks(found, items)
    return found


def _with_constraint_checks(found: dict[str, list[QuestionFinding]],
                            items: dict) -> dict[str, list[QuestionFinding]]:
    """MD0603–MD0606 on the contract the current items make, on its process item (#460).
    Items that do not yet make a contract have nothing to check."""
    if "contract:process" not in items:
        return found
    try:
        contract = contract_of(items, "draft/check@0", Provenance(
            source="forge", drafted_by="forge", approved_by="-", approved_at="-"))
    except (ValueError, KeyError):
        return found
    for message in check_constraints(contract):
        code, _, says = message.partition(": ")
        found.setdefault("contract:process", []).append(QuestionFinding(code=code, says=says))
    return found
