"""The engine's findings on an adaptation's questions (#452), from the current items.

Recomputed on every read and never stored: advice describes what is there now. Read by the
adaptation view (collapsed rows), the question context (the open card) and the prompts.
"""

from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.checks import QuestionFinding, findings
from mendel_forge.forging.model import Adaptation, Piece, Status
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
    if not asked:
        return {}
    folder = forging.module_folder(source, path)
    main_nf = folder / "main.nf"
    if not main_nf.is_file():
        return {}
    spec = ModuleSpec.parse(main_nf)
    channels = {c.name: c for c in parse_module(folder, path, source).inputs}
    items = {k: i.value for k, i in state.items.items()}
    return findings(items, dict(registry.stack().vocabulary.scopes), spec, channels, asked)
