"""What needs a person, across both halves.

**Counts and links, never items.** Spec §1: an Overview page was designed and cut once because
it answered the Queue's question, and the discipline that keeps this from becoming that page is
that it never renders a row. These tests hold the shape that makes that possible.
"""

from datetime import UTC, datetime

from mendel_api.services import attention, drafts
from mendel_api.services.attention import Urgency


def test_it_points_at_a_screen_and_never_at_a_registry_subject():
    """**Restated, not deleted** — Plan 4 phase 2, and `ov-settled` says to do exactly that.

    This asserted that `/` *counts and links and never renders an item*, which is the discipline
    `forge-review.md` §3 demanded: an Overview page was designed and CUT once for answering the
    same question as the forge Queue, and rendering one row here was how that decision would get
    undone by forgetting it.

    **The operator has ruled that constraint dead.** The page renders items now — pipelines and
    runs. So the rule narrows to the part that is still true and still worth keeping: it may
    never render a *registry* subject. A contract id, a question subject or a drift row on this
    page is the moment it has become the Queue a second time.
    """
    got = attention.whats_open()
    assert got.forge, "nothing at all is open — this test is measuring nothing"
    for call in got.forge:
        assert call.count >= 0
        assert call.what, "a count with no sentence is a number nobody can act on"
        assert call.where.startswith("/forge/"), "every call leads to the screen that owns it"
        # The narrowed rule: a call names a SCREEN and a filter, never a subject.
        assert "@" not in call.where, "a contract id in the link is a registry item on the page"


def test_the_mendel_half_reports_the_lab_s_own_pipelines(monkeypatch):
    """**This test asserted `mendel == []` and its docstring said "nothing stores pipelines".**

    That had been false since Plan 3E — drafts have been rows in Postgres since the builder
    became a builder, and nobody came back to the sentence. It is the drift `CLAUDE.md` warns
    about in prose that has no counter behind it, caught here by needing the field.

    **The rows are supplied rather than read.** Its second version looped over
    `whats_open().mendel`, which is `[]` on any machine without Postgres — so every assertion
    below sat inside an empty loop and the test passed by measuring nothing, on CI and on a
    developer machine with the stack down. `_waiting_on_a_person` degrades to `[]` by design
    (A192), and a test of what it *says* must not also be a test of whether a database is up:
    `test_the_page_survives_an_unreachable_store` below is that one.
    """
    rows = [
        _row("a1b2c3d4e5", "rnaseq", open_values=[("star_align", "strandedness")]),
        _row("f6a7b8c9d0", "", open_values=[("star_align", "strandedness"),
                                            ("featurecounts", "fragment_size")]),
        _row("0d9c8b7a6f", "capped", open_values=[("star_align", "strandedness")], more=3),
        _row("1122334455", "settled"),
    ]
    monkeypatch.setattr(drafts, "list_drafts", lambda **_: (rows, len(rows)))

    calls = attention.whats_open().mendel
    assert len(calls) == 3, "a pipeline with nothing open is not a call for anybody"
    for call in calls:
        assert call.urgency is Urgency.WAITING, "an open value holds somebody up; it breaks nothing"
        assert call.where.startswith("/build"), "it leads to the page that can answer it"
        assert not call.what.endswith("items"), (
            "waiting on a person NAMES the values — a count is what you write when you have "
            "not looked"
        )
        assert "strandedness" in call.what, "it names the value, and this is that assertion"
    named, plural, capped = calls
    assert named.what == "rnaseq: strandedness has no rule"
    assert plural.what == "f6a7b8c9: strandedness, fragment_size have no rule", (
        "an unnamed pipeline falls back to a short id, and two values take a plural verb"
    )
    assert capped.what.endswith("and 3 more have no rule") and capped.count == 4, (
        "a cap must not read as the total — `open_not_named` is counted, not dropped"
    )


def test_the_page_survives_an_unreachable_store(monkeypatch):
    """A192, on this half: the front door must not go blank because Postgres is down. The forge
    half reads files and the mendel half reads rows, so one failing may not take the other."""
    def _down(**_):
        raise RuntimeError("could not connect")

    monkeypatch.setattr(drafts, "list_drafts", _down)
    got = attention.whats_open()
    assert got.mendel == []
    assert got.forge, "the half that still works is still reported"


