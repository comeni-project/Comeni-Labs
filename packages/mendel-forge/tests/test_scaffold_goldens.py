"""What the forge authors for one nf-core tool and one PEGiS tool, frozen.

**The golden covers the deterministic half only** — what the forge *composed* — and the list of
source paths beside it. The source files themselves are upstream's bytes, already checked by
`test_an_nf_core_source_is_copied_unchanged_and_gets_no_generated_module`, and embedding a copy
of the vendored `main.nf` here would mean a registry bump churns a golden that is not about the
registry.

The two tools are chosen for the difference between them, which is the whole reason there are
two adapters: nf-core ships a process and a structured `meta.yml`, so the forge writes a
contract skeleton and no module. PEGiS ships a container and prose, so the forge writes a module
skeleton whose input, output and script are all marked open. A golden that only covered the
first would not notice the second breaking.

Regenerate with `--regenerate` after reading the diff:

    uv run pytest packages/mendel-forge/tests/test_scaffold_goldens.py --regenerate
"""

import json
from pathlib import Path

import pytest
from mendel_forge import bundle
from mendel_forge.bundle import Area, joined
from mendel_forge.catalogue import (
    BundleFact,
    BundleFile,
    CatalogueItem,
    ContainerRef,
    NumberedExcerpt,
    SourceBundle,
    SourceCapabilities,
)
from mendel_forge.observe import Excerpt
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
GOLDENS = Path(__file__).parent / "fixtures" / "scaffolds"

ADAPTATION = "0" * 32
REGISTRY_DIGEST = "r" * 64


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _nfcore() -> SourceBundle:
    module = ROOT / "registry" / "tools" / "nf-core" / "fastqc" / "module"
    return SourceBundle(
        item=CatalogueItem(
            id="1" * 64,
            source="nf-core",
            ref="fastqc",
            display_name="fastqc",
            summary="Run FastQC on sequenced reads",
            content_digest="2" * 64,
            latest_version="0.12.1",
            capabilities=SourceCapabilities(
                supplies_nextflow=True, supplies_structured_ports=True, supplies_tests=True
            ),
        ),
        source_digest="3" * 64,
        files=(
            BundleFile(path="main.nf", text=(module / "main.nf").read_text()),
            BundleFile(path="meta.yml", text=(module / "meta.yml").read_text()),
        ),
        facts=(
            BundleFact(name="nf_include", value="modules/nf-core/fastqc/main", evidence_id=None),
        ),
        evidence=(
            NumberedExcerpt(
                id="E001",
                excerpt=Excerpt(
                    locator="meta.yml:description", text="Run FastQC on sequenced reads"
                ),
                kind="metadata",
            ),
        ),
    )


def _pegi3s() -> SourceBundle:
    """A container with a README and no Nextflow — the case the whole marked-section change is
    for. `supplies_container_digest` is true and `supplies_nextflow` is false, which is exactly
    what PEGiS is: a better container pin than nf-core and no process at all."""
    return SourceBundle(
        item=CatalogueItem(
            id="4" * 64,
            source="pegi3s",
            ref="clustalw",
            display_name="clustalw",
            summary="Multiple sequence alignment",
            content_digest="5" * 64,
            latest_version="2.1",
            container_refs=(
                ContainerRef(
                    registry="docker.io",
                    repository="pegi3s/clustalw",
                    tag="2.1",
                    digest="sha256:" + "6" * 64,
                ),
            ),
            capabilities=SourceCapabilities(
                supplies_nextflow=False,
                supplies_structured_ports=False,
                supplies_container_digest=True,
                supplies_tests=True,
            ),
            input_hints=("fasta",),
            output_hints=("output.aln",),
        ),
        source_digest="7" * 64,
        files=(
            BundleFile(path="Dockerfile", text="FROM debian:11\nRUN apt-get install clustalw\n"),
            BundleFile(path="README.md", text="# clustalw\n\nMultiple sequence alignment.\n"),
        ),
        evidence=(
            NumberedExcerpt(
                id="E001",
                excerpt=Excerpt(locator="README.md:3", text="Multiple sequence alignment."),
            ),
        ),
    )


def _snapshot(built: bundle.ScaffoldBundle) -> dict:
    """What the golden holds: everything the forge authored, plus the shape of what it copied.

    `source_files` is reduced to its paths on purpose — see the module docstring. The digests
    are included because a scaffold that silently stopped recording what it was built from is
    the failure `MF0301` refuses on, one layer up.
    """
    return {
        "adaptation_id": built.adaptation_id,
        "source_digest": built.source_digest,
        "registry_digest": built.registry_digest,
        "module_digest": built.module_digest(),
        "source_paths": [path for path, _ in built.source_files],
        "holes": [hole.model_dump(mode="json") for hole in built.holes],
        "deterministic": {path: text for path, text in built.deterministic},
    }


def _check(name: str, built: bundle.ScaffoldBundle, regenerate: bool) -> None:
    golden = GOLDENS / f"{name}.json"
    payload = json.dumps(_snapshot(built), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if regenerate:
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(payload)
        pytest.skip(f"regenerated {golden.name} — read the diff before committing it")
    assert golden.exists(), f"{golden} is missing; run with --regenerate"
    assert json.loads(golden.read_text()) == json.loads(payload), (
        f"{golden.name} no longer matches what the forge produces. Read the diff: a change here "
        "is a change to every scaffold, and the whole point of a golden is that it is reviewed "
        "rather than absorbed."
    )


def test_the_nf_core_scaffold_is_unchanged(stack, regenerate_goldens):
    _check("nfcore_fastqc", bundle.derive(
        _nfcore(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    ), regenerate_goldens)


def test_the_pegi3s_scaffold_is_unchanged(stack, regenerate_goldens):
    _check("pegi3s_clustalw", bundle.derive(
        _pegi3s(), stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    ), regenerate_goldens)


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
