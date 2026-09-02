"""A16, A32, A33, A125, A126, A128 and issue #10's tail — what was decided, and by whom.

One test per finding, named for it — the question a reader has is *is A9 still
closed?*, and the test name is the answer. The 2026-08-06 audit and the rounds after
it numbered every finding; `docs/notes/audits/` records how each was reproduced.
"""


from pathlib import Path

import pytest
from comeni_core.plan.tiers import Tier
from pydantic import ValidationError
from support.audit import _declared, _pipe, _published_pipeline
from support.paths import ROOT


def test_a11_a_duplicate_binding_is_refused_before_it_can_reach_a_compare():
    """A11, one layer higher than it used to sit, and refusing instead of surviving.

    Task 1 made a tie unreachable *at the contract*, and this asserted the emitter would
    survive one anyway — because the next unorderable field on `ResolvedValue` must not
    resurrect a crash that is already fixed. A duplicate binding stayed representable, since
    an IR is deserialised from a bundle and `set_param` appends.

    Plan 1.10's `MD0212` closes it properly: two settings with one name cannot exist on a
    `Step` at all, so there is nothing left for the emitter to compare. **This test failed for
    real when that validator landed** — it constructs exactly the duplicate the validator now
    refuses, which is the guard being watched failing rather than argued about.

    Refusing beats surviving here, and by more than tidiness: `ext.args` composition sorts by
    name and *joins*, so two settings called `seq_platform` were never going to be a crash.
    They were going to be two fragments concatenated into one flag string, silently.
    """
    from comeni_core.plan.ir import IRNode, PipelineIR, ResolvedValue, Tier
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract = next(c for c in loaded.registry.all() if c.params)
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="r"),
    )
    name = contract.params[0].name
    node.set_param(name, ResolvedValue(value=1, tier=Tier.CONVENTION, reason="a"))
    node.set_param(name, ResolvedValue(value=2, tier=Tier.CONVENTION, reason="b"))

    with pytest.raises(ValidationError, match="MD0212"):
        _pipe(PipelineIR(nodes=[node]), loaded)


def test_a16_a_decision_declares_its_kind():
    """A16 — `chosen` carried three sorts of value and the discriminator was a prefix.

        subject=f"producer:{type_id}"    # chosen is a ContractId
        subject=f"source:{port.name}"    # chosen is "{node}.{port}"
        subject=param_name               # chosen is a ParamValue — no prefix at all

    Two of three prefixed and one not, so "what kind of decision is this?" was answered by
    pattern-matching a string nobody designed to be parsed. Each kind now has a type and a
    domain, and the domains are what the checks read.
    """
    from comeni_core.plan.decision import (
        DecisionKind,
        ParamDecision,
        ProducerDecision,
        SourceDecision,
    )

    common = {"key": "k", "subject": "s", "reason": "r", "resolved_by": "flag-only"}

    assert ProducerDecision(**common, chosen="nf-core/star/align@1.11.0").kind is (
        DecisionKind.PRODUCER
    )
    with pytest.raises(ValidationError):
        ProducerDecision(**common, chosen="not-a-contract")

    # The A3 collision, resolved by declaration rather than by exemption.
    assert SourceDecision(**common, chosen="dual.bam").chosen == "dual.bam"
    for not_an_edge in ("PT-4471023.fastq.gz", "S1_R1.bam.gz", "bam"):
        with pytest.raises(ValidationError):
            SourceDecision(**common, chosen=not_an_edge)

    # And the kind with no declared domain keeps its blocklist, which is what Plan 2
    # Task 11 replaces.
    assert ParamDecision(**common, chosen=None).kind is DecisionKind.PARAM


