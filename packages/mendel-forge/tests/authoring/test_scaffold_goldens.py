"""Deterministic scaffold output for nf-core and PEGiS source bundles."""

import json

from mendel_forge import bundle
from mendel_forge.bundle import Area, joined
from mendel_forge_tests.scaffolds import (
    ADAPTATION,
    REGISTRY_DIGEST,
    _check,
    _nfcore,
    _pegi3s,
)
from mendel_forge_tests.scaffolds import stack as stack


def test_the_nf_core_scaffold_is_unchanged(stack, regenerate_goldens):
    _check(
        "nfcore_fastqc",
        bundle.derive(_nfcore(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST),
        regenerate_goldens,
    )


def test_the_pegi3s_scaffold_is_unchanged(stack, regenerate_goldens):
    _check(
        "pegi3s_clustalw",
        bundle.derive(_pegi3s(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST),
        regenerate_goldens,
    )


def test_the_pegi3s_scaffold_carries_a_module_and_the_nf_core_one_does_not(stack):
    """The difference the two goldens exist to hold. nf-core wrote the process, so nothing
    downstream may author one; PEGiS wrote none, so the forge writes a skeleton and marks every
    part of it that is a placeholder."""
    generated = joined(ADAPTATION, Area.SCAFFOLD, "module", "main.nf")

    from_nfcore = bundle.derive(
        _nfcore(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    )
    from_pegi3s = bundle.derive(
        _pegi3s(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    )

    assert generated not in dict(from_nfcore.files())
    module = dict(from_pegi3s.files())[generated]
    assert "MF0011" in module and "MF0005" in module
    assert "sha256:" in module, "the digest PEGiS pins must reach the module it generates"


def test_a_pegi3s_scaffold_asks_for_the_process_name_it_had_to_invent(stack):
    """`_process_name` names the placeholder `CLUSTALW`, and the scaffold still opens the hole.

    **A default is not an answer**, and this is where that distinction is enforced rather than
    asserted: the module has to be called something before anybody decides, and the decision is
    still owed. A scaffold that settled `nf_process` from the ref would be inventing a fact and
    recording it as derived.
    """
    built = bundle.derive(
        _pegi3s(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    )
    assert "nf_process" in [hole.id for hole in built.holes]
    module = dict(built.files())[joined(ADAPTATION, Area.SCAFFOLD, "module", "main.nf")]
    assert "process CLUSTALW {" in module


def test_a_pinned_digest_settles_the_container_rather_than_opening_a_hole(stack):
    """**PEGiS's one advantage, kept.** nf-core pins a container by *tag*, which is mutable —
    the image `pegi3s/clustalw:2.1` names today can be replaced tomorrow. PEGiS publishes
    digests, fetched from a registry API.

    Leaving `container` open here opened a hole over the single fact PEGiS actually proves, and
    asked a human to retype a 64-character digest. Found by printing a real scaffold; the golden
    now holds it.
    """
    built = bundle.derive(
        _pegi3s(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    )
    settled = json.loads(
        dict(built.files())[joined(ADAPTATION, Area.SCAFFOLD, "contract.yml.json")]
    )["settled"]
    assert settled["container"].endswith("@sha256:" + "6" * 64)
    assert "container" not in [hole.id for hole in built.holes]
