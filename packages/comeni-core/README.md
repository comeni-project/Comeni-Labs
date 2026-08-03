# comeni-core

The shared data model for [Comeni Labs](https://github.com/comeni-project/Comeni-Labs):
module contracts, closed type vocabularies, declared measurements, the pipeline IR, and
the layered registry.

**Pure by construction.** No web framework, no HTTP client, no model library — enforced by
a closed import allowlist in `tests/test_purity.py` that covers the standard library and
dynamic imports as well as third-party names. Telemetry cannot live here, structurally
rather than by promise.

```python
from comeni_core import MeasurementRegistry, Registry, Vocabulary

measurements = MeasurementRegistry.load("examples/measurements")
vocabulary = Vocabulary.load("examples/vocabularies").with_measurements(measurements)
registry = Registry.load("examples/contracts", vocabulary)
```

Load order matters — a measurement derives a `measurement.<id>` type that contracts are
validated against. Use `mendel_resolver.layers.load()` rather than assembling it by hand.

Documentation: [reference](../../docs/reference/) ·
[architecture](../../ARCHITECTURE.md). Licensed Apache-2.0.