def test_a16_the_artifact_round_trips_through_the_union(tmp_path):
    """`kind` reaches the artifact, so a published pipeline must read back as itself.

    The subject moved from `pipeline.bundle.json` to `pipeline.yml` and the property got
    stronger on the way: `build` now performs this round trip on **every** run and refuses
    with `MD0206` if it fails, so the discriminated union is exercised continuously rather
    than in this test alone.
    """
    from mendel_compiler import pipeline_file

    published = _published_pipeline(tmp_path, Path("."))
    text = published.read_text()

    pipeline = pipeline_file.load(published)
    assert pipeline.decisions, "the spine has a tier-4 parameter, so there is one to read"
    assert all(record.kind for record in pipeline.decisions)
    assert pipeline_file.dump(pipeline) == text, "byte-identical, not merely equivalent"


def test_a32_the_seam_a_model_sits_behind_is_a_declared_type():
    """A32 — `Ambiguity` was the one door with no type discipline.

    `candidates: list[Any]`, `context: dict[str, Any]`, and **no `model_config` at all**, so
    `extra` defaulted to *ignore*: a field misspelled at the call site vanished silently. It
    projects to `AmbiguityRequest`, which is a closed payload — the closed half was
    downstream of the open half, which is no boundary at all.
    """
    from comeni_core.plan.decision import ParamAsked, Resolution

    with pytest.raises(ValidationError):
        ParamAsked(node_id="n", subject="s", candidates=[], extra=1)

    # `context` is gone: its three uses are declared fields on the kinds that have them.
    with pytest.raises(ValidationError):
        ParamAsked(node_id="n", subject="s", context={"anything": object()})

    # And the answer coming back is a boundary too — `resolved_by` reaches every decision
    # record and therefore a publish bundle.
    with pytest.raises(ValidationError):
        Resolution(value=None, why="r", by="a\nb")


def test_a33_a_tier_4_reason_says_what_happened(tmp_path):
    """A33 — `router._choose`'s tier-4 reason always read "chosen by id order".

    True when a tie is broken alphabetically and false when a resolver answered, which is
    the case a reviewer most needs described accurately: the record said the machine
    shrugged when a human had in fact decided.

    The first version of this test ran a goal with no tie in it and asserted over an empty
    loop — the same shape as the `_source_for` test the 2026-08-06 audit caught. The tie is
    built here, and asserted to exist before anything is asserted about it.
    """
    import shutil

    from comeni_core.plan.decision import Resolution
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    class _PicksLast:
        def resolve(self, ambiguity):
            return Resolution(
                value=sorted(ambiguity.candidates)[-1],
                why="a person read both modules and chose",
                by="human",
            )

    layer = tmp_path / "registry"
    shutil.copytree("registry", layer)
    original = (layer / "tools" / "nf-core" / "trimgalore" / "contract.yml").read_text()
    # Same priority, same output, different module key: nothing distinguishes them.
    (layer / "tools" / "nf-core" / "fastp").mkdir(parents=True, exist_ok=True)
    (layer / "tools" / "nf-core" / "fastp" / "contract.yml").write_text(
        _declared(
            layer / "tools" / "nf-core" / "fastp" / "contract.yml",
            original.replace("nf-core/trimgalore@0.6.10", "nf-core/fastp@0.24.0").replace(
            "TRIMGALORE", "FASTP"
        ))
    )

    loaded = layers_mod.load(layer)
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["fastq.reads"],
        constraints={"required_states": {"fastq.reads": ["trimmed"]}},
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=_PicksLast(),
    )

    ambiguous = [n for n in ir.nodes if n.selection.tier is Tier.AMBIGUOUS]
    assert ambiguous, "the tie must actually happen, or this asserts over an empty loop"
    for node in ambiguous:
        assert "chosen by id order" not in node.selection.reason, node.selection.reason
        assert "human" in node.selection.reason, node.selection.reason


