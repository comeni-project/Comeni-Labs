"""The exact text that would be sent to a provider for one nf-core tool and one PEGiS tool.

**This is the golden that matters most in the prompt stack**, because a prompt is the one
product artifact nobody reviews by running it. A change to the dossier's ordering, to a hint
fragment, to a hole's phrasing or to the response schema is a change to what every model is
asked, and without this it would land as a behaviour nobody looked at — the exact failure mode
`test_scaffold_goldens.py` exists for, one layer up.

The two cases are the two the forge branches on. nf-core ships a process and a structured
`meta.yml`, so its dossier carries machine-readable evidence and asks nothing about Nextflow;
PEGiS ships a container and prose, so its dossier is where the model is trusted with the most.

Regenerate after reading the diff:

    uv run pytest packages/mendel-forge/tests/test_prompt_goldens.py --regenerate

**Read the diff properly.** A regenerated prompt golden is the moment to ask whether the change
makes the question clearer or merely different, and §5.9 requires a before/after evaluation
report for exactly that reason.
"""

import json
from pathlib import Path

import pytest
from mendel_forge import bundle, prompts
from mendel_forge.ai import select
from mendel_forge.ai.context import Budget
from mendel_resolver import layers

from .test_scaffold_goldens import ADAPTATION, REGISTRY_DIGEST, ROOT, _nfcore, _pegi3s

GOLDENS = Path(__file__).parent / "fixtures" / "prompts"
SCHEMA_VERSION = 6
BUDGET = Budget(tokens=32_000).characters()

VOCABULARIES = (
    select.vocabulary(
        name="roles",
        values=["align_reads", "count_features", "qc_per_sample", "sort_bam"],
        note="every role the registry already declares:",
    ),
    select.vocabulary(
        name="parameter-routes",
        values=["ext.args", "meta", "positional", "directive"],
        note="how a resolved value can reach a tool:",
    ),
)
"""Held here rather than read from the registry.

A golden that loaded the live vocabulary would churn on every registry bump, and the thing
under test is the *composition* — that a vocabulary is protected, ordered and rendered whole.
The registry's own contents are `test_ai_select.py`'s business and the live path's.
"""


@pytest.fixture(scope="module")
def stack():
    """The live registry, loaded once. A module-scoped fixture in another file is not shared,
    and importing one would tie two golden suites together for no benefit."""
    return layers.load(ROOT / "registry")


def _dossier(source, stack):
    built = bundle.derive(
        source, stack, adaptation_id=ADAPTATION, registry_digest=REGISTRY_DIGEST
    )
    return built, select.analysis_dossier(
        source=source,
        scaffold_holes=built.holes,
        registry_digest=REGISTRY_DIGEST,
        schema_version=SCHEMA_VERSION,
        vocabularies=VOCABULARIES,
        instruction="Answer every hole above, or say what evidence would close it.",
        budget=BUDGET,
    )


def _check(name: str, text: str, manifest: dict, regenerate: bool) -> None:
    golden = GOLDENS / f"{name}.txt"
    side = GOLDENS / f"{name}.manifest.json"
    payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if regenerate:
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(text)
        side.write_text(payload)
        pytest.skip(f"regenerated {golden.name} — read the diff before committing it")
    assert golden.exists(), f"{golden} is missing; run with --regenerate"
    assert golden.read_text() == text, (
        f"{golden.name} is not what the forge would send any more. Read the diff: this is the "
        "whole of what a model is asked, and a change here changes every adaptation."
    )
    assert json.loads(side.read_text()) == manifest


def test_the_nf_core_analysis_prompt_is_unchanged(stack, regenerate_goldens):
    _, dossier = _dossier(_nfcore(), stack)
    rendered = prompts.template(prompts.ANALYSIS).render({"dossier": dossier.render()})
    _check(
        "nfcore_fastqc.analysis",
        rendered.text,
        dossier.manifest.model_dump(mode="json"),
        regenerate_goldens,
    )


def test_the_pegi3s_analysis_prompt_is_unchanged(stack, regenerate_goldens):
    _, dossier = _dossier(_pegi3s(), stack)
    rendered = prompts.template(prompts.ANALYSIS).render({"dossier": dossier.render()})
    _check(
        "pegi3s_clustalw.analysis",
        rendered.text,
        dossier.manifest.model_dump(mode="json"),
        regenerate_goldens,
    )


def test_the_pegi3s_implementation_prompt_is_unchanged(stack, regenerate_goldens):
    """Only PEGiS gets one. §5.6 says an nf-core prompt may bind a contract to the existing
    process and must not emit replacement Nextflow, so there is no implementation prompt for a
    source that already wrote the module."""
    _, dossier = _dossier(_pegi3s(), stack)
    rendered = prompts.template(prompts.IMPLEMENTATION).render({"dossier": dossier.render()})
    _check(
        "pegi3s_clustalw.implementation",
        rendered.text,
        dossier.manifest.model_dump(mode="json"),
        regenerate_goldens,
    )


def test_neither_prompt_names_a_path_from_the_machine_that_built_it():
    """A golden carrying `/home/someone/` would be a golden that only passes on one laptop, and
    a prompt carrying it would put that machine's layout in front of a provider.

    `ScaffoldBundle` already refuses one in a *generated file*; this is the same claim about
    the composed prompt, which is assembled from several sources and validated by none of them.
    """
    for golden in sorted(GOLDENS.glob("*.txt")):
        text = golden.read_text()
        for prefix in ("/home/", "/Users/", "/root/", "/tmp/"):
            assert prefix not in text, f"{golden.name} names a host path: {prefix}"
    assert list(GOLDENS.glob("*.txt")), "no goldens were scanned, so this asserted nothing"


def test_the_manifest_beside_each_golden_records_what_was_left_out(stack):
    """The prompt says what the model saw; the manifest says what it was *not* shown, which is
    the half a reader cannot reconstruct from the text.

    Stored beside the golden rather than inside it because they are read for different reasons —
    the prompt is read to judge the question, the manifest to judge whether the question was
    asked with everything available.
    """
    _, dossier = _dossier(_nfcore(), stack)
    assert dossier.manifest.fits()
    assert dossier.manifest.prompt_digest.startswith("sha256:")


def test_a_prompt_is_byte_identical_across_two_builds(stack):
    """Two runs over the same source and the same registry produce the same bytes, which is
    what makes the golden a golden rather than a snapshot of one afternoon."""
    _, first = _dossier(_nfcore(), stack)
    _, second = _dossier(_nfcore(), stack)
    assert first.render() == second.render()
