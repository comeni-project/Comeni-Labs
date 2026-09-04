"""Prompt templates: loaded by versioned id, rendered by exact substitution, digested.

The point of this module is that a stored review record naming `forge.analysis.v1` can reach
the text that was actually sent. Every test here is about one of the ways that stops being
true — an id with no version, a template that moved, a placeholder nobody filled.
"""

import pytest
from comeni_ai.prompts import PromptTemplate, UnknownPromptError


def _write(tmp_path, name: str, body: str):
    (tmp_path / name).write_text(body)
    return tmp_path


def test_a_template_loads_by_id_and_keeps_it(tmp_path) -> None:
    _write(tmp_path, "forge.analysis.v1.md", "Hello {{who}}")
    template = PromptTemplate.load(tmp_path, "forge.analysis.v1")
    assert template.prompt_id == "forge.analysis.v1"
    assert template.body == "Hello {{who}}"


def test_an_unversioned_id_is_refused(tmp_path) -> None:
    """The file may exist; the id is still not citable."""
    _write(tmp_path, "forge.analysis.md", "x")
    with pytest.raises(UnknownPromptError, match="MA0008"):
        PromptTemplate.load(tmp_path, "forge.analysis")


def test_a_missing_template_names_what_is_there(tmp_path) -> None:
    _write(tmp_path, "forge.analysis.v1.md", "x")
    with pytest.raises(UnknownPromptError) as raised:
        PromptTemplate.load(tmp_path, "forge.repair.v1")
    assert "forge.analysis.v1" in str(raised.value)


def test_a_missing_directory_refuses_rather_than_raising_oserror(tmp_path) -> None:
    with pytest.raises(UnknownPromptError, match="MA0008"):
        PromptTemplate.load(tmp_path / "nothing", "forge.analysis.v1")


def test_rendering_substitutes_every_placeholder(tmp_path) -> None:
    _write(tmp_path, "a.v1.md", "one {{first}} two {{ second }} {{first}}")
    rendered = PromptTemplate.load(tmp_path, "a.v1").render({"first": "A", "second": "B"})
    assert rendered.text == "one A two B A"


def test_a_missing_value_is_refused(tmp_path) -> None:
    """Otherwise the literal `{{dossier}}` reaches the provider."""
    _write(tmp_path, "a.v1.md", "{{first}} {{second}}")
    with pytest.raises(UnknownPromptError) as raised:
        PromptTemplate.load(tmp_path, "a.v1").render({"first": "A"})
    assert "second" in str(raised.value)


def test_a_surplus_value_is_refused(tmp_path) -> None:
    """The quiet one: the caller assembled a dossier and passed it under a key nothing reads,
    so the model answered with no evidence and looked weak rather than unfed."""
    _write(tmp_path, "a.v1.md", "{{first}}")
    with pytest.raises(UnknownPromptError) as raised:
        PromptTemplate.load(tmp_path, "a.v1").render({"first": "A", "dossier": "B"})
    assert "dossier" in str(raised.value)


def test_braces_in_a_value_are_not_re_substituted(tmp_path) -> None:
    """A dossier carries JSON Schema, which is full of braces. `str.format` would have raised
    on the first one; a value that happens to contain `{{x}}` must survive as text."""
    _write(tmp_path, "a.v1.md", "schema: {{schema}}")
    rendered = PromptTemplate.load(tmp_path, "a.v1").render(
        {"schema": '{"type": "object", "note": "{{first}}"}'}
    )
    assert rendered.text == 'schema: {"type": "object", "note": "{{first}}"}'


def test_the_digest_is_of_the_rendered_text_not_the_template(tmp_path) -> None:
    """Two adaptations share a template and must not share an invocation record."""
    _write(tmp_path, "a.v1.md", "{{who}}")
    template = PromptTemplate.load(tmp_path, "a.v1")
    first = template.render({"who": "fastqc"})
    second = template.render({"who": "samtools"})
    assert first.digest != second.digest
    assert first.prompt_id == second.prompt_id


def test_the_digest_is_stable_across_renders(tmp_path) -> None:
    """The property a stored digest depends on: re-rendering the same inputs compares equal."""
    _write(tmp_path, "a.v1.md", "{{who}}")
    template = PromptTemplate.load(tmp_path, "a.v1")
    assert template.render({"who": "x"}).digest == template.render({"who": "x"}).digest


def test_a_template_with_no_placeholders_renders_with_no_values(tmp_path) -> None:
    _write(tmp_path, "a.v1.md", "a fixed instruction")
    assert PromptTemplate.load(tmp_path, "a.v1").render({}).text == "a fixed instruction"


def test_placeholders_are_reported(tmp_path) -> None:
    """What a caller asks before assembling: which keys does this version want."""
    _write(tmp_path, "a.v1.md", "{{one}} {{two}} {{one}}")
    assert PromptTemplate.load(tmp_path, "a.v1").placeholders() == {"one", "two"}
