# packages/comeni-core/tests/test_tools.py
"""The `tool` kind: what a tool is, in one file beside its contracts (#216).

Stacked like every kind (invariant 11): an overlay may describe a tool the base lacks, or
replace the base's description. One tool per file, `declares: tool`.
"""

import pytest
from comeni_core.declared.tools import Tool, ToolCatalogue
from pydantic import ValidationError


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


SAMTOOLS = (
    "declares: tool\nid: nf-core/samtools\nname: SAMtools\n"
    "description: Reads, writes, sorts and indexes alignments.\n"
    "homepage: https://www.htslib.org\n"
)


def test_a_tool_file_loads_keyed_on_its_id(tmp_path):
    _write(tmp_path, "tools/nf-core/samtools/tool.yml", SAMTOOLS)
    catalogue = ToolCatalogue.load(tmp_path)
    assert list(catalogue.tools) == ["nf-core/samtools"]
    assert catalogue.tools["nf-core/samtools"].name == "SAMtools"


def test_a_higher_layer_replaces_a_description(tmp_path):
    base, lab = tmp_path / "base", tmp_path / "lab"
    _write(base, "tools/nf-core/samtools/tool.yml", SAMTOOLS)
    _write(lab, "samtools.yml", SAMTOOLS.replace("Reads, writes", "Our lab's samtools; reads"))
    catalogue = ToolCatalogue.load([base, lab])
    assert catalogue.tools["nf-core/samtools"].description.startswith("Our lab's")


@pytest.mark.parametrize("missing", ["id", "name", "description"])
def test_a_tool_says_what_it_is_or_fails(missing):
    fields = {"id": "nf-core/x", "name": "X", "description": "Does x."}
    del fields[missing]
    with pytest.raises(ValidationError):
        Tool.model_validate(fields)


def test_an_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        Tool.model_validate({"id": "a/b", "name": "B", "description": "d.", "licence": "MIT"})
