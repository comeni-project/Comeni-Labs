"""Build, edit and read saved-pipeline examples for artifact integration tests.

Helpers use the compiler CLI and temporary output directories. Archived examples remain
committed fixtures so compatibility tests do not manufacture their own expected format.
"""

import pathlib

import yaml
from comeni_core.artifact.pipeline import Pipeline, Why
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_compiler.cli import main

from support.audit import _declared
from support.paths import ROOT

GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _build(tmp_path, name="p"):
    out = tmp_path / name
    assert main(["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    return out


def _emit(out, capsys, path=None):
    """`mendel emit`, with stderr. Returns `(code, stderr)`."""
    code = main(["emit", str(path or out / "pipeline.yml"), "--out", str(out)])
    return code, capsys.readouterr().err


def _load(out) -> Pipeline:
    return Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))


ARCHIVED = ROOT / "tests" / "fixtures" / "pipeline-v1" / "pipeline.yml"
"""A pipeline written before Plan 1.13, committed rather than built.

A fixture produced by the code under test cannot demonstrate anything about reading what a
laboratory archived — see the README beside it.
"""


def _build_measured(
    tmp_path,
    name="measured",
    source="source: measured, by: comeni/profile-fastqc@0.1.0",
    paired="source: goal",
):
    """The same goal, with `read_length` recorded as **measured** rather than asserted.

    The mapping shorthand a goal file usually uses defaults every entry to `source: goal`, so
    the explicit list form is the only way to write a profile a tool produced. That asymmetry
    is deliberate: a hand-written goal *is* an assertion, and the shorthand is the honest
    spelling of one.
    """
    goal = tmp_path / "measured-goal.yml"
    goal.write_text(
        _declared(
            goal,
            "have:\n"
            "  - type_id: fastq.reads\n"
            "  - type_id: annotation.gtf\n"
            "  - type_id: genome.fasta\n"
            "want: [counts.matrix]\n"
            "constraints:\n"
            "  required_states:\n"
            "    counts.matrix: [gene_level]\n"
            "profile:\n"
            "  measurements:\n"
            f"    - {{measurement: read_length, value: 150, {source}}}\n"
            "    - {measurement: strandedness, value: reverse, source: goal}\n"
            "    - {measurement: n_samples, value: 12, source: goal}\n"
            f"    - {{measurement: paired, value: true, {paired}}}\n",
        )
    )
    out = tmp_path / name
    assert main(["build", "--goal", str(goal), "--out", str(out), "--root", str(ROOT)]) == 0
    return out


def _answer(out, name, value):
    """Edit one setting's `value:`, the way a person would.

    Text, not a model round trip: the guards exist for the file as somebody types it, and
    rewriting it through Pydantic would launder exactly the mistakes they are watching for.
    """
    path = out / "pipeline.yml"
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    assert lines[at + 1].strip() == "value: null", lines[at + 1]
    lines[at + 1] = lines[at + 1].replace("value: null", f"value: {value}")
    path.write_text(_declared(path, "".join(lines)))


# --- A38: via: meta and via: directive are declared routes; they must emit ---
def _overlay_with(tmp_path, extra_params: str) -> pathlib.Path:
    """A registry overlay adding params to subread/featurecounts. Shared by A38–A42 tasks."""
    ov = tmp_path / "ov"
    ov.mkdir(parents=True)
    (ov / "registry.yml").write_text(_declared(ov / "registry.yml", "name: lab\n"))
    src = (ROOT / "registry/tools/nf-core/subread/featurecounts/contract.yml").read_text()
    src = src.replace("params:", "params:\n" + extra_params, 1)
    (ov / "tools/nf-core/subread/featurecounts").mkdir(parents=True, exist_ok=True)
    (ov / "tools/nf-core/subread/featurecounts/contract.yml").write_text(
        _declared(ov / "tools/nf-core/subread/featurecounts/contract.yml", src)
    )
    return ov


def _build_with_overlay(tmp_path, ov) -> pathlib.Path:
    out = tmp_path / "b"
    assert (
        main(
            [
                "build",
                "--goal",
                str(GOAL),
                "--registry",
                str(ROOT / "registry"),
                "--registry",
                str(ov),
                "--out",
                str(out),
                "--root",
                str(ROOT),
            ]
        )
        == 0
    )
    return out


# --- A51: displacements of all four kinds reach the artifact, not just contracts+measurements ---
def _displaced_kinds(out) -> list[str]:
    reg = yaml.safe_load((out / "pipeline.yml").read_text())["registry"]
    return [d["kind"] for d in reg.get("displaced") or []]


