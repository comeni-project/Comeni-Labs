"""Reading and writing `pipeline.yml`, and the four checks that guard the pair of files.

`comeni_core.pipeline` owns what a `Pipeline` *is*; this owns what it looks like on disk and
what must be true of the directory around it. The split matters because `comeni-core` may not
know about `main.nf` — a `Pipeline` is a document, and only the compiler generates Nextflow
from one.
"""

from pathlib import Path

import yaml
from comeni_core import yaml_strict
from comeni_core.digest import digest_of_bytes
from comeni_core.egress import Emitted
from comeni_core.pipeline import Pipeline

FILENAME = "pipeline.yml"

EMITTED_FILES = ("main.nf", "nextflow.config")
"""What this compiler generates. Named once, because `publish` records their digests, `emit`
compares against that record and `upgrade` reports on it — three lists would be one drift away
from a verdict about a file nobody looked at."""

HEADER = """\
# This pipeline, in full. Read it; edit it; then rebuild the Nextflow from it:
#
#     mendel emit pipeline.yml --out .
#
# Every value carries a `why:` — the tier it exited at, who settled it, which registry layer
# it came from, and the citation behind it. That is the point of the file: one place that
# answers "what settings does this pipeline use, and why".
#
# `goal:` is INERT to `mendel emit`. It is the input to *resolution*, and the facts emission
# needs are already materialised into `channels[].meta`, so editing `profile:` or `want:`
# changes nothing until `mendel upgrade` re-resolves against a registry.
#
# `emitted.from_digest` is the digest of everything above it. Nextflow runs `main.nf`, not
# this file — that digest is what notices if you edit here and forget to re-emit.
"""


def dump(pipeline: Pipeline) -> str:
    """The bytes of the file.

    `sort_keys=False` keeps Pydantic's declaration order, which is the order a person should
    read these sections in — `version`, then what was asked for, then what it resolved to.
    Alphabetical would put `call` above `id` and scatter the answer. It is deterministic
    either way, which is what byte-identical emission needs.
    """
    body = yaml.safe_dump(
        pipeline.model_dump(mode="json"),
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=96,
    )
    return HEADER + "\n" + body


def load(path: Path) -> Pipeline:
    """Parse one, strictly.

    Through `yaml_strict` so a repeated key is refused rather than silently taking the last
    one (A31). This file is hand-edited by design, which makes it the likeliest place in the
    whole system for a key to appear twice.

    Every model-level code — `MD0207`, `MD0211`, `MD0212`, `MD0215` — fires here, because they
    are properties of the document rather than of the verb reading it.
    """
    return Pipeline.model_validate(yaml_strict.load(path))


def write(directory: Path, pipeline: Pipeline) -> Pipeline:
    """Write it, read it back, and hand back **the copy that was read**. `MD0206`.

    Emission then runs on the round trip rather than on the object in memory, so a field that
    does not survive YAML is a refused build instead of a file that quietly means less than it
    says. `ResolvedValue._drop_computed` exists because the IR did not round-trip at all and —
    in its own words — *"nothing noticed, because nothing read an IR back until now"*. This is
    what makes that impossible to repeat.
    """
    path = directory / FILENAME
    path.write_text(dump(pipeline))
    reparsed = load(path)
    if reparsed != pipeline:
        raise ValueError(
            f"MD0206: {path} does not parse back to what it was written from. The pipeline "
            f"directory is not trustworthy and nothing further was emitted. This is a bug in "
            f"Mendel rather than in your goal — `mendel explain MD0206`."
        )
    return reparsed


def stamp(directory: Path, pipeline: Pipeline) -> None:
    """Record what was written, and what it was written from.

    Last, and on the failing-gate path too: a directory holding generated files with no record
    of where they came from is exactly the divergence `MD0213` exists to catch.
    """
    pipeline.emitted = Emitted.of(
        directory, EMITTED_FILES, from_digest=pipeline.content_digest()
    )
    (directory / FILENAME).write_text(dump(pipeline))


def hand_edited(directory: Path, pipeline: Pipeline) -> list[str]:
    """Which generated files differ from what was recorded. `MD0214`.

    A file that is **absent** is not hand-edited — it is missing, and rewriting it destroys
    nothing. That is deliberate: it is the escape hatch `MD0214`'s fix names, and without it
    someone who hand-edited `main.nf` would have no way forward except editing the digest,
    which is teaching them to defeat the guard.
    """
    if pipeline.emitted is None:
        return []
    return sorted(
        record.name
        for record in pipeline.emitted.files
        if (directory / record.name).exists()
        and digest_of_bytes((directory / record.name).read_bytes()) != record.digest
    )


def is_stale(pipeline: Pipeline) -> bool:
    """Has the file changed since the Nextflow was generated from it? `MD0213`.

    `None` means no evidence — a build whose gate failed, or a file from before this field
    existed. It must never read as "identical", so it is not stale either; there is simply
    nothing to compare.
    """
    if pipeline.emitted is None or pipeline.emitted.from_digest is None:
        return False
    return pipeline.emitted.from_digest != pipeline.content_digest()
