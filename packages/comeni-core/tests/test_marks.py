"""Behavioral checks for marked strings and their boundary-specific validators."""

import pytest
from comeni_core.spell.marks import (
    AnyKey,
    ContractId,
    DiagnosticCode,
    GroovyExpression,
    LayerName,
    Line,
    NfIdentifier,
    NfPath,
    NfTemplate,
    NodeId,
    SpdxId,
    TestDataRef,
    Text,
    TypeId,
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
        "A }\nprintln 'x'",
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
    """Generated-file prose cannot introduce a second statement."""
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
    """A laboratory-defined entry channel is the explicitly marked unbounded exception."""
    arbitrary = "Channel.fromFilePairs(params.input).map { id, reads -> [ [id: id], reads ] }"
    assert _model(GroovyExpression)(value=arbitrary).value == arbitrary


def test_every_new_mark_is_in_the_closed_vocabulary():
    """Public aliases use the shared closed `Mark` vocabulary."""
    from comeni_core.spell.marks import Mark

    for alias in (NfIdentifier, NfPath, GroovyExpression, Line, Text):
        assert any(isinstance(meta, Mark) for meta in alias.__metadata__), alias


# Test-data references reach generated Groovy, so they are validated as well as marked.


@pytest.mark.parametrize(
    "bad",
    [
        'x"; throw new RuntimeException("PWNED"); def z="',
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


# Text around {value} reaches a command line and therefore has a closed grammar.


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


@pytest.mark.parametrize(
    ("alias", "bad"),
    [
        (TypeId, ""),
        (ContractId, "owner/name@1 0"),
        (NodeId, ""),
        (LayerName, ""),
        (DiagnosticCode, "MDAAAA"),
        (SpdxId, ""),
        (AnyKey, "two words"),
    ],
)
def test_closed_string_shapes_reject_invalid_boundary_values(alias, bad):
    """Each public alias rejects a representative value outside its declared grammar."""
    with pytest.raises(ValidationError):
        _model(alias)(value=bad)


def test_nf_template_rejects_an_unterminated_interpolation():
    with pytest.raises(ValidationError, match="MD0204"):
        _model(NfTemplate)(value="--rg ${meta.id")


@pytest.mark.parametrize("good", ["MD0204", "MA0001", "MI9999"])
def test_diagnostic_code_accepts_two_letters_and_four_digits(good):
    assert _model(DiagnosticCode)(value=good).value == good
