"""A4 and A91 — the gate that ran, and a value that reaches the tool or is refused.

One test per finding, named for it — the question a reader has is *is A9 still
closed?*, and the test name is the answer. The 2026-08-06 audit and the rounds after
it numbered every finding; `docs/notes/audits/` records how each was reproduced.
"""


import json
from pathlib import Path

from support.paths import ROOT


def test_a4_gate_is_one_class_in_two_places():
    """`Gate` moves to comeni-core so the publication payload can name one. Not a copy.

    Same move `Goal` and `DataProfile` made, with the same shim: `comeni-core` must not
    depend on the compiler, and the *command lines* stay in the compiler because those are
    how a gate is run and the core has no business knowing.
    """
    from comeni_core.artifact.gates import Gate as CoreGate
    from mendel_compiler.gates import Gate as CompilerGate

    assert CoreGate is CompilerGate
    assert [g.value for g in CoreGate] == ["lint", "preview", "stub", "test"]


def test_a4_the_artifact_records_which_gate_it_passed():
    """A4 — only `--gate test` sees a contract pointing channels at the wrong inputs.

    nf-core stubs never read their inputs, so conformance, `nextflow lint` and `-stub-run`
    all pass a mis-wired pipeline. Requiring `--gate test` to publish was rejected as a
    floor (minutes, Docker and network per publish); recording what ran lets a curator
    refuse a pipeline that never ran the only gate that checks wiring. `PipelineIR.unverified`
    set the precedent. The field moved from `PublishBundle` to `Pipeline` with the door in
    Plan 1.10 Task 11; the claim did not move at all.
    """
    from comeni_core.artifact.gates import Gate
    from comeni_core.artifact.pipeline import Pipeline
    from comeni_core.goal.asked import Goal

    assert Pipeline(goal=Goal()).gate is None
    passed = Pipeline(goal=Goal(), gate=Gate.TEST)
    assert passed.gate is Gate.TEST
    # `None` must be distinguishable from "passed lint" — an absent gate is not a weak
    # gate, it is no evidence at all, and a curator reads the two differently.
    assert json.loads(passed.model_dump_json())["gate"] == "test"
    assert json.loads(Pipeline(goal=Goal()).model_dump_json())["gate"] is None


def test_a4_publishing_records_the_gate_that_actually_ran(tmp_path, monkeypatch):
    import yaml
    from mendel_compiler import cli
    from mendel_compiler.cli import artifact_verbs, resolve_verbs
    from mendel_compiler.gates import GateResult

    # **Two patches, because the gate runs twice from two modules.** `build` invokes it from
    # `resolve_verbs` and `publish` from `artifact_verbs`, and `run_gate` is looked up in the
    # calling module. Patching only the first left `publish` running the *real* gate — which
    # passes on a developer machine with `nextflow` on PATH and fails in CI, where it is not
    # installed. The test was green locally for the wrong reason, and CI is what said so.
    def _passes(gate, out):
        return GateResult(gate=gate, passed=True)

    monkeypatch.setattr(resolve_verbs, "run_gate", _passes)
    monkeypatch.setattr(artifact_verbs, "run_gate", _passes)
    out = tmp_path / "p"
    assert cli.main([
        "build", "--goal", str(Path("examples/rnaseq-goal.yml")),
        "--out", str(out), "--root", ".",
    ]) == 0
    assert cli.main([
        "publish", str(out / "pipeline.yml"), "--root", ".", "--gate", "lint",
    ]) == 0
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"