def test_a20_marker_metadata_is_a_closed_vocabulary():
    """The marker set was open, so "declared identifier" meant "a string exists here".

    `_has_bare_str` exempts anything carrying *any* metadata, so `Annotated[str,
    "clinical-notes"]` and even `Annotated[str, 42]` passed as declared identifiers. That is
    why inverting the egress blocklist is not enough on its own: an allowlist reading "a leaf
    may be `Annotated[str, <a declared marker>]`" rebuilds the same hole unless the markers
    themselves are enumerable. Found while writing root A's spec.
    """
    import typing

    from comeni_core.spell.marks import ContractId, Mark

    # **Some** metadata element, never all. `ContractId` carries an `AfterValidator`
    # alongside its `Mark` since root C gave it a shape, exactly as `HumanParamValue`
    # always has — and requiring all would refuse every alias that validates anything,
    # which is the trap `_leaf_problems` documents.
    assert any(isinstance(m, Mark) for m in ContractId.__metadata__)

    for invented in (typing.Annotated[str, "clinical-notes"], typing.Annotated[str, 42]):
        assert not any(isinstance(m, Mark) for m in invented.__metadata__), (
            f"{invented} must not read as declared"
        )


# --- Plan 1.10 Task 8: an override is a different act from a goal pin -----------------
#
# Issue #10's tail. Answering a tier-4 parameter must clear the flag without pretending the
# question was never asked — and, as it turned out, without the answer being thrown away.


def _override_record(value="illumina"):
    from comeni_core.plan.decision import ParamDecision

    return ParamDecision(
        key="star_align.seq_platform",
        subject="seq_platform",
        candidates=[None],
        chosen=None,
        human_override=value,
        reason="our sequencer",
        resolved_by="human",
    )


def _loaded():
    from mendel_resolver import layers as layers_mod

    return layers_mod.load("registry")


def _resolved(resolver=None, mutate=None, prior=()):
    """The shipped goal, resolved. `mutate` edits the raw mapping before validation.

    `prior` is the recorded decisions behind a replayed human override. A56: `resolve()`
    honours `source: HUMAN` only where a record the *caller* supplied says a person answered
    that question with that value, so replaying an override needs both the resolver and the
    records — passing the resolver alone leaves the value flagged, which is the safe
    direction and the one `mendel upgrade` relies on.
    """
    from comeni_core import yaml_strict
    from mendel_resolver.goal import Goal
    from mendel_resolver.resolve import resolve

    loaded = _loaded()
    raw = yaml_strict.load(Path("examples/rnaseq-goal.yml"))
    if mutate is not None:
        mutate(raw)
    return resolve(
        Goal.model_validate(raw),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=resolver,
        prior=prior,
    )


def _ir_with_override(value="illumina"):
    from mendel_resolver.replay import ReplayResolver

    # The record goes to both: `ReplayResolver` answers from it, and `resolve()` verifies the
    # `HUMAN` claim against it. A56 — the claim and its evidence arrive through different
    # arguments on purpose, so one object cannot supply both.
    record = _override_record(value)
    return _resolved(resolver=ReplayResolver([record]), prior=[record])


def _binding(ir, name):
    return next(b.value for n in ir.nodes for b in n.params if b.name == name)


def test_a_human_override_on_a_parameter_is_replayed_at_all():
    """It was not, and nothing said so. Found while writing the test below.

    A parameter's candidate list is literally `[None]` — a placeholder, because a `Param` has
    no declared legal values until Plan 2 Task 11 — so `_still_applies` asked whether the
    human's answer was a member of `[None]`, and it never was. **Every** override on a
    parameter was discarded, counted as newly asked, and the recorded answer thrown away.

    That is issue #10's shape exactly: a mechanism that runs, records, and changes nothing.
    """
    from comeni_core.plan.decision import ParamAsked
    from mendel_resolver.replay import ReplayResolver

    resolver = ReplayResolver([_override_record()])
    resolution = resolver.resolve(
        ParamAsked(node_id="star_align", subject="seq_platform", candidates=[None])
    )
    assert resolution.value == "illumina", "the human's answer must be the answer"
    assert resolver.replayed == ["star_align.seq_platform"]
    assert resolver.fresh == [], "an answered question is not a new one"


def test_an_override_keeps_the_tier_it_displaced():
    """Collapsing it to tier 1 would say "no choice existed", which is what a *goal pin*
    means and is precisely what did not happen here. Resolution met a real ambiguity and
    could not settle it; a person settled it afterwards, and a reviewer reading a curated
    pipeline needs to see that it contains a question rather than that it contains none."""
    from comeni_core.plan.tiers import ValueSource

    value = _binding(_ir_with_override(), "seq_platform")
    assert value.value == "illumina"
    assert value.tier is Tier.AMBIGUOUS
    assert value.source is ValueSource.HUMAN


