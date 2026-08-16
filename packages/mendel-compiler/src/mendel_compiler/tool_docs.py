"""One Markdown page per tool, rendered from declared data and nothing else.

**Pure.** Takes loaded layers, returns strings. `cli/layer_verbs.py` is the only thing that
touches disk, which is what makes these tests golden-file tests rather than filesystem tests —
the same split `cli/__init__.py` describes and for the same reason.

comeni-registry#2.
"""

from collections import defaultdict

from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.registry import Registry


def _tool_of(contract_id: str) -> str:
    """`nf-core/star/align@1.11.0` -> `nf-core/star`.

    The **module key** — the id minus `@version` — is what shadowing already keys on, so a
    version bump never splits a page in two.

    The first two segments, because the ids are **not uniformly shaped**: `nf-core/star/align`
    has three and `nf-core/fastqc` has two, so "drop the last segment" turns the second into
    `nf-core` and collapses every nf-core module onto one page. That was checked against the
    whole registry rather than reasoned about.

    Fewer than two segments returns the key itself rather than refusing. No contract has one
    today, and a laboratory's in-house `sortmerna@4.3.6` is not obviously wrong — inventing a
    rule for a case that does not exist is how a closed vocabulary comes to forbid something
    legitimate.
    """
    key = contract_id.split("@")[0]
    return "/".join(key.split("/")[:2])


def tools_of(registry: Registry) -> dict[str, list[ModuleContract]]:
    """Every contract in the stack, grouped into the page it belongs on.

    Sorted at both levels. A generated file that reorders itself between runs is a file whose
    `--check` fails for a reason nobody can act on, which is the same hazard `IREdge.states`
    carries a `field_serializer` for.
    """
    grouped: dict[str, list[ModuleContract]] = defaultdict(list)
    for contract_id in sorted(registry.contracts):
        grouped[_tool_of(contract_id)].append(registry.contracts[contract_id])
    return dict(sorted(grouped.items()))