def test_a4_a_failed_gate_publishes_nothing(tmp_path, monkeypatch):
    """Publication is the door with no undo, so a *verdict* must not survive a failed gate.

    The bundle was written before the gate ran, so `publish --gate test` left a bundle on
    disk and returned 1 — an artifact claiming to be a pipeline that had just failed the only
    gate that checks wiring. The bundle is gone since Plan 1.10 and the claim survives it: a
    failed gate stamps `gate: null`, which is no evidence, and no evidence must never read as
    a gate that passed.
    """
    import yaml
    from mendel_compiler import cli
    from mendel_compiler.cli import artifact_verbs, resolve_verbs
    from mendel_compiler.gates import GateResult

    # **Both**, and that is the finding rather than a chore. This test builds and then
    # publishes, and issue #41's split put those verbs in different modules — `resolve_verbs`
    # runs the gate at the end of a build, `artifact_verbs` runs it when certifying a
    # directory that already exists. One `monkeypatch` covered both while they shared a
    # module, which meant nothing here recorded that the gate is invoked twice.
    failed = lambda gate, out: GateResult(gate=gate, passed=False, stdout="no")  # noqa: E731
    monkeypatch.setattr(resolve_verbs, "run_gate", failed)
    monkeypatch.setattr(artifact_verbs, "run_gate", failed)
    out = tmp_path / "p"
    assert cli.main([
        "build", "--goal", str(Path("examples/rnaseq-goal.yml")),
        "--out", str(out), "--root", ".",
    ]) == 0
    assert cli.main([
        "publish", str(out / "pipeline.yml"), "--root", ".", "--gate", "lint",
    ]) == 1
    # The claim moved with the artifact. There is no bundle to be absent any more, so what
    # must not survive a failed gate is the *verdict*: `gate: null` is no evidence, and it
    # must never read as a gate that passed.
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] is None


def test_a91_a_positional_parameter_reaches_the_call_and_nothing_else(tmp_path):
    """A91, critical — one call carrying **two values of the same name, disagreeing**.

    `Via` had three members and none emitted into a call position, so three of ten vendored
    modules took a bare `val` that no route could reach. Routing STAR's own
    `star_ignore_sjdbgtf` the only way the design permitted — `via: meta` — produced:

        STAR_ALIGN((TRIMGALORE.out.reads).map { it -> [ it[0] + [star_ignore_sjdbgtf: true] ]
                   + it[1..-1] }, STAR_GENOMEGENERATE.out.index, ch_annotation_gtf, false)

    The documented, tier-4, human-answered value landed in `meta`, where `main.nf:47` never
    looks. The one STAR reads is the trailing `false`. `pipeline.yml` said the GTF was being
    ignored; the pipeline used it.
    """
    from comeni_core.artifact.pipeline import Pipeline
    from mendel_compiler.emit import emit
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput, ParamOverride
    from mendel_resolver.resolve import resolve

    root = ROOT
    loaded = layers.load(root / "registry")
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={
            "required_states": {"counts.matrix": ["gene_level"]},
            "params": [ParamOverride(name="star_ignore_sjdbgtf", value=True)],
        },
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    ir = resolve(
        goal, loaded.registry, loaded.rules, loaded.measurements, vocabulary=loaded.vocabulary
    )
    pipeline = Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal
    )
    call = next(
        line for line in emit(pipeline).splitlines() if "STAR_ALIGN(" in line
    )

    assert call.count("star_ignore_sjdbgtf") == 0, (
        "it is positional; the module reads it by position and no name is emitted"
    )
    assert call.rstrip().endswith("true)"), call


def test_a91_a_meta_route_to_a_key_the_module_never_reads_is_refused():
    """The other half of A91: the route that let it hide.

    `MD0108` exists to refuse a route the module does not read, and gated on
    `via is not Via.EXT` — its own docstring conceded meta and directive were unchecked. So
    routing a parameter to `meta` produced a value STAR never looks at, no diagnostic fired,
    and the artifact recorded a documented, human-answered decision that reached nothing.
    """
    from mendel_compiler import conformance
    from mendel_resolver import layers

    root = ROOT
    loaded = layers.load(root / "registry")
    contract = loaded.registry.get("nf-core/star/align@1.11.0")
    # Reroute the positional parameter to `meta`, which is exactly what the audit did and
    # what nothing refused.
    # `model_validate` rather than `model_copy`: the latter skips validation and leaves
    # `via` as the *string* "meta", which `is Via.META` then misses — A62's shape, and it
    # would have made this test pass for the wrong reason had the check used `==`.
    raw = contract.model_dump()
    for entry in raw["params"]:
        if entry["name"] == "star_ignore_sjdbgtf":
            entry.update(via="meta", key=None, template=None)
    rerouted = type(contract).model_validate(raw)
    registry = loaded.registry
    registry.contracts[contract.id] = rerouted

    # **The layer carries the module** since Plan 5A, so conformance is handed the stack's
    # modules rather than a `vendor/` root — a contract and the thing it is a binding for are
    # versioned together now, which is what `MD0104` needed all along.
    found = conformance.check(registry, loaded.modules)
    codes = {(d.code, d.where) for d in found}

    assert any(
        code == "MD0108" and "star_ignore_sjdbgtf" in where for code, where in codes
    ), codes
