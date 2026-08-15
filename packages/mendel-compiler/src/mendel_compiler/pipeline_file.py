"""Reading and writing `pipeline.yml`, and the four checks that guard the pair of files.

`comeni_core.artifact.pipeline` owns what a `Pipeline` *is*; this owns what it looks like on
disk and what must be true of the directory around it. The split matters because `comeni-core`
may not
know about `main.nf` — a `Pipeline` is a document, and only the compiler generates Nextflow
from one.
"""

from pathlib import Path

import yaml
from comeni_core import yaml_strict
from comeni_core.artifact.digest import digest_of_bytes
from comeni_core.artifact.egress import Emitted
from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline
from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import Tier

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
            coded("MD0206", f"{path} does not parse back to what it was written from. The pipeline "
            f"directory is not trustworthy and nothing further was emitted. This is a bug in "
            f"Mendel rather than in your goal — `mendel explain MD0206`.")
        )
    return reparsed


def stamp(directory: Path, pipeline: Pipeline, gate=None) -> Pipeline:
    """Record what was written, what it was written from, and which gate it passed.

    Last, and on the failing-gate path too: a directory holding generated files with no record
    of where they came from is exactly the divergence `MD0213` exists to catch.

    `model_copy` rather than assignment, because `Pipeline` is door 4's payload and therefore
    frozen — what was reviewed is what is sent. That is the right shape for these two fields
    anyway: both are evidence about a finished pipeline, and evidence should not be edited in
    place. The stamped copy is returned so a caller cannot keep using the unstamped one.

    `gate` is applied **before** the digest, because `from_digest` covers it. Recording the
    digest and then setting the verdict would make every gated build stale the moment its
    verdict arrived.
    """
    stamped = pipeline.model_copy(update={"gate": gate})
    stamped = stamped.model_copy(
        update={
            "emitted": Emitted.of(
                directory,
                EMITTED_FILES,
                from_digest=stamped.content_digest(),
                # The version the digest was taken under, so a later Mendel can tell its own
                # schema moving from a person editing the file. See `predates_schema`.
                schema_version=SCHEMA_VERSION,
            )
        }
    )
    (directory / FILENAME).write_text(dump(stamped))
    return stamped


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

    **A digest taken under an older schema is not evidence of an edit.** `from_digest` hashes
    the model dump, so adding one field to the artifact moves it for every pipeline ever
    archived, at once, with nobody touching one — which is what Plan 1.13's `CallArg.join`
    did. Reporting that as "you changed this file" sends a laboratory looking for an edit that
    does not exist, and the recovery it suggests is right for the wrong reason.

    `predates_schema` is the honest reading of that case, and it is deliberately *not*
    stale-ness: the generated files are unaffected and `files_changed` still checks them, so
    the real corruption this diagnostic exists for is still caught. Found while executing
    Plan 1.13; the fixture is `notes/audits/fixtures/pipeline-v1/`.
    """
    if pipeline.emitted is None or pipeline.emitted.from_digest is None:
        return False
    if predates_schema(pipeline):
        return False
    return pipeline.emitted.from_digest != pipeline.content_digest()


def stale_reasons(pipeline: Pipeline) -> list[str]:
    """Settings whose value moved and whose reason did not. `MD0223`.

    The file's own header says *"Read it; edit it"*, and `settings[].value` is what it points
    a person at. Editing one is therefore the ordinary case, not the suspicious one — and
    until this check existed the edit reached the tool while the justification beside it went
    on describing the value it replaced. `min_mqs` 0 → 30 emitted `-Q 30` under
    `reason: contract default for min_mqs`, and `publish` certified it at exit 0. Audit A104.

    A **diagnostic rather than a validator**, deliberately. Refusing at load would mean the
    file a reader is invited to edit cannot be edited; what is wanted is to be told to update
    the reason, in the same breath as being told the edit worked.

    Skipped where `for_value` is `None` — a file written before 1.14 has no such field, and
    absence is not disagreement.

    **Except for a tier-4 setting somebody answered, which is issue #48.** A value nothing
    resolved also has `for_value: null`, so by shape alone it is indistinguishable from a
    pre-1.14 field — and the one case where a human is most likely to be editing a value was
    the one case this could not see. Answering the question in the file left `why.reason`
    reading *"no rule covered … please review"* beside a value somebody had just chosen, and
    `emit` accepted it at exit 0.

    **Three conditions, and the third is what keeps this from being a nag.** No recorded
    value, tier 4, *and* a decision carrying a `human_override`. An **unanswered** tier-4
    setting is supposed to say "please review" and must not be flagged for doing so; a check
    that fires on correct output is a check people stop reading. Genuinely pre-1.14 files need
    no special case — they are `version: 1`, and `predates_schema()` suppresses the whole
    family for them.
    """
    answered = {
        decision.key for decision in pipeline.decisions if decision.human_override is not None
    }
    stale = []
    for step in pipeline.steps:
        for setting in step.settings:
            key = f"{step.id}.{setting.name}"
            if setting.why.for_value is not None:
                if setting.why.for_value != setting.value:
                    stale.append(
                        f"{key}: value is {setting.value!r}, but the reason beside it was "
                        f"written about {setting.why.for_value!r} — {setting.why.reason}"
                    )
            elif setting.why.tier is Tier.AMBIGUOUS and key in answered:
                stale.append(
                    f"{key}: a human answered this tier-4 question with {setting.value!r}, "
                    f"and the reason beside it is still the resolver's — "
                    f"{setting.why.reason!r}. Put your reasoning in the decision's "
                    f"`override_reason`, and make `why.reason` say the override answered it."
                )
    return stale


def predates_schema(pipeline: Pipeline) -> bool:
    """Was this file's digest taken under an older `SCHEMA_VERSION`?

    Only meaningful where there is a digest to have been taken. A file with no `emitted`
    record predates the record itself, which `upgrade` already reports in its own words.
    """
    if pipeline.emitted is None or pipeline.emitted.from_digest is None:
        return False
    return pipeline.emitted.schema_version < SCHEMA_VERSION
