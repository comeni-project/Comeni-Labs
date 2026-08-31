"""Put the module source a pipeline needs beside the artifact.

**Every `include` in the emitted workflow points at `./modules/<key>/main`**, so an artifact
with no `modules/` directory beside it is a pipeline that cannot run — which is what `MD0210`
refuses. Two callers write that directory: `mendel build`, and the API's `keep`. They used to
do it with two copies of `shutil.copytree(vendor/modules, out/modules)`, which is the shape a
bug hides in: `keep` did not have one at all until `MD0210` found it, and a kept draft that
cannot be emitted is not a pipeline whatever its header says.

**It copies what the pipeline includes, and not the layer.** The old `copytree` shipped all
thirteen vendored modules into every bundle including the three no contract references. A
laboratory receiving an artifact needs the code that runs, and nothing else — and the smaller
claim is also the checkable one: every include has a file, and every file has an include.
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
