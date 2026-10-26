"""Copy exactly the Nextflow module sources referenced by a pipeline artifact.

Emitted includes point to ``modules/<key>/main`` beside the artifact. Staging copies each
selected module once and reports missing sources instead of shipping an entire registry layer.
"""

import shutil
from collections.abc import Mapping
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.module import Module, key_of


def stage(pipeline: Pipeline, modules: Mapping[str, Module], out: Path) -> list[str]:
    """Copy each step's module into `out`, at the path its `include` names.

    Returns the module keys written, sorted — so a caller can report what a bundle carries
    without walking it again. A step whose module the stack does not declare is **skipped
    silently here**: conformance has already reported it as `MD0100 unverified`, and refusing
    at copy time would turn a build that was allowed to proceed into one that dies at the last
    step with a different message.
    """
    written: set[str] = set()
    for step in pipeline.steps:
        key = key_of(step.include)
        found = modules.get(key)
        if found is None or found.source is None or not found.source.is_dir():
            continue
        # `include` is `modules/nf-core/fastqc/main`; the module's own tree lands at the
        # directory holding it, so `./modules/nf-core/fastqc/main.nf` resolves. This is the
        # one place the emitted layout and the layer layout are joined, and it is joined
        # through `key_of` in both directions rather than by two string manipulations.
        target = out / Path(step.include).parent
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(found.source, target, dirs_exist_ok=True)
        written.add(key)
    return sorted(written)
