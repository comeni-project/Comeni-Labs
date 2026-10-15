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


def test_each_revisions_candidate_survives_the_next(tmp_path, complete_scaffold):
    """Issue 280: `draft.json` is the working candidate and the next generation overwrites it,
    while `ForgeRevision` promises the superseded candidate survives. Each is kept per revision."""
    workspace = Workspace(root=tmp_path)
    for revision, module in (("r1", "process ONE {}\n"), ("r2", "process TWO {}\n")):
        workspace.write_draft(Draft(name="a1", scaffold=complete_scaffold, module=module))
        workspace.keep_revision("a1", revision)

    assert workspace.read_revision("a1", "r1").module == "process ONE {}\n"
    assert workspace.read_revision("a1", "r2").module == "process TWO {}\n"
    assert workspace.read_draft("a1").module == "process TWO {}\n"


def test_a_kept_revision_is_never_overwritten(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    workspace.write_draft(Draft(name="a1", scaffold=complete_scaffold, module="process A {}\n"))
    workspace.keep_revision("a1", "r1")
    workspace.write_draft(Draft(name="a1", scaffold=complete_scaffold, module="process B {}\n"))
    with pytest.raises(ValueError, match="MF0012"):
        workspace.keep_revision("a1", "r1")
    assert workspace.read_revision("a1", "r1").module == "process A {}\n"


def test_a_revision_id_cannot_escape_the_workspace(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    workspace.write_draft(Draft(name="a1", scaffold=complete_scaffold, module=None))
    with pytest.raises(ValueError, match="MF0008"):
        workspace.keep_revision("a1", "../../escape")