def test_a_goal_pin_is_still_tier_one_and_still_says_goal():
    """The regression guard for the split. `ValueSource`'s docstring argues that a
    goal-pinned param is legitimately tier 1 — the user removed the ambiguity before
    anything looked at it — and that argument stays true."""
    from comeni_core.plan.tiers import ValueSource

    def pin(raw):
        raw["constraints"] = {"params": [{"name": "seq_platform", "value": "illumina"}]}

    ir = _resolved(mutate=pin)
    value = _binding(ir, "seq_platform")
    assert value.tier is Tier.STRUCTURAL
    assert value.source is ValueSource.GOAL
    assert ir.overrides() == [], "a pin is not an override; the two must not merge"


def test_an_answered_setting_leaves_needs_review_and_appears_in_overrides():
    """Otherwise the count never reaches zero and the CLI says REVIEW for ever on a question
    already answered. `lockfile.py` makes this argument about a different list and it is the
    sharper one: a list that cries wolf gets ignored, so the genuinely unanswered tier-4
    beside it goes unread too."""
    ir = _ir_with_override()
    assert "star_align.seq_platform" not in ir.needs_review()
    assert any("star_align.seq_platform" in item for item in ir.overrides())


def test_an_unanswered_tier_four_still_needs_review():
    """The other half, and the one that matters most: clearing the flag must depend on
    somebody having answered, not on the machinery having run."""
    ir = _resolved()
    assert "star_align.seq_platform" in ir.needs_review()
    assert ir.overrides() == []


def test_an_override_reaches_the_pipeline_file_as_source_human():
    """The artifact is where a reviewer meets this, so it has to survive materialisation.

    `Why.source` already carried a `ValueSource`; what changed is that there is now a value
    for it to carry. Without this the file would say `source: resolver` beside a value no
    resolver chose."""
    from comeni_core.plan.tiers import ValueSource

    pipeline = _pipe(_ir_with_override(), _loaded())
    step = next(s for s in pipeline.steps if s.id == "star_align")
    setting = next(s for s in step.settings if s.name == "seq_platform")
    assert setting.value == "illumina"
    assert setting.why.source is ValueSource.HUMAN
    assert setting.why.tier is Tier.AMBIGUOUS


def test_a_binding_with_no_declared_param_refuses_instead_of_vanishing():
    """MD0216, and it exists because two A27 tests passed for the wrong reason.

    Both hung a smuggled value on a `nf-core/samtools/sort` binding, and that contract
    declares `params: []` — so `_settings` dropped the binding before anything looked at it,
    and neither test was asserting what its name said.

    The drop itself is the defect: a value resolution recorded, absent from the artifact that
    claims to record every value, with nothing said. It is the orphan case one level below
    `MD0203`, and it refuses for the same reason that one does.

    Resolution cannot produce this — it sets parameters *from* `contract.params` — so the
    input is a deserialised or hand-built IR, which is exactly the input `Pipeline.of` must
    not trust.

    **This test exists because reverting the refusal broke nothing.** The rule shipped first
    and the guard was written after a revert probe found it inert, which is A14's finding
    happening to the person who had just written A14's ledger row.
    """
    from comeni_core.plan.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    # `samtools/sort` until Plan 1.14, which routed its `index_format` (A91). The assertion
    # below is what caught that, and it is why the fixture names its requirement rather than
    # assuming it.
    contract_id = "nf-core/fastqc@0.12.1"
    assert loaded.registry.get(contract_id).params == [], "the fixture needs a param-less one"

    node = IRNode(
        id="samtools_sort",
        contract_id=contract_id,
        selection=ResolvedValue(value=contract_id, tier=Tier.STRUCTURAL, reason="only one"),
        params=[
            ParamBinding(
                name="threads",
                value=ResolvedValue(value=4, tier=Tier.CONVENTION, reason="a default"),
            )
        ],
    )
    with pytest.raises(ValueError, match="MD0216"):
        _pipe(PipelineIR(nodes=[node]), loaded)


