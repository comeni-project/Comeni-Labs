"""A tool's test as a small pipeline, built with the compiler (forge MVP 4, spec §4).

**Not through routing.** The test is of this tool, so the rules must not choose another: the IR is
made directly, one node per setup step and one for the tool, and from there on it is the same
`Pipeline.of`, `emit` and `emit_config` a built pipeline goes through.
"""

from collections.abc import Iterable
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.module import key_of
from comeni_core.declared.tooltest import ToolTest
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal, GoalInput
from comeni_core.plan.ir import (
    IRChannel,
    IREdge,
    IRNode,
    ParamBinding,
    PipelineIR,
    ResolvedValue,
)
from comeni_core.plan.tiers import Scope, Tier
from mendel_compiler import locate
from mendel_resolver.layers import Layers

TESTDATA_BASE = "https://raw.githubusercontent.com/nf-core/test-datasets/{commit}/data/"
TOOL = "tool"
_BECAUSE = "a forge test of this tool"


def _exact(value: object = None) -> ResolvedValue:
    return ResolvedValue(value=value, tier=Tier.STRUCTURAL, reason=_BECAUSE)


def _node(node_id: str, contract: ModuleContract, given: dict) -> IRNode:
    node = IRNode(id=node_id, contract_id=contract.id, selection=_exact(contract.id),
                  presence=_exact())
    node.params = [ParamBinding(name=p.name, value=_exact(_setting(contract, p, given)))
                   for p in contract.params]
    return node


def _setting(contract: ModuleContract, param, given: dict) -> object:
    if param.name in given:
        return given[param.name]
    if param.default is None and param.tier_hint == Tier.AMBIGUOUS:
        raise ValueError(coded("MF0515", f"{contract.id} needs a value for {param.name}, and "
                               "the test gives none"))
    return param.default


def _steps(test: ToolTest, stack: Layers) -> list[tuple[str, ModuleContract, dict]]:
    setups = [(f"setup_{n}", stack.registry.get(step.tool), {})
              for n, step in enumerate(test.setup, 1)]
    return [*setups, (TOOL, stack.registry.get(test.contract), test.params)]


def build_test_pipeline(test: ToolTest, stack: Layers) -> Pipeline:
    """The test as a pipeline. `ValueError` with its code when it cannot be one."""
    steps = _steps(test, stack)
    tool = stack.registry.get(test.contract)
    edges = _edges(test, steps, tool)
    fed = {(e.to_node, e.to_port) for e in edges}
    channels = [
        IRChannel(name=f"{node}_{port.name}", type_id=port.type_id, ports=[f"{node}.{port.name}"])
        for node, contract, _ in steps for port in contract.consumes
        if (node, port.name) not in fed
    ]
    ir = PipelineIR(nodes=[_node(node, contract, given) for node, contract, given in steps],
                    edges=edges, channels=channels, registry_layers=[])
    goal = Goal(have=[GoalInput(type_id=c.type_id, name=c.name) for c in channels],
                want=sorted({p.type_id for p in tool.produces}))
    return Pipeline.of(ir, stack.registry, stack.vocabulary, stack.measurements, stack.paths,
                       goal=goal, locators=locate.locators(stack.paths))


def _edges(test: ToolTest, steps: list, tool: ModuleContract) -> list[IREdge]:
    edges: list[IREdge] = []
    for (node, contract, _), step in zip(steps, test.setup, strict=False):
        makes = {p.name: p for p in contract.produces}
        takes = {p.name: p for p in tool.consumes}
        for output, port in step.feeds.items():
            if output not in makes or port not in takes:
                raise ValueError(coded("MF0515", f"setup {step.tool} feeds {output} → {port}: "
                                       "one of those ports does not exist"))
            edges.append(IREdge(from_node=node, from_port=output, to_node=TOOL, to_port=port,
                                type_id=takes[port].type_id))
    return edges


def params_for(test: ToolTest, pipeline: Pipeline) -> dict[str, str | list[str] | list[dict]]:
    """What the run must be given: exactly the pipeline's holes, as pinned public URLs."""
    urls = {f"{TOOL}_{port}": paths for port, paths in test.inputs.items()}
    for n, step in enumerate(test.setup, 1):
        urls |= {f"setup_{n}_{port}": paths for port, paths in step.inputs.items()}
    base = TESTDATA_BASE.format(commit=test.data_commit)
    params: dict = {}
    row = {"sample": "test"}
    for channel in pipeline.channels:
        files = [base + path for path in urls.get(channel.name, [])]
        if not files:
            raise ValueError(coded("MF0515", f"nothing feeds {channel.name}"))
        if channel.scope is Scope.SAMPLE and len(_per_sample(pipeline)) > 1:
            row |= dict(zip(channel.columns, files, strict=False))
        else:
            params[channel.param] = files[0] if len(files) == 1 else files
    if len(row) > 1:
        params["input"] = [row]
    return params


def _per_sample(pipeline: Pipeline) -> list[str]:
    return [c.name for c in pipeline.channels if c.scope is Scope.SAMPLE]


def module_files(pipeline: Pipeline, stack: Layers) -> Iterable[tuple[str, Path]]:
    """Each step's module source, as (path in the bundle, file on disk)."""
    for key in sorted({key_of(step.include) for step in pipeline.steps}):
        source = stack.modules[key].at / "module"
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            yield f"modules/{key}/{path.relative_to(source)}", path
