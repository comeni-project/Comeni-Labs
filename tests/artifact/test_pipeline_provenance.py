"""Saved-pipeline provenance: observable CLI and artifact behavior."""

import pytest
import yaml
from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline
from comeni_core.plan.tiers import PremiseOrigin
from mendel_compiler.cli import main
from pydantic import ValidationError
from support.paths import ROOT
from support.pipeline import (
    GOAL,
    _answer,
    _answer_the_tier_four_question,
    _build,
    _build_measured,
    _build_with_overlay,
    _declared,
    _displaced_kinds,
    _edit_setting_value,
    _emit,
    _load,
    _star_why,
)


def test_the_file_carries_every_provenance_a_reader_needs(tmp_path):
    """One file answers "what settings does this pipeline use, and why".

    Four files answered it before, and one of the four mechanisms carried nothing at all.
    """
    raw = yaml.safe_load((_build(tmp_path) / "pipeline.yml").read_text())
    assert raw["version"] == SCHEMA_VERSION
    assert set(raw) == {
        "version",
        "goal",
        "registry",
        "ai",
        "steps",
        "channels",
        # How a laboratory hands this pipeline its per-sample data — a closed choice, so the
        # words a reader needs are generated rather than authored. Plan 5B §5.2.
        "input_form",
        "decisions",
        "emitted",
        "gate",
    }
    star = next(s for s in raw["steps"] if s["id"] == "star_align")
    assert star["module"]["digest"].startswith("sha256:")
    assert star["module"]["container"].startswith("community.wave.seqera.io/")
    assert star["why"]["reason"]
    setting = next(s for s in star["settings"] if s["name"] == "seq_platform")
    assert setting["value"] is None, "nobody answered it, and the file must not pretend"
    assert setting["via"] == "ext" and setting["key"] == "args"
    assert setting["why"]["tier"] == 4


def test_the_file_records_the_goal_it_was_built_from(tmp_path):
    """`goal:` was written empty for the first hour of Task 6, and everything passed.

    `Pipeline.of` defaulted it to `Goal(profile=ir.profile)` — which type-checks, round-trips,
    and satisfies the totality test, because that test asks whether a field has a *home* and
    this one did. It is now keyword-only with no default. A field present and empty is worse
    than a field absent: the file claims to record what was asked for.
    """
    raw = yaml.safe_load((_build(tmp_path) / "pipeline.yml").read_text())
    declared = yaml.safe_load(GOAL.read_text())
    assert raw["goal"]["want"] == declared["want"]
    assert [item["type_id"] for item in raw["goal"]["have"]] == [
        item["type_id"] for item in declared["have"]
    ]
    measured = {m["measurement"]: m["value"] for m in raw["goal"]["profile"]["measurements"]}
    assert measured["strandedness"] == "reverse"


# Regression evidence: A51
def test_a_vocabulary_displacement_reaches_the_artifact(tmp_path):
    """A24 gave a vocabulary displacement somewhere to be recorded — `loaded.displaced` — but
    `resolve()` re-derived `PipelineIR.displaced` from measurements+contracts alone, so the one
    overlay that rewrites emitted Groovy verbatim reached the published file saying nothing. The
    artifact is what a reader audits; a silent reroute there is the whole of what invariant 11
    forbids."""
    ov = tmp_path / "ov"
    (ov / "vocabularies").mkdir(parents=True)
    (ov / "registry.yml").write_text(_declared(ov / "registry.yml", "name: lab-vocab\n"))
    # Replace fastq.reads' entry_channel — the base's states, a lab's own source path.
    (ov / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(
            ov / "vocabularies" / "fastq.reads.yml",
            "states: [trimmed, deduplicated, subsampled]\n"
            "entry_channel: \"Channel.fromFilePairs('/mnt/lab/run7/*_R{1,2}.fastq.gz')\"\n",
        )
    )
    out = _build_with_overlay(tmp_path, ov)
    assert "vocabularies" in _displaced_kinds(out)


# Regression evidence: A51
def test_a_rules_displacement_reaches_the_artifact(tmp_path):
    """The same gap for the fourth kind: an overlay `rules/` block replacing a base decision
    was recorded on `RuleTable.displaced_layer` (per-node, A15) but never as a `Displacement`
    on the artifact's `registry.displaced`. Now all four kinds land in one list a reader reads
    once."""
    ov = tmp_path / "ov"
    (ov / "rules").mkdir(parents=True)
    (ov / "registry.yml").write_text(_declared(ov / "registry.yml", "name: lab-rules\n"))
    base_rule = (ROOT / "registry/rules/alignment.yml").read_text()
    (ov / "rules" / "alignment.yml").write_text(
        _declared(ov / "rules" / "alignment.yml", base_rule)
    )
    out = _build_with_overlay(tmp_path, ov)
    assert "rules" in _displaced_kinds(out)


