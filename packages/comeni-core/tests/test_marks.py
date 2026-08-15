"""The kinds a declared string may be, and what each one refuses.

Root C: every string the emitter writes is one of five kinds and the codebase distinguished
exactly one. These are the four that now have a type — the fifth, a literal value, already
went through `_render_literal`.

The two rows that catch over-correction are here too: `Text` must still accept newlines,
because `GateFailure.tool_message` exists to carry Nextflow's multi-line stderr, and
`GroovyExpression` must accept anything at all, because `entry_channel` is the designed
exception a laboratory brings its own type through.
"""

import pytest
from comeni_core.spell.marks import (
    GroovyExpression,
    Line,
    NfIdentifier,
    NfPath,
    NfTemplate,
    TestDataRef,
    Text,
)
from pydantic import BaseModel, ValidationError


def _model(alias):
    class Holder(BaseModel):
        value: alias

    return Holder


@pytest.mark.parametrize("good", ["STAR_ALIGN", "_x", "SAMTOOLS_SORT2", "a"])
def test_an_identifier_accepts_what_groovy_accepts(good):
    assert _model(NfIdentifier)(value=good).value == good


@pytest.mark.parametrize(
    "bad",
    [
        "A }\nprintln 'x'",  # A34, verbatim
        "STAR ALIGN",
        "",
        "2FAST",
        "star-align",
        "STAR;RM",
        # Legal in Groovy, refused here: two process names that render identically
        # and are not equal is a bad property for a reviewer's reading to have.
        "STAR_ÄLIGN",
        "ＳＴＡＲ",
    ],
)
def test_an_identifier_refuses_anything_else(bad):
    """No escaping option exists: an identifier is emitted into a declaration."""
    with pytest.raises(ValidationError):
        _model(NfIdentifier)(value=bad)


@pytest.mark.parametrize(
    "good",
    ["modules/nf-core/star/align/main", "./modules/x/main", "main", "a/b.c/d"],
)
def test_a_path_fragment_accepts_a_relative_path(good):
    assert _model(NfPath)(value=good).value == good


@pytest.mark.parametrize(
    "bad", ["/etc/passwd", "../../secrets/main", "a/../b", "a\nb", "~/x", ""]
)
def test_a_path_fragment_refuses_an_escape(bad):
    with pytest.raises(ValidationError):
        _model(NfPath)(value=bad)


def test_a_line_refuses_a_newline():
    """A27 — prose reaching a generated file became a second statement."""
    with pytest.raises(ValidationError):
        _model(Line)(value="a\nprintln 'x'")
    with pytest.raises(ValidationError):
        _model(Line)(value="a\rb")


def test_text_still_accepts_a_newline():
    """The split is by destination, not by prose-ness.

    `GateFailure.tool_message` carries Nextflow's stderr, which is inherently multi-line.
    A blanket control-character ban on `Text` would have broken the one field the rule was
    proposed to protect.
    """
    assert _model(Text)(value="line one\nline two\n").value == "line one\nline two\n"


def test_a_groovy_expression_is_unbounded_on_purpose():
    """`entry_channel` is the designed exception, and marking it says so out loud.

    The compiler has no built-in idea what a FASTQ is; a lab bringing its own type declares
    how it arrives. Root B makes replacing one *visible* (A24) rather than forbidding it.
    """
    arbitrary = "Channel.fromFilePairs(params.input).map { id, reads -> [ [id: id], reads ] }"
    assert _model(GroovyExpression)(value=arbitrary).value == arbitrary


def test_every_new_mark_is_in_the_closed_vocabulary():
    """Root A and root C share one `Mark` enum. New markers join it; they are not minted."""
    from comeni_core.spell.marks import Mark

    for alias in (NfIdentifier, NfPath, GroovyExpression, Line, Text):
        assert any(isinstance(meta, Mark) for meta in alias.__metadata__), alias


# --- A44: test_data reaches generated Groovy, so it is validated, not merely marked ---


@pytest.mark.parametrize(
    "bad",
    [
        'x"; throw new RuntimeException("PWNED"); def z="',  # the audit's payload
        "x'; println 'y",
        "a`id`b",
        "a${System.env}b",
        "line1\nline2",
    ],
)
def test_test_data_ref_rejects_an_injection(bad):
    with pytest.raises(ValidationError):
        _model(TestDataRef)(value=bad)


@pytest.mark.parametrize(
    "good",
    [
        "https://raw.githubusercontent.com/nf-core/test-datasets/72a702d/reference/genes.gtf",
        "s3://a-lab-bucket/reference/genome.fasta",  # scheme is the lab's call, not ours
    ],
)
def test_test_data_ref_accepts_a_reference(good):
    assert _model(TestDataRef)(value=good).value == good


# --- A45: the text around {value} is emitted into a command line, so it has a grammar ---


@pytest.mark.parametrize(
    "bad",
    [
        "-Q {value}; touch /tmp/OWNED #",              # shell path — no quotes or ${}
        '-Q {value}"${new File("/tmp/x").text="y"}"',  # Groovy closure path
        "-Q {value}`id`",                              # backtick
        "-Q {value} | cat",                            # pipe
        "--x ${System.env}",                           # ${} that is not meta/task
        "--x $meta.id",                                # bare $ interpolation
        "--x {value}\n--y",                            # newline
    ],
)
def test_nf_template_rejects_injection(bad):
    with pytest.raises(ValidationError):
        _model(NfTemplate)(value=bad)


@pytest.mark.parametrize(
    "good",
    [
        "-Q {value}",
        "--rg-id ${meta.id} --rg SM:${meta.id} --rg PL:{value}",
        "--outSAMattrRGline 'ID:${meta.id}' 'SM:${meta.id}' 'PL:{value}'",
        "--cpus ${task.cpus}",
    ],
)
def test_nf_template_allows_value_meta_task_and_quotes(good):
    assert _model(NfTemplate)(value=good).value == good
