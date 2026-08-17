import pytest
from mendel_forge.workspace import Draft, Workspace


def test_a_draft_round_trips_byte_identically(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    path = workspace.save(Draft(name="fastqc", scaffold=complete_scaffold, module=None))
    first = path.read_text()
    workspace.save(workspace.load("fastqc"))
    assert path.read_text() == first, "save(load(x)) must not move a byte"


def test_names_are_sorted(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    for name in ("zebra", "alpha"):
        workspace.save(Draft(name=name, scaffold=complete_scaffold, module=None))
    assert workspace.names() == ["alpha", "zebra"]


def test_loading_an_absent_draft_names_the_ones_that_exist(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    workspace.save(Draft(name="fastqc", scaffold=complete_scaffold, module=None))
    with pytest.raises(ValueError, match="MF0008") as caught:
        workspace.load("multiqc")
    assert "fastqc" in str(caught.value)


def test_a_draft_carrying_a_generated_module_keeps_it(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    workspace.save(Draft(name="widget", scaffold=complete_scaffold, module="process WIDGET {}\n"))
    assert workspace.load("widget").module == "process WIDGET {}\n"


def test_a_draft_name_cannot_escape_the_workspace(tmp_path, complete_scaffold):
    """A name reaching the filesystem is a name that can contain `../`."""
    workspace = Workspace(root=tmp_path)
    with pytest.raises(ValueError, match="MF0008"):
        workspace.save(Draft(name="../escape", scaffold=complete_scaffold, module=None))