def _row(id: str, name: str, *, open_values=(), more: int = 0) -> drafts.DraftRow:
    return drafts.DraftRow(
        id=id,
        name=name,
        who="a-curator",
        updated_at=datetime(2026, 9, 2, tzinfo=UTC),
        steps=4,
        kept=True,
        open_values=[drafts.OpenValue(step=step, setting=setting)
                     for step, setting in open_values],
        open_not_named=more,
    )


def test_drift_outranks_an_undrafted_tool():
    """Drift breaks pipelines that already run; an undrafted tool is an opportunity. The
    landing page sorts by the same consequence order the queue does.

    `rank` is **declared, not derived from the member order** — the fourth time this project
    has needed that note, after `Band.rank` shipped alphabetical.
    """
    assert Urgency.BLOCKING.rank < Urgency.WAITING.rank < Urgency.IDLE.rank


def test_the_calls_come_back_worst_first():
    got = attention.whats_open()
    ranks = [call.urgency.rank for call in got.forge]
    assert ranks == sorted(ranks), f"not in consequence order: {ranks}"


def test_the_front_door_does_not_report_the_registry_s_inventory():
    """**Deleted deliberately, and this is what replaced it.**

    `test_the_standing_says_what_the_registry_holds` asserted 12 contracts, 22 types and one
    source, and defended the block as *the half a dashboard usually omits*. `ov-settled` is the
    counter-argument and the operator's ruling: that is the PRODUCT's state, not YOURS, and it
    is why the old page read as slop — information with no question behind it.

    An assertion that the field is gone, rather than no assertion at all, because the block is
    exactly the kind of thing that comes back when somebody wants the page to look fuller.
    """
    assert not hasattr(attention.whats_open(), "standing")
    assert not hasattr(attention, "Standing")


def test_an_undrafted_tool_is_an_invitation_not_a_warning():
    """Measured: three vendored tools have no contract. The page offers them as available work
    rather than as a deficiency, which is what `idle` means."""
    # **Matched on `state=undrafted`, not on the screen's name.** This said `"sources" in
    # call.where` and broke the moment Plan 3D pointed the link at `/forge/tools` — correctly,
    # because a test keyed on a URL is testing the router. What it means is *the undrafted call
    # is idle*, and `state=undrafted` is the part of the link that says which call it is.
    got = attention.whats_open()
    undrafted = [call for call in got.forge if "state=undrafted" in call.where]
    assert undrafted, "nothing is undrafted — this test is now vacuous"
    assert all(call.urgency is Urgency.IDLE for call in undrafted)
    # And it points somewhere that keeps the filter. `<Navigate>` on the old path replaces the
    # whole location with a fixed query, so a link through the redirect silently loses it.
    assert all(call.where.startswith("/forge/tools") for call in undrafted)


def test_nothing_open_is_a_state_it_can_report():
    """Today's real screen: 0 open questions and 0 drift. A page whose empty state is the one
    that ships had better be able to say so — and `whats_open()` reporting an empty `forge`
    list is how the screen knows to render it."""
    got = attention.whats_open()
    blocking = [call for call in got.forge if call.urgency is Urgency.BLOCKING]
    assert blocking == [], "the shipped registry has drift — the empty state is not reachable"


def test_the_front_door_survives_a_store_it_cannot_reach(monkeypatch):
    """**A192's argument, on the other half of the product.**

    `/overview` was required to degrade where `/graph` 404s, because *a 404 on the default view
    turns a readable run into a blank page*. The same holds here and the failure modes differ:
    the forge half reads FILES and the mendel half reads ROWS, so the one that can be
    unavailable must not take the other down with it.

    This is also why `whats_open()` stays testable in CI, which has no Postgres — a consequence
    rather than the reason.
    """
    from mendel_api.services import drafts

    def unreachable(**kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(drafts, "list_drafts", unreachable)

    got = attention.whats_open()
    assert got.mendel == [], "an unreachable store reports nothing, rather than raising"
    assert got.forge, "the half that reads files must still answer"