def test_a_binding_the_contract_does_declare_is_carried():
    """The regression guard for the refusal above: it must depend on the param being absent,
    not on a binding existing at all."""
    from comeni_core.plan.ir import IRNode, ParamBinding, PipelineIR, ResolvedValue, Tier
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract = next(c for c in loaded.registry.all() if c.params)
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="only one"),
        params=[
            ParamBinding(
                name=contract.params[0].name,
                value=ResolvedValue(value="illumina", tier=Tier.CONVENTION, reason="d"),
            )
        ],
    )
    pipeline = _pipe(PipelineIR(nodes=[node]), loaded)
    assert [s.name for s in pipeline.steps[0].settings] == [contract.params[0].name]


MINIMAP2 = """declares: contract
id: nf-core/minimap2/align@2.28.0
nf_process: MINIMAP2_ALIGN
nf_include: modules/nf-core/minimap2/align/main
consumes:
  - {name: reads, type_id: fastq.reads, state_required: [trimmed]}
produces: [{name: bam, type_id: alignment.bam, state: []}]
priority: 10
nf_inputs:
  - {ports: [reads]}
container: community.wave.seqera.io/library/minimap2:2.28--audit
provenance: {source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-14"}
"""


def _tying_layer(tmp_path: Path) -> Path:
    """One aligner at STAR's priority, so `alignment.bam` has a genuine two-way tie.

    Inline rather than a committed fixture: the finding is entirely about *ranking*, so the
    only thing that has to be true of this contract is `priority: 10`, and a reader should
    not have to open a second file to see that. Audit A125.
    """
    layer = tmp_path / "tie-layer"
    (layer / "tools" / "nf-core" / "minimap2" / "align").mkdir(parents=True)
    (layer / "tools" / "nf-core" / "minimap2" / "align/contract.yml").write_text(
        _declared(layer / "tools" / "nf-core" / "minimap2" / "align/contract.yml", MINIMAP2)
    )
    (layer / "registry.yml").write_text(
        _declared(
            layer / "registry.yml",
            'name: tie-layer\nversion: "0"\n'))
    return layer


def _aligner_ir(*roots):
    """Resolve an aligner with no `read_length`, so the tier-3 rule cannot pin one."""
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    loaded = layers.load(list(roots))
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["alignment.bam"],
        profile=loaded.measurements.profile({"strandedness": "reverse"}),
    )
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )


def test_a125_a_tie_offers_only_the_candidates_that_tied(tmp_path):
    """A125 — adding one contract installed the aligner the registry ranked *last*.

    STAR and MINIMAP2 both sit at priority 10, so the tie is between those two. HISAT2 is at
    priority 0 and lost outright. `_choose` handed the resolver *every* candidate sorted by
    id and `FlagOnlyResolver` takes `candidates[0]`, so `hisat2` won on the letter h — and
    the artifact then reported that nothing distinguished three contracts that `priority`
    distinguishes deliberately.
    """
    registry_root = ROOT / "registry"
    ir = _aligner_ir(registry_root, _tying_layer(tmp_path))

    asked = [d for d in ir.decisions if d.subject == "producer:alignment.bam"]
    assert len(asked) == 1, [d.subject for d in ir.decisions]
    assert asked[0].candidates == [
        "nf-core/minimap2/align@2.28.0",
        "nf-core/star/align@1.11.0",
    ]
    assert "hisat2" not in asked[0].chosen


def test_a126_a_producer_decision_key_names_the_question_not_the_winner(tmp_path):
    """A126 — the key was `<winning module>.producer:<type>`, so it moved when the registry did.

    Installing one more contract renamed the question, `upgrade` found no record under the new
    name and reported the curator's recorded override as `ORPHANED — your edit no longer
    applies to anything`, while asking the identical question one line above.
    """
    registry_root = ROOT / "registry"
    ir = _aligner_ir(registry_root, _tying_layer(tmp_path))

    producer_keys = [d.key for d in ir.decisions if d.subject.startswith("producer:")]
    assert producer_keys == ["producer:alignment.bam"]


