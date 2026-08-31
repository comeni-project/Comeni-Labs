import pathlib
import re

import pytest
from comeni_core.artifact.pipeline import ExtArgs, Pipeline
from comeni_core.goal.asked import Goal
from comeni_core.plan.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from mendel_compiler.emit import emit
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _vocab():
    return layers.load(ROOT / "registry").vocabulary


def _pipeline():
    """The two-node fixture, materialised. `emit` takes one argument now.

    An empty `Goal`: this fixture starts from a hand-written IR, so there is no goal behind
    it to record, and `goal:` is inert to emission anyway.
    """
    loaded = layers.load(ROOT / "registry")
    return Pipeline.of(
        _ir(), loaded.registry, loaded.vocabulary, loaded.measurements, goal=Goal()
    )


def _registry():
    return layers.load(ROOT / "registry").registry


def _ir():
    return PipelineIR(
        nodes=[
            IRNode(id="trimgalore", contract_id="nf-core/trimgalore@0.6.10"),
            IRNode(
                id="star_align",
                contract_id="nf-core/star/align@1.11.0",
                params={
                    "seq_platform": ResolvedValue(
                        value="illumina", tier=Tier.CONVENTION, reason="contract default"
                    ),
                    # `resolve()` binds *every* declared param; this fixture writes an IR by
                    # hand and so has to as well. `star_ignore_sjdbgtf` became a routed
                    # parameter in Plan 1.14 (A91) — it fills STAR's fourth call slot, and
                    # leaving it unbound is a pipeline that cannot start, which MD0224 says.
                    "star_ignore_sjdbgtf": ResolvedValue(
                        value=False, tier=Tier.CONVENTION, reason="contract default"
                    ),
                },
            ),
        ],
        edges=[
            IREdge(
                from_node="trimgalore",
                from_port="reads",
                to_node="star_align",
                to_port="reads",
                type_id="fastq.reads",
                states=frozenset({"trimmed"}),
            )
        ],
    )


def test_emits_include_statements_for_every_node():
    source = emit(_pipeline())
    assert "include { TRIMGALORE } from './modules/nf-core/trimgalore/main'" in source
    assert "include { STAR_ALIGN } from './modules/nf-core/star/align/main'" in source


def test_emits_workflow_block_wiring_edges():
    source = emit(_pipeline())
    assert "workflow {" in source
    assert "TRIMGALORE(ch_fastq_reads)" in source
    assert "STAR_ALIGN(TRIMGALORE.out.reads" in source


def test_a_resolved_param_no_longer_becomes_a_dead_params_line():
    """This test used to assert the opposite, and asserting it was the bug.

    It required `params.star_align_seq_platform = 'illumina'` in `main.nf` with a tier comment
    above it — a line no module reads. The resolver ran, flagged tier 4, printed REVIEW, and
    the pipeline behaved identically whatever the answer was. Issue #10.

    The value now reaches the tool through `ext.args`, so `main.nf` carries no `params.<node>_`
    line at all and the provenance lives in `pipeline.yml` beside the value.
    """
    source = emit(_pipeline())
    assert "params.star_align_seq_platform" not in source
    assert "// tier " not in source


def test_emission_is_byte_identical_across_runs():
    assert emit(_pipeline()) == emit(_pipeline())


def test_carries_its_intended_purpose_statement():
    """The .nf travels alone. It has to say what it is without the rest of the repo."""
    source = emit(_pipeline())
    assert "It is not a diagnostic" in source
    assert "must be validated by" in source


def test_matches_the_golden_file():
    golden = ROOT / "tests" / "golden" / "spine" / "main.nf"
    assert emit(_pipeline()) == golden.read_text()


def test_the_config_matches_its_golden_file():
    """`nextflow.config` is the second output surface and it had no golden.

    `main.nf` goes through Jinja and looks like output; this file is assembled by f-strings and
    looks like plumbing, which is the same reason root C found it "also injectable" as the
    surface nobody was guarding. A28's `emitted:` digests catch that it *changed*, against what
    a build itself produced. Only a golden catches that it changed *to something wrong*, as a
    diff a person reads before merge — and `ext.args` is where a wrong flag would appear, which
    reaches the tool while every digest stays happy.
    """
    from mendel_compiler.emit import emit_config

    golden = ROOT / "tests" / "golden" / "spine" / "nextflow.config"
    assert emit_config(_pipeline()) == golden.read_text()


