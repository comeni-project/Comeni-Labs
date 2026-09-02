"""Every input the emitted pipeline declares is fed by something real.

`gate stub: PASS` cannot prove this. nf-core stubs never read their inputs, so a process
handed `Channel.value([[:], []])` where a genome should be executes exactly as happily as
one handed a genome. The DAG was correct and the analysis was impossible.

`test_contract_input_signatures_match_the_vendored_modules` cannot prove it either: it
checks arity, and an empty placeholder has the same arity as a real channel.
"""


import pytest
from comeni_core.declared.contract import NfInput
from comeni_core.plan.tiers import ValueSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from pydantic import ValidationError
from support.paths import ROOT


@pytest.fixture
def loaded():
    return layers.load(ROOT / "registry")


@pytest.fixture
def spine(loaded):
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )


@pytest.fixture
def spine_with_profile(loaded):
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile(
            {"read_length": 150, "strandedness": "reverse", "paired": True}
        ),
    )
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )


def test_every_empty_placeholder_says_why_it_is_empty(loaded):
    """`NfInput.empty` was doing two different jobs, and nothing told them apart.

    "this input models nothing in the type system" and "we have not wired this yet" look
    identical in YAML and identical in the emitted Groovy. One is a design decision and
    the other is a bug, and the second shipped twice. Requiring a sentence turns the next
    one into something a reviewer reads rather than something a real run discovers.
    """
    unexplained = [
        f"{contract.id} input {position}"
        for contract in loaded.registry.all()
        for position, spec in enumerate(contract.input_signature())
        if spec.empty and not spec.because
    ]
    assert unexplained == [], (
        "an empty placeholder must say why the type system does not model this input: "
        + ", ".join(unexplained)
    )


def test_a_declared_type_is_never_replaced_by_a_placeholder(loaded):
    """The specific failure: `genome.fasta` exists, and STAR was handed an empty tuple.

    If a contract consumes a port, that port must appear in `nf_inputs`. A declared port
    that no channel carries is a port the router satisfied and the compiler discarded.
    """
    dropped = []
    for contract in loaded.registry.all():
        wired = {name for spec in contract.input_signature() for name in spec.ports}
        for port in contract.consumes:
            if port.name not in wired:
                dropped.append(f"{contract.id}.{port.name}")
    assert dropped == [], (
        "these ports are consumed but never reach the process call: " + ", ".join(dropped)
    )


def test_the_genome_is_a_declared_type(loaded):
    """You cannot build an aligner index without one."""
    assert "genome.fasta" in loaded.vocabulary.types
    assert loaded.vocabulary.entry_channels["genome.fasta"]


def test_both_index_builders_consume_the_genome(loaded):
    for contract_id in ("nf-core/star/genomegenerate@1.11.0", "nf-core/hisat2/build@2.2.2"):
        consumed = {p.type_id for p in loaded.registry.get(contract_id).consumes}
        assert "genome.fasta" in consumed, contract_id


def test_star_align_consumes_the_annotation(loaded):
    """It was handed an empty tuple while the GTF sat in the same workflow."""
    star = loaded.registry.get("nf-core/star/align@1.11.0")
    assert "annotation.gtf" in {p.type_id for p in star.consumes}


def test_the_emitted_workflow_feeds_the_genome_to_star(spine, loaded):
    from mendel_compiler.emit import emit

    source = emit(_pipe(spine, loaded))
    call = next(line for line in source.splitlines() if "STAR_GENOMEGENERATE(" in line)
    assert "ch_fasta" in call, call
    assert "[[:], []]" not in call, call


def test_the_emitted_workflow_feeds_the_annotation_to_star_align(spine, loaded):
    from mendel_compiler.emit import emit

    source = emit(_pipe(spine, loaded))
    call = next(line for line in source.splitlines() if "STAR_ALIGN(" in line)
    assert "ch_gtf" in call, call


def test_the_config_asks_the_laboratory_for_a_genome(spine, loaded):
    from mendel_compiler.emit import emit_config, entry_params

    assert "fasta" in entry_params(_pipe(spine, loaded))
    assert "fasta = null" in emit_config(_pipe(spine, loaded))


