"""A contract may say in one line what its step does: context for the builder agent (#463)."""

import pytest
from comeni_core.declared.contract import ModuleContract
from pydantic import ValidationError

BASE = {
    "id": "nf-core/samtools/faidx@1.24",
    "nf_process": "SAMTOOLS_FAIDX",
    "nf_include": "modules/nf-core/samtools/faidx/main",
    "provenance": {"source": "hand", "drafted_by": "hand", "approved_by": "r",
                   "approved_at": "2026-11-14"},
}


def test_a_contract_may_say_what_this_step_does():
    said = "Index a FASTA reference so tools can read regions of it"
    contract = ModuleContract.model_validate({**BASE, "does": said})
    assert contract.does == said


def test_a_contract_without_does_has_none_and_writes_none():
    contract = ModuleContract.model_validate(BASE)
    assert contract.does is None
    assert "does" not in contract.model_dump(mode="json", exclude_none=True)


def test_does_is_one_line():
    with pytest.raises(ValidationError):
        ModuleContract.model_validate({**BASE, "does": "Index a reference.\nAnd more."})
