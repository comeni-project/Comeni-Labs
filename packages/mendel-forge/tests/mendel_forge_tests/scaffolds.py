"""Source bundles, fixtures and golden comparison for scaffold and prompt tests."""

import json

import pytest
from mendel_forge import bundle
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
from mendel_forge_tests.paths import FIXTURES as FORGE_FIXTURES
from mendel_resolver import layers
from support.paths import ROOT as REPOSITORY_ROOT

ROOT = REPOSITORY_ROOT


GOLDENS = FORGE_FIXTURES / "scaffolds"


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