# Regression evidence: A46
# --- A46: a tier-4 answer has one writable home; the two must not disagree ---
def test_value_and_human_override_may_not_contradict(tmp_path, capsys):
    """settings[].value is the writable answer; a human_override that differs is one file, two
    answers, and emit and upgrade read different ones. Refuse rather than pick."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
    for d in doc["decisions"]:
        if d["key"].endswith("seq_platform"):
            d["human_override"] = "illumina"
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0218" in err


# Regression evidence: A46
def test_editing_the_value_answers_for_emit_and_upgrade(tmp_path, capsys):
    """The A46 fix: editing settings[].value is honoured by both verbs, not just emit."""
    out = _build(tmp_path)
    _answer(out, "seq_platform", "nanopore")
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert "'PL:nanopore'" in (out / "nextflow.config").read_text()
    nxt = tmp_path / "next"
    assert main(["upgrade", str(out / "pipeline.yml"), "--out", str(nxt), "--root", str(ROOT)]) == 0
    assert "'PL:nanopore'" in (nxt / "nextflow.config").read_text()


# Regression evidence: A54
# --- A54: `source: human` is a claim about evidence, not assertable through the port ---
def test_human_source_requires_a_matching_override(tmp_path, capsys):
    """`why.source: human` is what clears a tier-4 review — it says a person answered the
    ambiguity after resolution flagged it. Asserted through `settings[].why` with no decision
    recording that answer, it is a review cleared by claim: the exact dishonesty invariant 6
    forbids. A `human` source must have a matching non-null `human_override`."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
                setting["why"]["source"] = "human"
                setting["why"]["reason"] = "this facility sequences on a MinION"
                setting["why"]["for_value"] = "nanopore"
    # Deliberately leave decisions[].human_override null — the claim without the evidence.
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code == 2 and "MD0220" in err


# Regression evidence: A54
def test_human_source_with_a_matching_override_is_accepted(tmp_path, capsys):
    """The honest case: the value, the `human` source, the decision's override **and the
    reason beside the value** all agree — a person answered, and the record proves it.

    The reason was not part of "all agree" until issue #48, and that was the defect: this
    test set the value, the source and the override, left `why.reason` reading *"no rule
    covered … please review"*, and called the record proof. `MD0223` now refuses exactly
    that, so the test says what it always meant.
    """
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
                setting["why"]["source"] = "human"
                setting["why"]["reason"] = "this facility sequences on a MinION"
                setting["why"]["for_value"] = "nanopore"
    for d in doc["decisions"]:
        if d["key"].endswith("seq_platform"):
            d["human_override"] = "nanopore"
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    code, err = _emit(out, capsys)
    assert code == 0, err


# Regression evidence: A104, A105
def test_editing_a_value_and_leaving_its_reason_is_refused(tmp_path, capsys):
    """A104, critical. The edit reached the tool; the reason beside it described the old value.

    Reproduced by the design audit: `min_mqs` edited 0 → 30 emits `-Q 30` — reads below
    mapping quality 30 are now discarded, a real analysis change — while the record still
    reads `tier: 2 / source: resolver / reason: contract default for min_mqs`, all three
    false. `mendel publish --gate lint` certified it at exit 0.

    A diagnostic rather than a parse error, deliberately: the file says *"Read it; edit it"*,
    so a person who changes a number must be **told to update the reason**, not handed a
    stack trace for doing what the header invited.
    """
    out = _build(tmp_path)
    _edit_setting_value(out, "min_mqs", 30)

    code, err = _emit(out, capsys)

    assert code != 0
    assert "MD0223" in err
    assert "0" in err and "30" in err, "name both values, or the reader cannot act"


# Regression evidence: A104, A105
def test_editing_a_value_and_its_reason_together_is_accepted(tmp_path, capsys):
    """The negative. A check that can only refuse is not a check — it is an obstacle."""
    out = _build(tmp_path)
    _edit_setting_value(out, "min_mqs", 30)
    path = out / "pipeline.yml"
    path.write_text(
        _declared(
            path,
            path.read_text()
            .replace(
                "reason: contract default for min_mqs",
                "reason: lab SOP BIOINF-014 requires MAPQ >= 30",
            )
            .replace("for_value: 0", "for_value: 30"),
        )
    )

    code, err = _emit(out, capsys)

    assert code == 0, err
    assert "-Q 30" in (out / "nextflow.config").read_text()


# Regression evidence: A108, A127
def test_a_tier_3_decision_records_the_premise_it_rested_on(tmp_path):
    """A108. Tier 3 is defined as producing `value + rule + measurement` and produced the
    first two: the artifact said which rule fired and never what it fired *on*.

    `CLAUDE.md` calls tier 3 advisory and glosses it *"the machinery worked, check the
    premise"* — and there was no premise in the file to check.
    """
    why = _star_why(_build(tmp_path))
    assert [(p.id, p.value) for p in why.premise] == [("read_length", 150)]
    assert why.premise[0].origin is PremiseOrigin.ASSERTED


# Regression evidence: A108, A127
def test_a_measured_build_and_an_asserted_one_are_not_byte_identical(tmp_path):
    """The sharp end of A108, and the thing `sealed` needs (issue #2).

    A read length a tool measured and one somebody typed into a goal file are different
    evidence for the same decision, and the artifact recorded them identically. A clinical
    reviewer had no way to tell a pipeline resting on measurement from one resting on a
    claim.
    """
    asserted = _load(_build(tmp_path, "asserted"))
    measured = _load(_build_measured(tmp_path))
    assert asserted.model_dump() != measured.model_dump()
    origins = {
        step.id: [p.origin for p in step.why.premise] for step in measured.steps if step.why.premise
    }
    assert origins["star_align"] == [PremiseOrigin.MEASURED]


