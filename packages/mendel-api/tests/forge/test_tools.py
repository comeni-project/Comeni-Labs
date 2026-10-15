"""Sources and Contracts were one query at two stages of one object's life.

Both screens carried a `Facets` component with the same docstring, written twice, and nobody
noticed what that was saying. A tool moves **undrafted -> drafted -> landed**, and `status` —
does it still agree with its source — is a property of the last stage only.

Spec §1.3 and §3.
"""

from mendel_api.services import tools


def test_a_landed_tool_carries_its_status_and_its_ports() -> None:
    board = tools.board()
    landed = [row for row in board.rows if row.state == "landed"]
    assert landed, "the registry has twelve contracts"
    row = landed[0]
    assert row.status is not None, "a landed tool has been checked, or is unverifiable"
    # **The field the old row omitted.** `status | id | roles` spent 180px on `roles`, which
    # helps nobody choose a tool; what it consumes and produces is what a decision needs.
    assert row.consumes or row.produces


def test_an_undrafted_tool_has_no_status() -> None:
    undrafted = [row for row in tools.board().rows if row.state == "undrafted"]
    assert undrafted, "no tool is undrafted — the rule below was never exercised"
    for row in undrafted:
        assert row.status is None, "nothing was checked, so nothing may claim a status"
        assert not row.consumes and not row.produces, "nothing declares its ports yet"


def test_the_known_total_is_absent_rather_than_wrong() -> None:
    """Issue #77 — discovery reads `vendor/modules/`, so the size of the known world is unknown.

    `13` presented as that size is a lie; `None` renders `—`. The same discipline as
    `pipeline_pins: None` and `Pipeline.ai.available: []` — an absence is not a zero.
    """
    assert tools.board().known is None


def test_counts_are_over_everything_not_the_filtered_view() -> None:
    everything = tools.board()
    filtered = tools.board(state="landed")
    assert filtered.counts == everything.counts
    assert filtered.status_counts == everything.status_counts
    assert len(filtered.rows) < len(everything.rows)


def test_a_landed_contract_appears_even_if_no_source_can_discover_it() -> None:
    """**The join is a union, not a lookup.**

    `sources.catalogue()` iterates what a source can *discover*, so composing the board by
    walking that list would silently drop any contract whose module is not in `vendor/` — a
    hand-written contract, or one whose module was removed upstream. Those are exactly the
    contracts a person most needs to see, because nothing can re-read them.
    """
    board = tools.board()
    landed_on_board = {row.contract_id for row in board.rows if row.state == "landed"}
    from mendel_api.services import registry

    assert landed_on_board == {c.id for c in registry.stack().registry.all()}