def test_the_artifact_never_names_an_output_directory():
    """Where results go is a SITE fact, and the artifact must not decide it.

    `params.outdir` is emitted `null`, exactly as `params.input` is, and Wiener's launcher
    supplies the value through `site.config` — the same posture `process.resourceLimits`
    already takes for how big the machine is (`docs/design/wiener.md` §12).

    **Baking a default here would be cheap and wrong.** `mendel emit` would produce a different
    file per deployment, so `Pipeline.emitted`'s digests would stop reproducing and invariant 10
    would be gone — not loosened, gone. The temptation is real because `outdir = 'results'` is
    what almost every nf-core pipeline ships, which is why this is a test and not a comment.

    **Not even a profile may set it.** A first version gave `stub_data` and `test` a
    `params.outdir` so a gate would publish, which looked harmless and was two things wrong at
    once: it put a destination in the artifact, and it did not even work — `enabled:` is
    evaluated when the `process {` scope is read, which is *before* `profiles {`. The gates pass
    `--outdir` on the command line instead (`gates.py`), so the artifact declares the hole and
    nothing in it fills the hole.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipeline())
    assert "    outdir = null" in config, "the artifact must declare the hole"

    # **Assignments only.** The first version of this checked every line MENTIONING `outdir`
    # and tripped on `publishDir`'s own `path:`, which *reads* `${params.outdir}` — reading the
    # hole is the entire mechanism, and a guard that forbids it forbids the feature.
    assignments = [
        line.strip()
        for line in config.splitlines()
        if re.match(r"\s*(params\.)?outdir\s*=", line)
    ]
    assert assignments == ["outdir = null"], (
        f"the only thing the artifact may say about a destination is that it has none: "
        f"{assignments!r}"
    )


def test_publishing_is_off_when_nobody_said_where():
    """Absent is absent — a null destination publishes nothing, not into a folder called null.

    Without the guard Nextflow interpolates `null` into the path and an un-configured run
    scatters its outputs into a directory named after the absence. Same class of error as a zero
    standing in for a missing measurement, and worse, because it looks like it worked.

    **`enabled` must be an EXPRESSION, and this assertion is that shape rather than the
    behaviour.** It shipped as `enabled: { params.outdir != null }` and published NOTHING with
    all five processes green: Nextflow evaluates `enabled` when it reads the config and never
    calls a closure handed to it, so the closure was merely truthy — no, worse, it silently
    disabled nothing and yet no file appeared. `nextflow config` printed the directive correctly
    and the log said nothing at all. Only looking in `results/` after a stub run found it.

    `path` stays a closure, and must: it is called per task, which is the only way it can read
    `task.process`. The two are different evaluation times in one literal, which is exactly why
    it is worth a test rather than a comment.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipeline())
    # Comment lines are dropped first: the emitted config EXPLAINS this bug in prose, so a scan
    # that cannot tell a directive from the comment above it punishes writing the reason down.
    # `tokens.test.ts` needed the same fix for the same reason on the same day.
    directives = "\n".join(
        line for line in config.splitlines() if not line.lstrip().startswith("//")
    )
    assert "enabled: params.outdir != null," in directives
    assert "enabled: {" not in directives, "a closure here is never called and publishes nothing"
    assert "path:    { " in directives, "path must stay lazy — it reads task.process"


def test_call_arity_follows_the_declared_signature():
    """One contract port is not one process argument, and assuming so emits bad Nextflow.

    star/align declares four inputs for three ports; the one it does not model is a plain
    value.

    The third argument used to be `Channel.value([[:], []])` — an empty tuple where the
    annotation belongs, while `ch_annotation_gtf` sat in the same workflow feeding
    featureCounts. Issue #8. `-stub-run` could never catch it, because nf-core stubs do
    not read their inputs, so the call was as green as a correct one.
    """
    source = emit(_pipeline())
    call = next(line for line in source.splitlines() if "STAR_ALIGN(" in line).strip()
    assert call == (
        "STAR_ALIGN(TRIMGALORE.out.reads, ch_genome_index_star, ch_annotation_gtf, false)"
    ), call


def test_empty_placeholders_match_the_declared_tuple_width():
    """Nextflow matches tuple arity: a 2-tuple handed to a 3-tuple input is a null path."""
    from mendel_compiler.emit import _argument

    pipeline = _pipeline()
    step = next(s for s in pipeline.steps if s.id == "star_align")

    class _Arg:
        empty_width, ports, literal = 3, [], None

    assert _argument(pipeline, step, _Arg()) == (
        "Channel.value([[:], [], []])"
    )


def test_a_none_value_renders_as_null_not_a_string():
    from mendel_compiler.emit import _render_literal

    assert _render_literal(None) == "null"
    assert _render_literal(None) != "'None'"


def test_config_declares_every_entry_parameter_as_null():
    """The pipeline describes a shape; the laboratory supplies the data. Invariant 15."""
    from mendel_compiler.emit import emit_config, entry_params

    config = emit_config(_pipeline())
    for name in entry_params(_pipeline()):
        assert f"{name} = null" in config
    assert "stub_data" in config


