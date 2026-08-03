"""IR to Nextflow DSL2. Deterministic: same IR, byte-identical output."""

from pathlib import Path

from comeni_core.contract import ModuleContract, NfInput
from comeni_core.ir import PipelineIR
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES = Path(__file__).parent / "templates"

def _empty(width: int) -> str:
    """An empty tuple of the arity the process declares."""
    return "Channel.value([" + ", ".join(["[:]"] + ["[]"] * (width - 1)) + "])"


def _render_literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return f"'{value}'"


def _channel_name(type_id: str) -> str:
    """`fastq.reads` -> `ch_reads`. The last segment is what a reader recognises."""
    return f"ch_{type_id.rsplit('.', 1)[-1]}"


def _default_entry(type_id: str) -> str:
    param = type_id.rsplit(".", 1)[-1]
    return f"Channel.fromPath(params.{param}, checkIfExists: true).map {{ f -> [ [:], f ] }}"


def _contract(ir: PipelineIR, registry: Registry, node_id: str) -> ModuleContract:
    node = next(n for n in ir.nodes if n.id == node_id)
    return registry.get(node.contract_id)


def _process(ir: PipelineIR, registry: Registry, node_id: str) -> str:
    return _contract(ir, registry, node_id).nf_process


def _port_expression(ir: PipelineIR, registry: Registry, node_id: str, port_name: str) -> str:
    """Where this port's data comes from: an upstream process, or an entry channel."""
    for edge in ir.edges:
        if edge.to_node == node_id and edge.to_port == port_name:
            return f"{_process(ir, registry, edge.from_node)}.out.{edge.from_port}"
    contract = _contract(ir, registry, node_id)
    port = next(p for p in contract.consumes if p.name == port_name)
    return _channel_name(port.type_id)


def _argument(ir: PipelineIR, registry: Registry, node_id: str, spec: NfInput) -> str:
    if spec.empty:
        return _empty(spec.empty)
    if not spec.ports:
        return _render_literal(spec.literal)
    expressions = [_port_expression(ir, registry, node_id, name) for name in spec.ports]
    if len(expressions) == 1:
        return expressions[0]
    # Several semantic ports share one channel — featurecounts wants
    # tuple(meta, bams, annotation). Combine drops the second tuple's meta.
    head, *rest = expressions
    joined = "".join(f".combine({expr}.map {{ it[1] }})" for expr in rest)
    return f"{head}{joined}"


def _entry_channels(ir: PipelineIR, registry: Registry, vocab: Vocabulary) -> list[tuple[str, str]]:
    """Declarations for every type consumed but not produced inside the pipeline."""
    fed = {(edge.to_node, edge.to_port) for edge in ir.edges}
    needed: dict[str, str] = {}
    for node in ir.nodes:
        for port in registry.get(node.contract_id).consumes:
            if (node.id, port.name) in fed:
                continue
            needed[port.type_id] = vocab.entry_channels.get(
                port.type_id, _default_entry(port.type_id)
            )
    return [(_channel_name(type_id), needed[type_id]) for type_id in sorted(needed)]


def _calls(ir: PipelineIR, registry: Registry) -> list[str]:
    calls = []
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        args = [_argument(ir, registry, node.id, spec) for spec in contract.input_signature()]
        calls.append(f"{contract.nf_process}({', '.join(args)})")
    return calls


def emit(ir: PipelineIR, registry: Registry, vocab: Vocabulary | None = None) -> str:
    vocab = vocab or Vocabulary(types={})
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
                for name, value in sorted((b.name, b.value) for b in node.params)
            ],
        }
        for node in ir.nodes
    ]
    return env.get_template("main.nf.j2").render(
        nodes=nodes,
        entry_channels=_entry_channels(ir, registry, vocab),
        calls=_calls(ir, registry),
    )


def entry_params(ir: PipelineIR, registry: Registry, vocab: Vocabulary) -> list[str]:
    """The `params.<name>` a generated pipeline expects the laboratory to supply.

    Read out of the entry-channel expressions rather than hardcoded, so a type that
    declares its own entry channel automatically declares its own parameter.
    """
    import re

    found: set[str] = set()
    for _, expression in _entry_channels(ir, registry, vocab):
        found.update(re.findall(r"params\.(\w+)", expression))
    return sorted(found)


def emit_config(ir: PipelineIR, registry: Registry, vocab: Vocabulary) -> str:
    """`nextflow.config` for the generated pipeline.

    Every input parameter defaults to `null`: the pipeline describes a shape and the
    laboratory supplies the data at run time, which is invariant 15 surviving into the
    configuration as well as the workflow.

    The `stub_data` profile exists for the `-stub-run` gate and points at synthetic
    files the gate materialises. It is a validation harness, not a test profile — it
    proves the DAG executes, never that the analysis is right.
    """
    params = entry_params(ir, registry, vocab)
    lines = [
        "// Generated by Mendel. Do not edit by hand — edit the goal and recompile.",
        "",
        "params {",
    ]
    lines += [f"    {name} = null" for name in params]
    lines += ["}", "", "profiles {", "    stub_data {"]
    for name in params:
        pattern = (
            '"${projectDir}/stub-data/*_R{1,2}.fastq.gz"'
            if name == "input"
            else f'"${{projectDir}}/stub-data/{name}.txt"'
        )
        lines.append(f"        params.{name} = {pattern}")
    lines += [
        "    }",
        "    docker {",
        "        docker.enabled = true",
        "        // Without this, containers write as root and the work directory",
        "        // cannot be deleted by the person who created it.",
        "        docker.runOptions = '-u $(id -u):$(id -g)'",
        "    }",
        "    singularity {",
        "        singularity.enabled = true",
        "        singularity.autoMounts = true",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)