# Regression evidence: A108, A127
def test_a_premise_read_by_ai_says_so_in_the_file(tmp_path):
    """14.7.7: the reason a reader checks says who read it, and never *asserted in the goal*."""
    out = _build_measured(tmp_path, "read-by-ai", source="source: model", paired="source: model")
    why = _star_why(out)
    assert why.premise[0].origin is PremiseOrigin.MODEL_READ
    assert "read_length is 150, read by AI" in why.reason
    single_end = next(
        m for channel in _load(out).channels for m in channel.meta if m.key == "single_end"
    )
    assert single_end.why.reason.startswith("read by AI from the start of a sample")
    # #239 (a): the file says the characteriser was used, upstream of this build.
    ai = _load(out).ai
    assert "characterise" in ai.available and "characterise" in ai.used


# Regression evidence: A108, A127
def test_MD0225_a_premise_read_by_ai_cannot_claim_no_ai_was_available(tmp_path):
    """#239: MD0225 covered settings only, so a premise or a `meta` value read by a model sat
    beside `ai.available: []`, the contradiction A130 refuses."""
    out = _build_measured(tmp_path, "read-by-ai", source="source: model", paired="source: model")
    raw = _load(out).model_dump(mode="json")
    raw["ai"] = {"available": [], "used": []}
    with pytest.raises(ValidationError) as caught:
        Pipeline.model_validate(raw)
    assert "MD0225" in str(caught.value)
    assert "star_align" in str(caught.value) and "single_end" in str(caught.value)


# Regression evidence: A108, A127
def test_the_premise_is_a_list_of_records_rather_than_a_mapping(tmp_path):
    """`tests/test_egress.py` forbids a mapping in anything payload-reachable, and `Why`
    reaches door 4 — publication, the door with no undo.

    The plan drafted this as two parallel `dict[str, Any]` fields and all three of that
    guard's rules refused it: a mapping, an `Any`, and a bare `str` key. One record carrying
    id, value and origin together is also the better shape — two parallel mappings can
    disagree about their key sets, and nothing would notice.
    """
    record = _star_why(_build(tmp_path)).premise[0]
    assert record.model_dump() == {
        "id": "read_length",
        "value": 150,
        "origin": "asserted",
    }


# Regression evidence: A108, A127
def test_the_reason_states_the_premise_value_not_the_predicate(tmp_path):
    """§6.1. The shipped artifact said

        reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: …'

    — a Python dict repr embedded in YAML with doubled quotes, reporting the **predicate**
    and never the value. A reader learned the rule tested `>= 70` and never learned that
    `read_length` was 150, or that anything had measured it.
    """
    reason = _star_why(_build(tmp_path)).reason
    assert "read_length is 150" in reason
    assert "{" not in reason, "no dict repr reaches a sentence a person reads"
    assert ">= 70" not in reason, "the predicate is the rule's business, not the reader's"


# Regression evidence: A108, A127
def test_the_reason_says_whether_the_premise_was_measured(tmp_path):
    """The value tells a reviewer what to check against the sample sheet; the origin tells
    them whether checking is worth their time. Both, or the sentence is half a claim."""
    assert "asserted, not measured" in _star_why(_build(tmp_path)).reason
    assert "measured" in _star_why(_build_measured(tmp_path)).reason


# Regression evidence: A108, A127
def test_MD0223_sees_a_tier_four_setting_answered_by_hand(tmp_path):
    """Issue #48 — the one case a human is most likely to be editing was the one case it missed.

    `stale_reasons` skipped every setting whose `for_value` is `None`, on the stated grounds
    that a pre-1.14 file has no such field and *absence is not disagreement*. A tier-4 value
    nothing resolved **also** has `for_value: null`, so answering one left `why.reason` reading
    *"no rule covered … please review"* beside a value somebody had just chosen, and `emit`
    accepted it at exit 0.
    """
    from mendel_compiler.pipeline_file import stale_reasons

    raw = _answer_the_tier_four_question(
        yaml.safe_load((_build(tmp_path) / "pipeline.yml").read_text())
    )
    stale = stale_reasons(Pipeline.model_validate(raw))
    assert any("seq_platform" in line for line in stale)
    assert any("override_reason" in line for line in stale), (
        "say what to write, not only that something is wrong"
    )


# Regression evidence: A108, A127
def test_an_unanswered_tier_four_setting_is_not_flagged(tmp_path):
    """*"please review"* is what an **open** question is supposed to say.

    Flagging it would make `MD0223` a nag, and a nag is a check people stop reading. This is
    the test that keeps the #48 widening from simply flagging every tier-4 setting.
    """
    from mendel_compiler.pipeline_file import stale_reasons

    raw = yaml.safe_load((_build(tmp_path) / "pipeline.yml").read_text())
    assert stale_reasons(Pipeline.model_validate(raw)) == []