def test_a_quote_in_a_value_does_not_break_or_escape_the_literal():
    """Unescaped, "it's fine" is a Groovy syntax error and a crafted value runs code.

    In Plan 2 these values come from a model reading a user's prompt, so this is the
    boundary between goal text and executed Groovy.
    """
    from mendel_compiler.emit import _render_literal

    assert _render_literal("it's fine") == r"'it\'s fine'"
    assert _render_literal(r"a\b") == r"'a\\b'"
    injected = _render_literal("x'; new File('/etc/passwd').text; //")
    assert injected.count("'") == injected.count(r"\'") + 2


def test_a_control_character_is_refused():
    import pytest
    from mendel_compiler.emit import _render_literal

    with pytest.raises(ValueError, match="control character"):
        _render_literal("bad\nvalue")


def test_a_routed_setting_composes_into_ext_args():
    """The whole point of Plan 1.10: a resolved value reaches the tool."""
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipeline())
    assert "withName: STAR_ALIGN" in config
    assert "--outSAMattrRGline" in config


def test_a_template_that_needs_the_task_is_emitted_as_a_closure():
    """Measured on Nextflow 25.10.4: a double-quoted config string fails at parse with
    `Unknown config attribute process.withName:FOO.meta.id`, because a config GString is
    evaluated when the config is read and no task exists then. Only a closure resolves.
    """
    from mendel_compiler.emit import emit_config

    line = next(line for line in emit_config(_pipeline()).splitlines() if "STAR_ALIGN" in line)
    assert "ext.args = {" in line, line


def test_a_static_ext_args_stays_a_plain_string():
    """Regression guard against over-correction.

    A contract's static flags need no task, so wrapping them in a closure would move every
    golden file for nothing. TRIMGALORE carries none, so STAR's is the one to check: its
    static part must survive composition rather than being replaced by the template.
    """
    from mendel_compiler.emit import emit_config

    line = next(line for line in emit_config(_pipeline()).splitlines() if "STAR_ALIGN" in line)
    assert "--readFilesCommand zcat" in line, line


def test_no_dead_params_line_survives():
    """`params.star_align_seq_platform` was read by nothing — issue #10. It is gone."""
    assert "star_align_seq_platform" not in emit(_pipeline())


def test_emission_needs_no_registry():
    """One argument. A published pipeline reproduces without the registry it was built
    against, which is what a laboratory archiving a validated pipeline needs.
    """
    import inspect

    assert list(inspect.signature(emit).parameters) == ["pipeline"]


def test_render_test_data_escapes_like_a_literal():
    """A44: test_data is emitted single-quoted and escaped, not raw double-quoted.

    Called directly with a value the type validator would reject, to prove the emitter is
    belt-and-braces: even a value that reached it would be inert Groovy, not a statement.
    """
    from mendel_compiler.emit import _render_test_data

    assert _render_test_data(["a'b"]) == "'a\\'b'"
    assert _render_test_data(["x", "y"]) == "['x', 'y']"


def test_a_contract_used_by_two_steps_emits_its_process_block_once():
    """A42. `_process_scope` does `sorted(set(blocks))`, so a module wired into two steps emits
    one `withName:` block, not two — byte-identical output requires it, and no test watched the
    dedup. Two identical steps stand in for one contract used twice; the block count must not
    double."""
    import types

    from mendel_compiler.emit import _process_scope

    pipeline = _pipeline()
    step = next(
        s for s in pipeline.steps
        if _process_scope(types.SimpleNamespace(steps=[s])) != []
    )
    one = _process_scope(types.SimpleNamespace(steps=[step]))
    two = _process_scope(types.SimpleNamespace(steps=[step, step]))
    assert two == one, "a process block emitted twice for one contract is a dedup regression"


def test_every_via_member_emits_or_is_refused():
    """A38: a route declared but not emitted is issue #10 reopened.

    Two of three routes shipped validated, recorded with provenance, and emitting nothing. This
    tripwire forces a decision when `Via` grows: a new member must be wired into `emit.py`
    (and added here) or refused at load — never left to record a value that reaches no tool.
    """
    from comeni_core.spell.routes import Via

    # `POSITIONAL` joined in Plan 1.14 and is wired in `_argument`, not in a scope block:
    # it emits into the process *call* rather than into `process { withName: … }`. That is
    # the whole point of the member — a bare `val` has no name at the call site, which is why
    # none of the other three could reach it (A91). This tripwire is what made that a decision
    # rather than an omission, so it is updated deliberately and not widened.
    emitted = {Via.EXT, Via.META, Via.DIRECTIVE, Via.POSITIONAL}
    assert set(Via) == emitted, (
        f"emit.py handles {emitted}; Via also has {set(Via) - emitted}, which would record a "
        "value that reaches no tool. Wire it into emit.py or refuse it at load."
    )


