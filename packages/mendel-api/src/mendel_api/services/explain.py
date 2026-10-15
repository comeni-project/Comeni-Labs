"""What a question is about and why it is asked, from declared data only (Part I.1 §4).

`what` is curated (the registry's `explain`); `needed` and `settles` are the engine's, derived
from the gap walk. Nothing here calls a model; I.3 hands the same fields to one as sources.
"""

from mendel_authoring.brief import tool_of

from mendel_api.authoring.types import Explanation, FactKind, Reason
from mendel_api.services.gaps import Gap


def name_of(stack, kind: FactKind, subject: str) -> str:
    """A type by its declared name, a measurement by its description; the id when neither."""
    if kind is FactKind.INPUT:
        return stack.vocabulary.names.get(subject, subject)
    return stack.measurements.get(subject).description or subject


def _what(stack, gap: Gap) -> str | None:
    if gap.kind is FactKind.INPUT:
        return stack.vocabulary.explains.get(gap.subject)
    return stack.measurements.get(gap.subject).explain


def _steps(stack, contracts) -> list[Reason]:
    """One reason per tool, in walk order: its declared name and description, else its key."""
    seen: set[str] = set()
    out: list[Reason] = []
    for contract_id in contracts:
        key = tool_of(contract_id)
        if key in seen:
            continue
        seen.add(key)
        tool = stack.tools.tools.get(key)
        out.append(Reason(text=tool.name if tool else key,
                          detail=tool.description if tool else None))
    return out


def _lower(text: str) -> str:
    return text[:1].lower() + text[1:]


def explanation(gap: Gap, found: list[Gap], stack, *, measured: dict[str, set[str]],
                read: set[str], characterisable: bool,
                files: dict[str, int] | None = None) -> Explanation:
    """`found` is every gap still open, so `settles` promises only questions still to come.
    `files` is the most files a sample of each input type may be (`gathering._sample_files`)."""
    if gap.decides:
        needed = [Reason(text=d.because or f"decides the {d.targets()[0].of}", detail=d.cite)
                  for d in gap.decides]
        reads = "rule"
    else:
        needed = _steps(stack, gap.used_by)
        reads = "steps" if needed else None
    settles: list[str] = []
    read_by = None
    most = 1
    if gap.kind is FactKind.INPUT:
        settles = [_lower(name_of(stack, FactKind.MEASUREMENT, g.subject)) for g in found
                   if g.kind is FactKind.MEASUREMENT and gap.subject in measured.get(g.subject, ())]
        read_by = "inspector" if gap.subject in read else ("ai" if characterisable else None)
        most = (files or {}).get(gap.subject, 1)
    return Explanation(name=name_of(stack, gap.kind, gap.subject), what=_what(stack, gap),
                       needed=needed, reads=reads, settles=settles, read_by=read_by, files=most)
