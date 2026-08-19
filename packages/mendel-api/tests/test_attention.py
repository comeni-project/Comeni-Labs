"""What needs a person, across both halves.

**Counts and links, never items.** Spec §1: an Overview page was designed and cut once because
it answered the Queue's question, and the discipline that keeps this from becoming that page is
that it never renders a row. These tests hold the shape that makes that possible.
"""

from mendel_api.services import attention
from mendel_api.services.attention import Urgency


def test_it_reports_what_is_open_without_listing_it():
    got = attention.whats_open()
    assert got.forge, "nothing at all is open — this test is measuring nothing"
    for call in got.forge:
        assert call.count >= 0
        assert call.where.startswith("/forge/"), "every call leads to the screen that owns it"
        assert call.what, "a count with no sentence is a number nobody can act on"


def test_the_mendel_half_is_absent_rather_than_zero():
    """Nothing stores pipelines, so there is nothing true to say. *0 pipelines need review*
    would claim that pipelines were looked at — the same falsehood as *0 of 0 emit channels*
    and *0 match their source*, both of which shipped once and were corrected."""
    assert attention.whats_open().mendel == []


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


def test_the_standing_says_what_the_registry_holds():
    """Not what it needs — that is the other half of the page. This is the half that makes a
    front door a place rather than an inbox."""
    standing = attention.whats_open().standing
    assert standing.contracts == 12
    assert standing.types == 22
    assert standing.matching + standing.unverifiable + standing.drifted == standing.contracts
    assert standing.sources == ["nf-core"]


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
