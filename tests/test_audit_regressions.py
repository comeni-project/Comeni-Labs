"""One test per finding in the 2026-08-06 audit, named for it.

Kept in one file rather than scattered into the suites they belong to, because the
question a reader has is "is A9 still closed?" and the answer should not require knowing
which module A9 was about. Each test carries the finding's one-line summary.

The audit is `docs/internal/audits/2026-08-06-plan-1-to-1.7-audit.md`; every finding
there records how it was reproduced, which is what these tests are the standing version of.
"""

import pytest
from pydantic import ValidationError

CONTRACT = {
    "id": "audit/x@1.0.0",
    "nf_process": "X",
    "nf_include": "./modules/x/main",
    "provenance": {
        "source": "audit",
        "drafted_by": "audit",
        "approved_by": "audit",
        "approved_at": "2026-08-06",
    },
}


def test_a13_a_profile_rejects_a_duplicate_measurement():
    """A13 — `get` was first-wins, so list order changed the pipeline."""
    from comeni_core.profile import DataProfile

    with pytest.raises(ValidationError, match="strandedness"):
        DataProfile.model_validate(
            {
                "measurements": [
                    {"measurement": "strandedness", "value": "reverse"},
                    {"measurement": "strandedness", "value": "unstranded"},
                ]
            }
        )


def test_a13_a_profile_sorts_so_the_same_facts_are_the_same_profile():
    """Order must not survive validation, or two equal profiles compare unequal."""
    from comeni_core.profile import DataProfile

    forward = DataProfile.model_validate(
        {"measurements": [{"measurement": "a", "value": 1}, {"measurement": "b", "value": 2}]}
    )
    backward = DataProfile.model_validate(
        {"measurements": [{"measurement": "b", "value": 2}, {"measurement": "a", "value": 1}]}
    )
    assert forward.model_dump_json() == backward.model_dump_json()


def test_a11_a_contract_rejects_a_duplicate_param_name():
    """A11 — two bindings of one name reached `sorted` and compared two ResolvedValues."""
    from comeni_core.contract import ModuleContract

    with pytest.raises(ValidationError, match="threads"):
        ModuleContract.model_validate(
            {
                **CONTRACT,
                "params": [{"name": "threads", "default": 4}, {"name": "threads", "default": 8}],
            }
        )


def test_a11_the_emitter_never_compares_two_resolved_values():
    """Belt and braces: the sort key is the name, so a tie cannot reach the value.

    Task 1 makes a tie unreachable by rejecting it at the contract. This asserts the
    emitter would survive one anyway, because the next unorderable field on
    `ResolvedValue` must not resurrect a crash that is already fixed.
    """
    from comeni_core.ir import IRNode, PipelineIR, ResolvedValue, Tier
    from mendel_compiler.emit import emit
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract = next(c for c in loaded.registry.all() if c.params)
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="r"),
    )
    name = contract.params[0].name
    node.set_param(name, ResolvedValue(value=1, tier=Tier.CONVENTION, reason="a"))
    node.set_param(name, ResolvedValue(value=2, tier=Tier.CONVENTION, reason="b"))

    # An IR is deserialised from a bundle, so a duplicate binding stays *representable*
    # even once a contract cannot declare one. It must not reach an unorderable compare.
    emit(PipelineIR(nodes=[node]), loaded.registry, loaded.vocabulary, loaded.measurements)
