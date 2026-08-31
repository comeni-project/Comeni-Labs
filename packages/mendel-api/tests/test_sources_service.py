"""What each source can read, and what has been done with each tool.

The list is the easy half. The second column is the screen: a bare list of thirteen names is a
directory listing, and *what can I start?* is the question a curator actually has.
"""

from mendel_api.services import sources
from mendel_api.services.sources import State


def test_the_three_states_partition_what_can_be_read():
    got = sources.catalogue()
    assert got.rows, "discovery found nothing — the source root is wrong"
    assert sum(got.counts.values()) == len(got.rows)


def test_a_tool_the_registry_has_is_landed():
    got = sources.catalogue()
    landed = {r.ref for r in got.rows if r.state is State.LANDED}
    assert "nf-core:fastqc" in landed
    row = next(r for r in got.rows if r.ref == "nf-core:fastqc")
    assert row.contract_id == "nf-core/fastqc@0.12.1"


def test_a_vendored_tool_with_no_contract_is_undrafted():
    """Measured: three of the thirteen vendored modules have no contract. If this ever returns
    nothing, the screen has no content and the exit criterion cannot be run."""
    got = sources.catalogue()
    undrafted = {r.ref for r in got.rows if r.state is State.UNDRAFTED}
    assert "nf-core:samtools/faidx" in undrafted


def test_drafted_is_derived_from_the_drafts_id_not_from_its_name(monkeypatch, tmp_path):
    """A draft called `mydraft` for `samtools/faidx` must show against that tool. The name is a
    label the person chose; `filled["id"]` is what the draft is *about*."""
    from mendel_api.settings import settings
    from mendel_forge import ops

    monkeypatch.setattr(settings, "workspace_root", tmp_path / "workspace")
    ops.draft(
        ops.DraftRequest(
            ref="nf-core:samtools/faidx",
            name="mydraft",
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
            workspace_root=tmp_path / "workspace",
            version="1.24",
        )
    )

    row = next(r for r in sources.catalogue().rows if r.ref == "nf-core:samtools/faidx")
    assert row.state is State.DRAFTED
    assert row.draft == "mydraft"


def test_a_landed_tool_stays_landed_even_with_a_draft_open(monkeypatch, tmp_path):
    """The half that must fail otherwise: `landed` outranks `drafted`, because a contract in
    the registry is what a pipeline resolves to whatever else is open."""
    from mendel_api.settings import settings
    from mendel_forge import ops

    monkeypatch.setattr(settings, "workspace_root", tmp_path / "workspace")
    ops.draft(
        ops.DraftRequest(
            ref="nf-core:fastqc",
            name="fastqc-again",
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
            workspace_root=tmp_path / "workspace",
            version="0.13.0",
        )
    )

    row = next(r for r in sources.catalogue().rows if r.ref == "nf-core:fastqc")
    assert row.state is State.LANDED


def test_filtering_narrows_the_rows_and_not_the_counts():
    everything = sources.catalogue()
    only = sources.catalogue(state=State.UNDRAFTED)
    assert only.rows, "nothing is undrafted — the fixture registry has changed"
    assert all(r.state is State.UNDRAFTED for r in only.rows)
    assert only.counts == everything.counts


def test_undrafted_sorts_first():
    """Worst first, the same argument as the queue and the contracts list: what needs doing
    goes at the top."""
    rows = sources.catalogue().rows
    assert rows[0].state is State.UNDRAFTED
