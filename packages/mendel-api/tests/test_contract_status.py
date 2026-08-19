"""How a contract stands against the module it claims to describe.

Three statuses and every contract has exactly one. `unverifiable` is present because a
contract nothing could re-read is neither drifted nor agreeing — `CheckResult.skipped`'s own
docstring says a contract nothing checks looks exactly like a contract that agrees, and slice
1 shipped that confusion once.
"""

from mendel_api.services import contracts
from mendel_api.services.contracts import Status


def test_the_three_statuses_partition_the_registry():
    """**The assertion this file exists for.** If they ever stop adding up, some contract is
    being counted twice or not at all, and the facet counts become a claim nobody checked."""
    listing = contracts.listing()

    assert listing.total > 0, "the registry must be non-empty for this to mean anything"
    assert sum(listing.counts.values()) == listing.total
    assert len(listing.rows) == listing.total


def test_the_comeni_contracts_are_unverifiable_rather_than_matching():
    """Measured: `ops.check` reports two `comeni/` contracts skipped, because no registered
    source can re-read them. Folding them into `matching` is the defect slice 1 shipped."""
    listing = contracts.listing()
    unverifiable = {r.id for r in listing.rows if r.status is Status.UNVERIFIABLE}

    assert unverifiable, "this registry has contracts no source can check"
    assert all(id.startswith("comeni/") for id in unverifiable)


def test_filtering_narrows_the_rows_and_not_the_counts():
    """The facet counts describe the registry, not the filtered view — otherwise the facet
    you are standing in reads 12 and the others read 0."""
    everything = contracts.listing()
    only = contracts.listing(against=Status.UNVERIFIABLE)

    assert all(r.status is Status.UNVERIFIABLE for r in only.rows)
    assert only.counts == everything.counts
    assert only.total == everything.total


def test_drifted_sorts_first_then_unverifiable_then_matching():
    """Worst first, the same argument as the queue's consequence order. Asserted on the rank
    sequence rather than on ids, so it holds when the registry changes."""
    rows = contracts.listing().rows
    ranks = [r.status.rank for r in rows]

    assert ranks == sorted(ranks), f"not worst-first: {[r.status.value for r in rows]}"


def test_a_role_filter_uses_the_declared_roles():
    listing = contracts.listing()
    a_role = next(r.roles[0] for r in listing.rows if r.roles)
    only = contracts.listing(role=a_role)

    assert only.rows
    assert all(a_role in r.roles for r in only.rows)


def test_the_check_is_cached_on_the_registry_digest(monkeypatch):
    """0.40s per request is fine once and not fine per keystroke. Keyed on the digest so a
    changed registry invalidates it — a time-based cache would serve a stale answer for
    exactly as long as it was wrong."""
    calls = []
    real = contracts.ops.check

    def counted(req):
        calls.append(req)
        return real(req)

    monkeypatch.setattr(contracts.ops, "check", counted)
    contracts._checked.cache_clear()

    contracts.listing()
    contracts.listing()

    assert len(calls) == 1, "the second call must come from the cache"


def test_a_conformance_failure_is_drift(monkeypatch, broken_registry_copy):
    """A contract that no longer describes its module is DRIFTED, whichever checker noticed.

    Same class of falsehood as folding `skipped` into `matching`, one checker over — the
    reader asking *does this still describe its module* does not care which check found it.
    The break here is a renamed emit label, which **no value check can see**: `ops.check`
    compares three fields and `produces[].name` is not one of them.
    """
    from mendel_api.settings import settings

    registry = broken_registry_copy(
        "tools/nf-core/fastqc/fastqc.contract.yml", "name: zip", "name: nonesuch"
    )
    monkeypatch.setattr(settings, "registry_root", registry)
    contracts._checked.cache_clear()

    listing = contracts.listing()
    row = next(r for r in listing.rows if r.id.startswith("nf-core/fastqc"))
    assert row.status is Status.DRIFTED
    assert listing.counts["drifted"] == 1
    contracts._checked.cache_clear()
