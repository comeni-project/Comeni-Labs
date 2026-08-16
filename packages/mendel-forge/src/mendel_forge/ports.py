"""The Phase 2 seam, built now and left empty.

`HoleFiller` is the only place a model may enter the forge. Phase 1 ships `NoFiller`,
which declines everything, and **`--no-ai` is therefore not a flag — it is the only
mode.** That is honest by construction rather than by discipline: there is nothing to
switch off, so there is nothing to leave accidentally on.

**A filler returns the same `FilledValue` a human's `forge fill` produces**, differing
only in `filler` and `by`. `land` copies `by` verbatim into `Provenance.drafted_by`, a
field every contract has carried since the first one — so wiring a model needs no change
to the artifact's provenance design at all.

**`None` must stay legal.** A filler that always answers is a filler that invents, and a
hole a model declines is a hole a human still sees.

Before implementing this in Phase 2, read §10.3 of the spec: a forge model call is a
fifth egress door, and invariant 14 says there are four.
"""

from typing import Protocol

from mendel_forge.observe import Observation
from mendel_forge.scaffold import FilledValue, Hole


class HoleFiller(Protocol):
    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None: ...


class NoFiller:
    """Phase 1's only implementation."""

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        return None