def _legacy_producer_record(candidates: list[str]):
    """A pre-1.13 producer record: the key carries the winning module's node id in front."""
    from comeni_core.plan.decision import ProducerDecision

    return ProducerDecision(
        key="star_align.producer:alignment.bam",
        subject="producer:alignment.bam",
        reason="the lab standardised on STAR",
        resolved_by="human",
        candidates=candidates,
        chosen="nf-core/star/align@1.11.0",
        human_override="nf-core/star/align@1.11.0",
    )


def _asked_producer(candidates: list[str]):
    from comeni_core.plan.decision import ProducerAsked

    return ProducerAsked(
        node_id="minimap2_align",
        subject="producer:alignment.bam",
        candidates=candidates,
    )


def test_a126_a_legacy_producer_key_still_replays():
    """A pre-1.13 artifact carries the node-prefixed key and must still replay.

    A126 is what made the prefix meaningless, not what made those files unreadable. Without
    the canonicalisation every archived pipeline reports its producer override orphaned on
    first upgrade — the exact bug, re-entering through the fix for it.
    """
    from mendel_resolver.replay import ReplayResolver

    same = ["nf-core/minimap2/align@2.28.0", "nf-core/star/align@1.11.0"]
    resolver = ReplayResolver([_legacy_producer_record(same)])

    resolution = resolver.resolve(_asked_producer(same))

    assert resolution.value == "nf-core/star/align@1.11.0"
    assert resolver.replayed == ["producer:alignment.bam"]
    assert resolver.orphaned == []


def test_a126_a_legacy_record_narrowed_by_a125_goes_stale_rather_than_orphaned():
    """Where A125 narrowed the offered set, the recorded answer is re-asked — and *said*.

    An interaction between this plan's own two fixes, found by testing it rather than by
    reasoning about it. Before A125 a producer record listed **every** candidate; after it,
    only those that tied. So a legacy record's candidate list genuinely differs and
    `_still_applies` rejects it.

    That rejection is correct: the question really did change, and replaying an answer
    chosen from a wider set would assert a decision between options that were never offered.
    What matters is that it lands in `stale_overrides` — "a person's answer was thrown away,
    here it is" — rather than in `orphaned`, which claims the edit applied to nothing. The
    honest report was the whole point of A126.
    """
    from mendel_resolver.replay import ReplayResolver

    before_a125 = [
        "nf-core/hisat2/align@2.2.2",
        "nf-core/minimap2/align@2.28.0",
        "nf-core/samtools/sort@1.21.0",
        "nf-core/star/align@1.11.0",
    ]
    after_a125 = ["nf-core/minimap2/align@2.28.0", "nf-core/star/align@1.11.0"]
    resolver = ReplayResolver([_legacy_producer_record(before_a125)])

    resolver.resolve(_asked_producer(after_a125))

    assert resolver.stale_overrides == ["producer:alignment.bam"]
    assert resolver.orphaned == []
    assert resolver.replayed == []


def test_a128_a_priority_win_says_why_the_registry_ranks_it_there(tmp_path):
    """A128 — `priority` is a bare integer and the selection said only what it did.

    *"registry priority 10, over nf-core/hisat2/align@2.2.2"* states the mechanism, not the
    reason. Tier 2 promises "a documented default exists", and the document was a YAML
    comment the loader discards — A76's exact shape, one field over.

    Reached by giving the goal no `read_length`, so the tier-3 rule cannot fire and priority
    is what decides.
    """
    ir = _aligner_ir(ROOT / "registry")
    node = next(n for n in ir.nodes if n.id == "star_align")

    assert node.selection.tier is Tier.CONVENTION
    assert "priority 10" in node.selection.reason, "the mechanism is still worth stating"
    assert "nf-core/rnaseq" in node.selection.axis_reason, (
        "and now the reason the registry ranks it there"
    )