def test_a_test_profile_is_emitted_when_every_input_declares_test_data(spine, loaded):
    """Gate.TEST runs `-profile test`. Until now nothing emitted one, so it could not pass.

    The URLs come from the vocabulary, for the same reason `entry_channel` does: the
    compiler has no built-in idea what a FASTQ is, and a type a lab invents has to be able
    to bring its own.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipe(spine, loaded))
    assert "test {" in config
    assert "nf-core/test-datasets" in config


def test_the_test_profile_is_labelled_as_a_smoke_test(spine, loaded):
    """It proves the pipeline runs on a known dataset. It does not prove the analysis."""
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipe(spine, loaded))
    assert "smoke test" in config.lower()
    assert "not" in config.lower() and "correct" in config.lower()


def test_a_contract_can_declare_flags_its_module_always_needs(loaded):
    """Not a decision, so it carries no tier. `nf_inputs` says which channels a module
    takes; this says which flags it takes. Both are "how is this called", and neither is
    "what should be decided" — giving it a tier would dilute what a tier means."""
    star = loaded.registry.get("nf-core/star/align@1.11.0")
    assert "--readFilesCommand zcat" in star.ext_args.template


def test_ext_args_reaches_the_emitted_config(spine, loaded):
    """STAR died on real data with 'wrong read ID line format' and a binary offending
    line: TrimGalore emits .fq.gz and nothing told STAR to decompress."""
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipe(spine, loaded))
    assert "process {" in config
    assert "withName: STAR_ALIGN" in config
    assert "ext.args = '--readFilesCommand zcat'" in config


def test_a_module_with_no_ext_args_gets_no_withname_block(spine, loaded):
    """An empty block is noise, and noise in generated config is how nobody reads it."""
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipe(spine, loaded))
    assert "withName: TRIMGALORE" not in config


def test_ext_args_is_escaped_like_any_other_literal():
    """These reach Groovy. An unescaped quote is a syntax error and a crafted value runs."""
    from mendel_compiler.emit import _render_literal

    assert "\\'" in _render_literal("--x 'quoted'")


def test_a_measurement_can_declare_how_it_appears_in_meta(loaded):
    strandedness = loaded.measurements.get("strandedness")
    assert strandedness.describes == "fastq.reads"
    assert strandedness.meta_key == "strandedness"


def test_a_measurement_can_declare_a_value_translation(loaded):
    """We ask whether the library is paired; nf-core asks whether it is single-end.
    The same fact, spelled inside out, and the translation is declared rather than known
    by the compiler."""
    paired = loaded.measurements.get("paired")
    assert paired.meta_key == "single_end"
    assert loaded.measurements.meta_for(
        "fastq.reads", loaded.measurements.profile({"paired": True})
    ) == {"single_end": False}


def test_measurements_without_a_meta_key_are_not_carried(loaded):
    """`n_samples` is a property of the study, not of a read. Opt-in, so nothing lands in
    a meta map by accident."""
    meta = loaded.measurements.meta_for(
        "fastq.reads", loaded.measurements.profile({"n_samples": 12, "strandedness": "reverse"})
    )
    assert meta == {"strandedness": "reverse"}


def test_meta_is_only_built_for_the_type_a_measurement_describes(loaded):
    """Putting strandedness on the genome channel would be meaningless and would read as a
    bug to anyone inspecting the emitted workflow."""
    profile = loaded.measurements.profile({"strandedness": "reverse"})
    assert loaded.measurements.meta_for("genome.fasta", profile) == {}


def test_the_emitted_entry_channel_carries_the_meta(spine_with_profile, loaded):
    from mendel_compiler.emit import emit

    source = emit(_pipe(spine_with_profile, loaded))
    line = next(ln for ln in source.splitlines() if "ch_reads =" in ln)
    assert "strandedness: 'reverse'" in line, line
    assert "single_end: false" in line, line


def test_an_unmeasured_profile_emits_no_meta_wrapper(loaded):
    """No profile, no `.map`. The pipeline should not gain a no-op that a reader has to
    understand before dismissing."""
    from mendel_compiler.emit import emit

    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["qc.report"],
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
    source = emit(_pipe(ir, loaded))
    line = next(ln for ln in source.splitlines() if "ch_reads =" in ln)
    assert "meta +" not in line, line


def _pipe(ir, loaded):
    """Materialise an IR for the emitter.

    `emit` takes one argument since Plan 1.10 Task 5 — everything it used to look up in the
    registry, vocabulary and measurements now lives on the `Pipeline`.

    `goal` is keyword-only and required since Task 6. An empty one is honest here: these
    fixtures start from an IR and never had a goal to record.
    """
    from comeni_core.artifact.pipeline import Pipeline
    from comeni_core.goal.asked import Goal

    return Pipeline.of(ir, loaded.registry, loaded.vocabulary, loaded.measurements, goal=Goal())


def test_two_ports_in_one_channel_must_declare_a_join():
    """A cross product where a per-sample join belongs is a wrong result from a green run.

    Audit A92: two samples in, four processes out, half of them pairing sample 1's data with
    sample 2's. Nextflow reports success and exits 0. `--gate test` cannot catch it because
    the nf-core RNA-seq test dataset has one sample, so `1 x 1 == 1`.
    """
    with pytest.raises(ValidationError, match="two or more ports"):
        NfInput(ports=["bam", "annotation"])


def test_one_port_needs_no_join():
    assert NfInput(ports=["bam"]).join is None


def _profiled_goal(loaded) -> Goal:
    """The `spine_with_profile` goal, reconstructed. Its measurements are asserted, not
    measured: a plain mapping in a goal file is a claim by whoever typed it."""
    return Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile(
            {"read_length": 150, "strandedness": "reverse", "paired": True}
        ),
    )


def test_a_measured_fact_carries_where_it_came_from(spine_with_profile, loaded):
    """A80 — `-s 2` is this project's worked example of the system working.

    `strandedness: reverse` becomes featureCounts' `-s 2`, and getting it wrong is the classic
    way to a matrix of zeroes. It reached the tool with **no `why` of any kind**, while the
    measurement's own declared `cite` stopped at the registry. `MetaEntry` was key + value.
    """
    from comeni_core.artifact.pipeline import Pipeline

    pipeline = Pipeline.of(
        spine_with_profile,
        loaded.registry,
        loaded.vocabulary,
        loaded.measurements,
        loaded.paths,
        goal=_profiled_goal(loaded),
    )
    meta = {entry.key: entry for channel in pipeline.channels for entry in channel.meta}

    assert meta["strandedness"].why.reason, "a fact reaching a tool with no reason is A80"
    assert meta["strandedness"].why.for_value == meta["strandedness"].value


def test_an_asserted_fact_and_a_measured_one_are_distinguishable(loaded):
    """The foundation of A108, and nothing more than that.

    A profiler naming itself and a person typing a number into a goal file are both
    legitimate; only one is checkable, and `sealed` is meant to refuse a tier-3 decision
    resting on the second (issue #2). Until now the artifact could not tell them apart at all.

    This does **not** close A108 — the tier-3 *decision* still carries no premise. It makes
    the premise recordable, which is the part that has to exist first.
    """
    from comeni_core.artifact.pipeline import Pipeline

    asserted = _profiled_goal(loaded)
    ir = resolve(
        asserted,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
    pipeline = Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=asserted
    )
    meta = {entry.key: entry for channel in pipeline.channels for entry in channel.meta}

    assert meta["strandedness"].why.source is ValueSource.GOAL
    assert "goal" in meta["strandedness"].why.reason.lower()


def test_every_positional_literal_says_why_it_is_that_value(loaded):
    """A81 — `'bai'` and `false` are analysis decisions wearing the costume of plumbing.

    `SAMTOOLS_SORT(…, 'bai')` picks BAI over CSI, which constrains which genomes the pipeline
    works on. `STAR_ALIGN(…, false)` decides whether alignment is GTF-guided. Both reached the
    tools with `why: null`, in no `decisions:` block and no review queue, and
    `pipeline-schema.md` documented a `literal` + `why` pair the registry could not produce.

    Same shape as the `empty` guard above and for the same reason: `empty` was the placeholder
    everyone worried about, so the *values* went unexamined.
    """
    unexplained = [
        f"{contract.id} input {position} = {spec.literal!r}"
        for contract in loaded.registry.all()
        for position, spec in enumerate(contract.input_signature())
        if spec.literal is not None and not spec.because
    ]
    assert unexplained == [], (
        "a positional literal must say why it is that value, not merely what it is: "
        + ", ".join(unexplained)
    )


def _goal_with_trimmed_reads(loaded) -> Goal:
    """The same goal, declaring the reads already trimmed. TrimGalore drops out."""
    return Goal(
        have=[
            GoalInput(type_id="fastq.reads", states=frozenset({"trimmed"})),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )


def test_ext_args_carries_a_reason(spine, loaded):
    """A82 — it reached the tool with no `why` at all, and that was recorded as deliberate.

    The recorded argument was *"nothing resolved it and there is no decision behind it, so
    giving it a `why` would invent provenance"*. That conflates **tier** with **reason**: a
    tier-1 fact still has a reason, and `NfInput.empty` already proves it by carrying a
    tier-1 `Why` for a structurally identical thing.
    """
    from comeni_core.artifact.pipeline import Pipeline

    pipeline = Pipeline.of(
        spine, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths,
        goal=_profiled_goal(loaded),
    )
    star = next(step for step in pipeline.steps if step.id == "star_align")

    assert star.ext_args.template == "--readFilesCommand zcat"
    assert star.ext_args.why.reason


def test_the_ext_args_premise_survives_the_module_it_names(loaded):
    """The sharp half of A82: **a recorded reason that has stopped being true**.

    `--readFilesCommand zcat` was justified in the contract by *"TrimGalore emits .fq.gz — a
    fact about the upstream module's output format."* One goal edit — declaring the reads
    already trimmed — removes TrimGalore from the pipeline entirely, and the flag survives
    with a justification naming a module that is not there.

    Stated as a *premise about the reads* rather than a fact about a neighbour, so it stays
    true when the graph moves and states its own limit: a laboratory supplying uncompressed
    trimmed reads gets a wrong flag, and nothing here will catch that.
    """
    from comeni_core.artifact.pipeline import Pipeline

    goal = _goal_with_trimmed_reads(loaded)
    ir = resolve(
        goal, loaded.registry, loaded.rules, loaded.measurements, vocabulary=loaded.vocabulary
    )
    pipeline = Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal
    )

    assert not any("trimgalore" in step.id for step in pipeline.steps), (
        "this test is about a premise outliving TrimGalore; TrimGalore must be gone"
    )
    star = next(step for step in pipeline.steps if step.id == "star_align")
    assert star.ext_args.template == "--readFilesCommand zcat"
    assert "TrimGalore emits" not in star.ext_args.why.reason, (
        "the reason must not assert a fact about a module that is not in this pipeline"
    )
    assert "gzip" in star.ext_args.why.reason.lower()
