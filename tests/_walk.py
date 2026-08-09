"""Annotation walkers, shared by the egress guard and the pipeline totality test.

**Extracted rather than duplicated.** `nested_models` is why `tests/test_egress.py` can see
inside `RepairRequest.ir` at all — its first version returned only `EgressPayload` subclasses,
and every check walked `typing.get_args`, which returns `()` at a nested `BaseModel`. So nothing
ever looked inside a nested model, and a payload serialised a patient path and an SSN while that
file reported green.

Two copies of that logic, drifting, is the same defect waiting to happen a second time. A
totality test written "in the same shape as" the egress guard is exactly the instruction that
produces a subtly different walker.
"""

import typing

from pydantic import BaseModel


def nested_models(annotation: object) -> list[type[BaseModel]]:
    """Every BaseModel mentioned anywhere in an annotation, however deeply wrapped."""
    found = []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.append(annotation)
    for arg in typing.get_args(annotation):
        found += nested_models(arg)
    return found


def reachable(*roots: type[BaseModel]) -> set[type[BaseModel]]:
    """Transitive closure over model fields, breadth-first.

    Exempting nested models would be the hole — see the module docstring.
    """
    seen: set[type[BaseModel]] = set()
    queue = list(roots)
    while queue:
        model = queue.pop()
        if model in seen:
            continue
        seen.add(model)
        for annotation in typing.get_type_hints(model, include_extras=True).values():
            queue += [n for n in nested_models(annotation) if n not in seen]
    return seen
