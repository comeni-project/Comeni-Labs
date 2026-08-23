"""`validate(graph, layers) -> Verdict` — the inverse of `resolve`.

**`resolve()` searches; this checks.** Both read the same declared facts in opposite directions:
the resolver is handed a goal and asked to find edges, and this is handed edges and asked whether
they hold. Nothing new is declared — see the spec's §2 table.

**It reports; it never raises.** The router raises `UnroutableError` because it has failed to
build something and has nothing to hand back. Here there is something: a graph with three
problems in it, and a person mid-gesture who would rather see all three.

**Pure, and that is load-bearing.** A check living in the browser would be a check the agent
driving the API cannot run, and then there are two answers to *is this legal*. The compatibility
index in `compatibility.py` is an optimisation *of this verb's answer*, never a second opinion.
"""

from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftEdge, DraftGraph
from comeni_core.review.verdict import Finding, Level, Verdict

from mendel_resolver.layers import Layers

__all__ = ["validate"]


def validate(graph: DraftGraph, layers: Layers) -> Verdict:
    findings: list[Finding] = []
    contracts = _contracts(graph, layers, findings)
    for edge in graph.edges:
        findings.extend(_check_edge(edge, contracts))
    return Verdict(findings=findings)


def _contracts(
    graph: DraftGraph, layers: Layers, findings: list[Finding]
) -> dict[str, ModuleContract]:
    """Node id to contract, skipping nodes whose contract is not in the stack.

    A node naming an unknown contract is reported once as `MD0509`, rather than once per edge
    that touches it — a renamed contract would otherwise print the same failure four times.
    `MD0501` is the *port* failure and stays distinct, because the fixes differ.
    """
    resolved: dict[str, ModuleContract] = {}
    for node in graph.nodes:
        try:
            resolved[node.id] = layers.registry.get(node.contract_id)
        except (KeyError, ValueError):
            # `Registry.get` raises a bare `KeyError(contract_id)`, so interpolating it would
            # repeat the id and explain nothing. The sentence carries the explanation.
            findings.append(
                Finding(
                    code="MD0509",
                    level=Level.ILLEGAL,
                    message=coded(
                        "MD0509",
                        f"node {node.id!r} names {node.contract_id!r}, which is not in this "
                        f"registry stack",
                    ),
                    node=node.id,
                )
            )
    return resolved


def _output(contract: ModuleContract, name: str) -> OutputPort | None:
    return next((p for p in contract.produces if p.name == name), None)


def _input(contract: ModuleContract, name: str) -> InputPort | None:
    return next((p for p in contract.consumes if p.name == name), None)


def _check_edge(edge: DraftEdge, contracts: dict[str, ModuleContract]) -> list[Finding]:
    source = contracts.get(edge.from_node)
    target = contracts.get(edge.to_node)
    if source is None or target is None:
        return []  # already reported by `_contracts`

    out = _output(source, edge.from_port)
    inp = _input(target, edge.to_port)

    # Direction before existence-of-the-right-kind: `samtools/sort` has a `bam` on BOTH sides,
    # so a backwards wire names two ports that both exist and is not a typo.
    if out is None and _input(source, edge.from_port) is not None:
        return [
            _f(
                code="MD0502",
                level=Level.ILLEGAL,
                edge=edge,
                message=f"{edge.from_node}.{edge.from_port} is an input; "
                f"a wire starts at an output",
            )
        ]
    if inp is None and _output(target, edge.to_port) is not None:
        return [
            _f(
                code="MD0502",
                level=Level.ILLEGAL,
                edge=edge,
                message=f"{edge.to_node}.{edge.to_port} is an output; a wire ends at an input",
            )
        ]
    if out is None:
        return [
            _f(
                code="MD0501",
                level=Level.ILLEGAL,
                edge=edge,
                message=f"{source.id} has no output port {edge.from_port!r}; it produces "
                f"{sorted(p.name for p in source.produces)}",
            )
        ]
    if inp is None:
        return [
            _f(
                code="MD0501",
                level=Level.ILLEGAL,
                edge=edge,
                message=f"{target.id} has no input port {edge.to_port!r}; it consumes "
                f"{sorted(p.name for p in target.consumes)}",
            )
        ]

    return _check_types(edge, out, inp)


def _check_types(edge: DraftEdge, out: OutputPort, inp: InputPort) -> list[Finding]:
    """`alternatives()` is the author's own preference order and is not re-derived here.

    Index 0 is the conventional form — `state_required | state_required_conventional`; the
    fallback, where one exists, is `state_required` alone. Matching only the fallback is legal
    and unconventional, which is the `advisory` level.
    """
    alternatives = inp.alternatives()
    for position, alternative in enumerate(alternatives):
        if alternative.type_id != out.type_id:
            continue
        if not alternative.states <= out.state:
            continue
        if position == 0:
            return _preference(edge, out, inp)
        return [
            _f(
                code="MD0507",
                level=Level.ADVISORY,
                edge=edge,
                message=f"{edge.to_node}.{edge.to_port} conventionally wants "
                f"{sorted(alternatives[0].states)}; this source carries {sorted(out.state)}",
            )
        ] + _preference(edge, out, inp)

    # Nothing matched. Which half failed decides the code, because the fixes differ.
    if any(a.type_id == out.type_id for a in alternatives):
        wanted = next(a for a in alternatives if a.type_id == out.type_id)
        return [
            _f(
                code="MD0504",
                level=Level.ILLEGAL,
                edge=edge,
                message=f"{edge.to_node}.{edge.to_port} requires {sorted(wanted.states)}; "
                f"{edge.from_node}.{edge.from_port} carries {sorted(out.state)}",
            )
        ]
    takes = " or ".join(sorted({a.type_id for a in alternatives}))
    return [
        _f(
            code="MD0503",
            level=Level.ILLEGAL,
            edge=edge,
            message=f"{edge.to_node}.{edge.to_port} takes {takes}; "
            f"{edge.from_node}.{edge.from_port} emits {out.type_id}",
        )
    ]


def _preference(edge: DraftEdge, out: OutputPort, inp: InputPort) -> list[Finding]:
    """`prefer` is a preference between SOURCES, not between kinds of input.

    That is why it sits outside `alternatives()`: an alternative says *what shape of thing*,
    and this says *which of two legal things we would rather have*.
    """
    missing = inp.prefer - out.state
    if not missing:
        return []
    return [
        _f(
            code="MD0507",
            level=Level.ADVISORY,
            edge=edge,
            message=f"{edge.to_node}.{edge.to_port} prefers {sorted(missing)}, which this source "
            f"does not carry",
        )
    ]


def _f(*, code: str, level: Level, edge: DraftEdge, message: str) -> Finding:
    """Keyword-only, and the codes at every call site are literals — both deliberate.

    `tests/test_diagnostics_ownership.py` scans source for `coded("MD0001"` or `code="MD0001"`
    and knows no third shape. A helper taking the code positionally is invisible to it, so a
    code could be emitted while the guard reported it dead. Found by running the guard.

    `<node>.<port>` on each end — the spelling `SourceDecision.chosen` already uses, so a
    finding and a decision name an endpoint the same way."""
    return Finding(
        code=code,
        level=level,
        message=coded(code, message),
        source=f"{edge.from_node}.{edge.from_port}",
        target=f"{edge.to_node}.{edge.to_port}",
    )
