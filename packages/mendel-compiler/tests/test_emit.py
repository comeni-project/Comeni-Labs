import pathlib

import pytest
from comeni_core.goal import Goal
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.pipeline import Pipeline
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
                    )
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
    from comeni_core.routes import Via

    emitted = {Via.EXT, Via.META, Via.DIRECTIVE}
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
    return step.model_construct(**{**dict(step), "settings": [setting], "ext_args": None})


def test_the_closure_branch_is_unreachable_from_a_raw_value():
    """A55, second layer. `model_construct` skips validators — that is A62, still open — so
    the emitter must not depend on `Setting`'s MD0221 having run. A raw value mentioning
    `${` is refused here too, at the branch that would otherwise make it a closure.
    """
    from comeni_core.pipeline import Setting, Why
    from comeni_core.routes import ExtKey, Via
    from comeni_core.tiers import ValueSource
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
    from comeni_core.pipeline import Setting, Why
    from comeni_core.routes import ExtKey, Via
    from comeni_core.tiers import ValueSource
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
