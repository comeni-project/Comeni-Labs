# mendel-resolver

The four-tier resolution ladder for
[Comeni Labs](https://github.com/comeni-project/Comeni-Labs): a backward-chaining router,
validated tier-3 decision tables, and the ports where AI plugs in.

Every module choice and every parameter exits at exactly one tier — structural,
convention, data-profiled, or ambiguous — and carries it forever. A tier-3 miss demotes to
tier 4 and never reaches for a model.

```python
from mendel_resolver import Goal, GoalInput, layers, resolve

loaded = layers.load("examples")
goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
ir = resolve(goal, loaded.registry, loaded.rules)

print(ir.needs_review())
```

**Pure by construction** — see [`comeni-core`](../comeni-core/). AI implementations satisfy
the `Protocol`s in `mendel_resolver.ports`; the dependency arrow points at this package,
never out of it.

Documentation: [tiers](../../docs/concepts/tiers.md) ·
[routing](../../docs/concepts/routing.md) ·
[rule schema](../../docs/reference/rule-schema.md). Licensed Apache-2.0.
