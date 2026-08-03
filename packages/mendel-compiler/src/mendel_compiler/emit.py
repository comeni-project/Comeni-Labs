"""IR to Nextflow DSL2. Deterministic: same IR, byte-identical output."""

from pathlib import Path

from comeni_core.ir import PipelineIR
from comeni_core.registry import Registry
from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES = Path(__file__).parent / "templates"


def _render_literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return f"'{value}'"


def _calls(ir: PipelineIR, registry: Registry) -> list[str]:
    incoming: dict[str, list[str]] = {node.id: [] for node in ir.nodes}
    for edge in ir.edges:
        incoming[edge.to_node].append(
            f"{_process(ir, registry, edge.from_node)}.out.{edge.from_port}"
        )

    calls = []
    for node in ir.nodes:
        args = incoming[node.id] or ["ch_reads"]
        calls.append(f"{_process(ir, registry, node.id)}({', '.join(args)})")
    return calls


def _process(ir: PipelineIR, registry: Registry, node_id: str) -> str:
    node = next(n for n in ir.nodes if n.id == node_id)
    return registry.get(node.contract_id).nf_process


def emit(ir: PipelineIR, registry: Registry) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    nodes = [
        {
            "id": node.id,
            "process": registry.get(node.contract_id).nf_process,
            "include": registry.get(node.contract_id).nf_include,
            "params": [
                (
                    name,
                    type(
                        "V",
                        (),
                        {
                            "tier": value.tier,
                            "review_level": value.review_level,
                            "reason": value.reason,
                            "rendered": _render_literal(value.value),
                        },
                    )(),
                )
                for name, value in sorted(node.params.items())
            ],
        }
        for node in ir.nodes
    ]
    return env.get_template("main.nf.j2").render(nodes=nodes, calls=_calls(ir, registry))