def _why() -> Why:
    return Why(tier=Tier.AMBIGUOUS, source=ValueSource.HUMAN, reason="a round-four probe")


# --- Plan 1.14 Task 0: a schema change must announce itself -------------------------------
SERIALISED_SHAPE = {
    "Pipeline": [
        "version",
        "goal",
        "registry",
        "ai",
        "steps",
        "channels",
        "decisions",
        "emitted",
        "gate",
        "input_form",
    ],
    "Step": [
        "id",
        "module",
        "process",
        "include",
        "why",
        "presence",
        "ext_args",
        "inputs",
        "call",
        "settings",
    ],
    "ExtArgs": ["template", "why"],
    "Setting": ["name", "value", "via", "key", "template", "why"],
    "Why": [
        "tier",
        "source",
        "reason",
        "premise",
        "for_value",
        "axis_reason",
        "from_layer",
        "displaced_layer",
    ],
    "CallArg": ["ports", "literal", "empty_width", "from_setting", "join", "why"],
    "MetaEntry": ["key", "value", "why"],
    "Emitted": ["schema_version", "files", "from_digest"],
    "ParamDecision": [
        "key",
        "subject",
        "reason",
        "confidence",
        "resolved_by",
        "tier",
        "model_override_by",
        "kind",
        "candidates",
        "chosen",
        "model_override",
        "human_override",
        "override_reason",
    ],
    # Watched since issue 233 added what measured a premise; the goal's `Measured` and
    # `Evidence` gained theirs in 14.7.6.3 within the same unreleased version.
    "PremiseRecord": ["id", "value", "origin", "by", "pieces"],
    "Measured": ["measurement", "value", "source", "by", "pieces", "evidence"],
    "Evidence": ["records", "rows", "share"],
}
"""The artifact's serialised field order, as of `SCHEMA_VERSION = 6`.

**This is a fingerprint, not a specification.** It exists to fail when somebody adds a field
without bumping the version — which is exactly what happened in Plan 1.13 and is why Task 0
exists. `emitted.from_digest` hashes the model dump, so *any* addition moves the digest of
every pipeline ever archived, at once, with nobody having touched one. The version is what
lets `MD0213` tell that apart from a human edit, and a version nobody remembers to bump
cannot.

When this test fails: add your field here, and make sure `SCHEMA_VERSION` is ahead of
`RELEASED_SCHEMA_VERSION`. Within one unreleased bump that is already true and the fingerprint
is all that changes — version 2 covers every field Plan 1.14 adds. What must never happen is
the shape moving while the version stays at what a laboratory already has on disk.
"""


RELEASED_SCHEMA_VERSION = 1
"""The highest version any archived pipeline can be carrying. Raised when a version ships."""


# --- Plan 1.14 Task 1: a reason cannot outlive its value (A104, A105) ---------------------
def _edit_setting_value(out, name, value):
    """Change a resolved setting's `value:` by hand, the way the file's own header invites.

    Text rather than a model round trip, for the same reason `_answer` is: the guard exists
    for the file as somebody types it, and rewriting through Pydantic would launder the
    mistake being watched for.
    """
    path = out / "pipeline.yml"
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    lines[at + 1] = f"    value: {value}\n"
    path.write_text(_declared(path, "".join(lines)))


# --- Plan 1.15 Task 8: the premise reaches the artifact (A108, A127) ---------------------
def _star_why(out):
    return next(step for step in _load(out).steps if step.id == "star_align").why


_GOAL_MODELS = frozenset(
    {
        "Goal",
        "GoalInput",
        "Constraints",
        "RequiredStates",
        "ParamOverride",
        "ProducerPin",
        "Site",
        "DataProfile",
        "Measured",
        "Evidence",
        "ParamDecision",
        "ProducerDecision",
        "SourceDecision",
        "Displacement",
    }
)
"""Models `Pipeline` carries that are genuinely the goal's or a decision's, so blaming the
goal for one is right. `Goal` failing on an `emit` really is the goal — it is recorded in the
file, and a hand-edit to `goal:` is a hand-edit to a goal."""


def _answer_the_tier_four_question(raw: dict) -> dict:
    """Do what `driving-mendel.md` §6 tells a reader to do: answer it in the file."""
    for decision in raw["decisions"]:
        if decision["subject"] == "seq_platform":
            decision["human_override"] = "ILLUMINA"
            decision["override_reason"] = "every run in this facility is on a NovaSeq X"
    for step in raw["steps"]:
        for setting in step["settings"]:
            if setting["name"] == "seq_platform":
                setting["value"] = "ILLUMINA"
    return raw
