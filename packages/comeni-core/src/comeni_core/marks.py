"""Type markers and closed value unions shared across the core.

These live apart from `ir.py`, `decision.py` and `egress.py` because all three need them
and any two of those importing each other would be a cycle. They are also the vocabulary
`tests/test_egress.py` reasons about, so keeping them in one small file makes the guard's
subject matter readable in one screen.

The distinction that matters:

- `FreeText` — text a human typed or a tool printed. Unbounded, and the thing the egress
  boundary exists to contain. Exactly the fields named in the guard's allowlist may carry it.
- `ParamLiteral` — a value that came from curated registry data: a contract default, a rule's
  `then`, or a resolver decision over those. It can be a string, but not an arbitrary one.

A bare `str` is neither, which is why the guard rejects it: a field with nothing said about
it is a field where anything fits.
"""

from typing import Annotated


class FreeText:
    """Marker: this field may hold text a human typed or a tool printed."""


class ParamLiteral:
    """Marker: a scalar drawn from curated registry data rather than from a person."""


Text = Annotated[str, FreeText]
ContractId = Annotated[str, "contract-id"]
TypeId = Annotated[str, "type-id"]
NodeId = Annotated[str, "node-id"]
Subject = Annotated[str, "subject"]
PortName = Annotated[str, "port-name"]
StateName = Annotated[str, "state-name"]
DecisionKey = Annotated[str, "decision-key"]
ResolverId = Annotated[str, "resolver-id"]

ParamValue = int | float | bool | Annotated[str, ParamLiteral] | None
"""What a resolved parameter or a decision may hold.

Replaces `Any`. Nextflow parameters are scalars — there is no shape a pipeline parameter
takes that this does not cover — and `Any` in a type reachable from an egress payload means
the payload can carry anything at all, which was true until 2026-08-03.
"""
