"""Result models to console text. No decisions, no lookups, no disk.

Every function here takes exactly one result model from `ops.py`, so a new field on a
result is a change in one place. **A hole prints why it is open**, not only its name — the
name alone tells a reader what to type and nothing about what to think, and the reasoning
is the part the forge exists to preserve.
"""

from mendel_forge import ops


def sources(result: ops.SourcesResult) -> str:
    return "\n".join(result.names) or "(none registered)"


def discover(result: ops.DiscoverResult) -> str:
    return "\n".join(result.refs) or "(nothing found)"


def draft(result: ops.DraftResult) -> str:
    lines = [f"{result.name} -> {result.target}"]
    if result.generated_module:
        lines.append("  a module was generated; its script body is a hole (MF0005)")
    lines.append(f"  {len(result.filled)} field(s) derived, {len(result.holes)} open")
    lines += _holes(result.holes)
    return "\n".join(lines)


def show(result: ops.ShowResult) -> str:
    lines = [f"{result.name} -> {result.target}", "", "filled:"]
    lines += [f"  {field} = {v.value!r}  ({v.filler}, {v.by})" for field, v in
              sorted(result.filled.items())]
    lines += ["", f"open ({len(result.holes)}):"]
    lines += _holes(result.holes)
    return "\n".join(lines)


def fill(result: ops.FillResult) -> str:
    if not result.remaining:
        return f"{result.field} filled; no holes remain"
    return f"{result.field} filled; {len(result.remaining)} left: {', '.join(result.remaining)}"


def verify(result: ops.VerifyResult) -> str:
    lines = []
    for verdict in result.verdicts:
        mark = "REFUSED" if verdict.refused else ("warn" if verdict.diagnostics else "ok")
        lines.append(f"{verdict.rung:<12} {mark}")
        lines += [f"    {d.render()}" for d in verdict.diagnostics]
    lines.append("")
    lines.append("refused" if result.refused else "no refusal")
    return "\n".join(lines)


def check(result: ops.CheckResult) -> str:
    lines = [f"checked {result.checked} contract(s)"]
    if result.skipped:
        lines.append(f"  skipped, no source can re-read them: {', '.join(result.skipped)}")
    if not result.drift:
        lines.append("no drift")
        return "\n".join(lines)
    lines.append(f"{len(result.drift)} disagreement(s):")
    lines += [
        f"  {d.contract_id}  {d.field}: registry says {d.registry_says!r}, "
        f"source says {d.source_says!r}"
        for d in result.drift
    ]
    return "\n".join(lines)


def land(result) -> str:
    return "\n".join(
        [f"landed on {result.branch} ({result.commit[:12]})", *(f"  {f}" for f in result.files)]
    )


def listing(names: list[str]) -> str:
    return "\n".join(names) or "(no drafts)"


def _holes(holes) -> list[str]:
    lines = []
    for hole in holes:
        lines.append(f"  {hole.field}")
        lines.append(f"      what: {hole.what}")
        lines.append(f"      why open: {hole.why_open}")
        if hole.candidates:
            lines.append(f"      one of: {', '.join(c.value for c in hole.candidates)}")
    return lines
