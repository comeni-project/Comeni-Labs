# comeni-core

The shared data model for [Comeni Labs](https://github.com/comeni-project/Comeni-Labs):
module contracts, closed type vocabularies, declared measurements, the pipeline IR, and
the layered registry.

**Pure by construction.** No web framework, no HTTP client, no model library — enforced by
a closed import allowlist in `tests/guards/test_purity.py` that covers the standard library and
dynamic imports as well as third-party names. Telemetry cannot live here, structurally
rather than by promise.

```python
from comeni_core import MeasurementRegistry, Registry, Vocabulary

measurements = MeasurementRegistry.load("registry")  # a layer root, not a slice of one
vocabulary = Vocabulary.load("registry").with_measurements(measurements)
measurements = measurements.with_grains(vocabulary.grains)  # a fact's scope is its type's grain
registry = Registry.load("registry", vocabulary)
```

`mendel_resolver.layers.load` does all of this, with the checks between the steps.

Load order matters — a measurement derives a `measurement.<id>` type that contracts are
validated against. Use `mendel_resolver.layers.load()` rather than assembling it by hand.

Documentation: [reference](../../docs/reference/) ·
[architecture](../../ARCHITECTURE.md). Licensed Apache-2.0.