def _step_carrying(setting):
    """A real step from the fixture, carrying one setting instead of its own.

    `model_construct` on the *step* too: `Step`'s own validators are not what is under test,
    and building one field-by-field here would drift from the real shape the moment `Step`
    gains a field.
    """
    step = next(s for s in _pipeline().steps if s.process == "STAR_ALIGN")
    return step.model_construct(
        **{**dict(step), "settings": [setting], "ext_args": ExtArgs.none()}
    )


def test_the_closure_branch_is_unreachable_from_a_raw_value():
    """A55, second layer. `model_construct` skips validators — that is A62, still open — so
    the emitter must not depend on `Setting`'s MD0221 having run. A raw value mentioning
    `${` is refused here too, at the branch that would otherwise make it a closure.
    """
    from comeni_core.artifact.pipeline import Setting, Why
    from comeni_core.plan.tiers import ValueSource
    from comeni_core.spell.routes import ExtKey, Via
    from mendel_compiler.emit import _ext_scope

    smuggled = Setting.model_construct(
        name="seq_platform",
        value="${['sh','-c','id'].execute().text}",
        via=Via.EXT,
        key=ExtKey.PREFIX,
        template=None,
        why=Why(tier=Tier.AMBIGUOUS, source=ValueSource.HUMAN, reason="a round-four probe"),
    )
    with pytest.raises(ValueError, match="MD0221"):
        _ext_scope(_step_carrying(smuggled))


def test_a_templated_fragment_still_emits_a_closure():
    """Regression guard on the fix. STAR's read-group line is
    `--outSAMattrRGline 'ID:${meta.id}' …` — a closure is *correct* there, and it arrives
    through a validated template rather than through a raw value.
    """
    from comeni_core.artifact.pipeline import Setting, Why
    from comeni_core.plan.tiers import ValueSource
    from comeni_core.spell.routes import ExtKey, Via
    from mendel_compiler.emit import _ext_scope

    templated = Setting(
        name="seq_platform",
        value="illumina",
        via=Via.EXT,
        key=ExtKey.ARGS,
        template="--outSAMattrRGline 'ID:${meta.id}' 'PL:{value}'",
        why=Why(tier=Tier.AMBIGUOUS, source=ValueSource.HUMAN, reason="a round-four probe"),
    )
    assert 'ext.args = { "' in "\n".join(_ext_scope(_step_carrying(templated)))


def test_emit_config_cannot_depend_on_a_deployment_target():
    """`docs/design/execution-boundary.md` §6.

    A pipeline emitted for AWS that differs from the same pipeline emitted for a laptop breaks
    invariant 10 (same goal → byte-identical `.nf`) and invariant 13 (self-hosted is not a
    degraded tier) at once, and makes `Pipeline.emitted`'s recorded digests depend on a
    deployment choice — so `mendel emit` could not reproduce the file it is handed.

    **A one-parameter signature cannot express a per-target emission.** That is why this guard
    is on the signature rather than on the output: it fails at the moment somebody reaches for
    the wrong design, not after they have wired it through and a digest has moved.
    """
    import inspect

    from mendel_compiler.emit import emit_config

    params = list(inspect.signature(emit_config).parameters)
    assert params == ["pipeline"], (
        f"emit_config takes {params}. The executor reaches a run through a PROFILE and "
        "`-c site.config`, never through emission — docs/design/execution-boundary.md §6."
    )


def test_the_config_offers_an_executor_for_every_target_the_mvp_names():
    """§7: local, Kubernetes and AWS, and Nextflow abstracts the difference between them.

    Every pipeline gets all three whether or not anyone selects one — exactly as every pipeline
    already gets `docker` and `singularity` blocks it may never use. That is what makes them a
    function of nothing, which is the property the test above defends.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipeline())
    for name in ("local", "k8s", "awsbatch"):
        assert f"    {name} {{" in config, f"no `{name}` profile"
    assert "process.executor = 'awsbatch'" in config


def test_a_profile_that_needs_site_facts_says_so_in_the_file():
    """A `k8s` profile with no storage claim and an `awsbatch` profile with no queue cannot run
    on their own, and a reader must not have to discover that from a Nextflow stack trace.

    §5: the executor, the queue and `workDir` are site facts supplied at run time. The profile
    declares the intent and `-c site.config` completes it — the same division `params.input`
    already makes for data.
    """
    from mendel_compiler.emit import emit_config

    assert "site.config" in emit_config(_pipeline())
