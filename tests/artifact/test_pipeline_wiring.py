"""Saved-pipeline wiring: observable CLI and artifact behavior."""

from mendel_compiler.cli import main
from support.paths import ROOT
from support.pipeline import (
    GOAL,
    _answer,
    _build,
    _build_with_overlay,
    _declared,
    _emit,
    _load,
    _overlay_with,
)


def test_answering_a_tier_four_question_in_the_file_reaches_the_tool(tmp_path, capsys):
    """The point of the whole file, in one test.

    `seq_platform` is tier 4 and nothing answered it, so the shipped spine emits STAR's
    `ext.args` without a read-group line. Answer it by editing `pipeline.yml`, re-emit, and
    the answer arrives on the command line — **with no registry, no vocabulary and no
    resolution.** Before this it was issue #10: the resolver ran, printed REVIEW, and the
    pipeline behaved identically whatever anyone answered.

    The plan had this as a refusal — `MD0213`, "you edited it". That is backwards: `emit` is
    the verb that *cures* staleness, and refusing here would mean the file a reader is told to
    edit can never be edited. Corrected during Task 6.
    """
    out = _build(tmp_path)
    assert "outSAMattrRGline" not in (out / "nextflow.config").read_text()
    _answer(out, "seq_platform", "nanopore")
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert "'PL:nanopore'" in (out / "nextflow.config").read_text()


# Regression evidence: A38
def test_via_directive_reaches_nextflow_config(tmp_path):
    ov = _overlay_with(tmp_path, "  - {name: cpus, default: 7, via: directive}\n")
    out = _build_with_overlay(tmp_path, ov)
    assert "cpus = 7" in (out / "nextflow.config").read_text()


# Regression evidence: A38
def test_via_meta_reaches_the_channel_meta_map(tmp_path):
    """A38, with a legal key since Plan 1.14.

    This used to route an invented `tag`, which `MD0108`'s meta arm now refuses — a param in
    `meta` that the module never reads is the deadness issue #10 was about, and is exactly
    where A91 hid. featureCounts reads `id`, `single_end` and `strandedness`, so the route
    has to name one of those; `single_end` is free only when the goal states no `paired`
    measurement, which is what this goal does.
    """
    goal = tmp_path / "goal.yml"
    paired = "    - {measurement: paired, value: true, source: said}\n"
    example = (ROOT / "examples" / "rnaseq.yml").read_text()
    assert paired in example, "the example states `paired`; this test removes it"
    goal.write_text(_declared(goal, example.replace(paired, "")))
    ov = _overlay_with(tmp_path, "  - {name: single_end, default: false, via: meta}\n")
    out = tmp_path / "b"
    assert (
        main(
            [
                "build",
                str(goal),
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
    assert "single_end: false" in (out / "main.nf").read_text()


# Regression evidence: A42, A42
def test_ext_args_fragments_emit_name_sorted_whatever_the_setting_order(tmp_path):
    """The property the emitter's own docstring predicted no test could see: `_ext_scope`
    composes `key: args` fragments in **name-sorted** order, so emission is byte-identical
    however the settings arrive. Materialisation already sorts them, which is why an end-to-end
    build cannot watch this — so the step's settings are reversed by hand and `_ext_scope` must
    still emit `--alpha` before `--zulu`. Reverting the sort in `_ext_scope` fails this."""
    from mendel_compiler.emit import _ext_scope

    ov = _overlay_with(
        tmp_path,
        '  - {name: zulu, default: 1, via: ext, key: args, template: "--zulu {value}"}\n'
        '  - {name: alpha, default: 2, via: ext, key: args, template: "--alpha {value}"}\n',
    )
    out = _build_with_overlay(tmp_path, ov)
    step = next(s for s in _load(out).steps if "FEATURECOUNTS" in s.process)
    reversed_step = step.model_copy(update={"settings": list(reversed(step.settings))})
    argline = next(line for line in _ext_scope(reversed_step) if "ext.args" in line)
    assert argline.index("--alpha") < argline.index("--zulu"), "name-sorted, not setting order"


# Regression evidence: A40
def test_two_ext_args_settings_still_compose(tmp_path):
    """The exemption: args/args2/args3 are designed to concatenate, so two is not a collision."""
    ov = _overlay_with(
        tmp_path,
        '  - {name: a, default: 1, via: ext, key: args, template: "--a {value}"}\n'
        '  - {name: b, default: 2, via: ext, key: args, template: "--b {value}"}\n',
    )
    out = tmp_path / "b"
    assert (
        main(
            [
                "build",
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


# Regression evidence: A39
# --- A39: a non-templated ext key is quoted once, not twice ---
def test_a_non_templated_ext_key_is_quoted_once(tmp_path):
    """`prefix` takes one value and has no template, so _render_literal must run once.

    It ran twice — per fragment and again on the join — so `alpha` emitted as `'\\'alpha\\''`,
    a Groovy string whose value includes the quote characters, corrupting every output filename.
    """
    ov = _overlay_with(tmp_path, "  - {name: tag, default: alpha, via: ext, key: prefix}\n")
    out = _build_with_overlay(tmp_path, ov)
    cfg = (out / "nextflow.config").read_text()
    assert "ext.prefix = 'alpha'" in cfg
    assert "\\'alpha\\'" not in cfg
