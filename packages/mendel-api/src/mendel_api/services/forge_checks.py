"""The engine's findings on an adaptation's questions (#452) and contract (#460), from the
current items.

Recomputed on every read and never stored: advice describes what is there now. Read by the
adaptation view (collapsed rows), the question context (the open card) and the prompts.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from comeni_core.declared.constraints import check_constraints
from comeni_core.declared.contract import Provenance
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.checks import QuestionFinding, contract_findings, findings
from mendel_forge.forging.model import Adaptation, Piece, Status
from mendel_forge.forging.values import contract_of
from mendel_forge.nfcore.parse import parse_module
from mendel_resolver.rules.format import Decision, Derivation
from mendel_resolver.rules.validate import check_table

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
    items = {k: i.value for k, i in state.items.items() if i.status is not Status.REMOVED}
    return _with_rule_checks(_module_findings(source, path, state, items), items)


def _with_rule_checks(found: dict[str, list[QuestionFinding]],
                      items: dict) -> dict[str, list[QuestionFinding]]:
    """A drafted rule's table checked as the registry will (#461): a gap over several facts,
    a dead row, too many cases. A rule that does not yet validate has nothing to check."""
    if not any(key.startswith("rules:rule:") for key in items):
        return found
    stack = registry.stack()
    derived = {d.fact: d.kind for d in stack.rules.derivations}
    for key, value in items.items():
        if key.startswith("rules:derive:"):
            try:
                drafted = Derivation.model_validate(value)
            except ValueError:
                continue
            derived[drafted.fact] = drafted.kind
    for key, value in items.items():
        if not key.startswith("rules:rule:"):
            continue
        try:
            decision = Decision.model_validate(value)
        except ValueError:
            continue
        for message in check_table(decision, measurements=stack.measurements, derived=derived):
            code, _, says = message.partition(": ")
            found.setdefault(key, []).append(QuestionFinding(code=code, says=says))
    return found


@dataclass(frozen=True)
class ModuleSource:
    """What the checks read of a module's source: its parsed `main.nf`, its text, and its input
    channels as `meta.yml` declares them. Shared between reads, so nothing may change it."""

    spec: ModuleSpec
    text: str
    channels: dict


_FILES = ("main.nf", "meta.yml", "environment.yml")


def _stamp(folder: Path) -> tuple:
    """Each source file's size, modification time and inode: what says the source moved."""
    found = []
    for name in _FILES:
        try:
            st = os.stat(folder / name)
        except OSError:
            continue
        found.append((name, st.st_size, st.st_mtime_ns, st.st_ino))
    return tuple(found)


@lru_cache(maxsize=32)
def _parsed(folder: Path, path: str, source: str, _stamp: tuple) -> ModuleSource:
    main_nf = folder / "main.nf"
    return ModuleSource(
        spec=ModuleSpec.parse(main_nf), text=main_nf.read_text(),
        channels={c.name: c for c in parse_module(folder, path, source).inputs})


def module_source(folder: Path, path: str, source: str) -> ModuleSource:
    """The module's source, parsed once for each state of its files (#576): `forging.read`
    is polled every 2 s while a forging drafts or asks, and each read parsed `main.nf` and
    `meta.yml` again, 5 to 20 ms. **Keyed by the files' stats**, so an edit is parsed again; a
    rewrite keeping size, modification time and inode is not seen, as with the data scan."""
    return _parsed(folder, path, source, _stamp(folder))


def _module_findings(source: str, path: str, state: Adaptation,
                     items: dict) -> dict[str, list[QuestionFinding]]:
    asked = {k: v for k, v in asked_questions(state).items()
             if k.startswith("questions:input_type:")}
    drafted = any(k.startswith("contract:") for k in items)
    if not asked and not drafted:
        return {}
    folder = forging.module_folder(source, path)
    main_nf = folder / "main.nf"
    if not main_nf.is_file():
        return {}
    module = module_source(folder, path, source)
    spec = module.spec
    found: dict[str, list[QuestionFinding]] = {}
    if asked:
        found.update(findings(items, dict(registry.stack().vocabulary.grains), spec,
                              dict(module.channels), asked))
    if drafted:
        for key, more in contract_findings(items, spec, module.text).items():
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
