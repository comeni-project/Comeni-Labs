from pathlib import Path

from mendel_forge.verify import Rung, refuses, verify

ROOT = Path(__file__).resolve().parents[3]


def _verify(scaffold):
    return verify(scaffold, registry_root=ROOT / "registry", source_root=ROOT / "registry")


def test_an_incomplete_scaffold_stops_at_the_first_rung(incomplete_scaffold):
    verdicts = _verify(incomplete_scaffold)
    assert verdicts[0].rung is Rung.COMPLETE
    assert verdicts[0].refused is True
    assert len(verdicts) == 1, "the ladder is cheapest-first; a failed rung stops it"
    assert verdicts[0].diagnostics[0].code == "MF0004"


def test_a_complete_scaffold_reaches_the_conformance_rung(complete_scaffold):
    assert Rung.CONFORMS in [v.rung for v in _verify(complete_scaffold)]


def test_a_wrong_process_name_is_caught_by_the_existing_conformance_code(complete_scaffold):
    """MD0101, reused rather than twinned. A draft failing this fails it for exactly the
    reason a built pipeline would, and a runbook citing MD0101 covers both."""
    broken = complete_scaffold.model_copy(
        update={
            "filled": {
                **complete_scaffold.filled,
                "nf_process": complete_scaffold.filled["nf_process"].model_copy(
                    update={"value": "FASTQCC"}
                ),
            }
        }
    )
    codes = [d.code for v in _verify(broken) for d in v.diagnostics]
    assert "MD0101" in codes


def test_every_diagnostic_carries_a_fix(incomplete_scaffold, orphan_scaffold, widget_scaffold):
    """**It ran on `complete_scaffold` and therefore on nothing.** A complete scaffold is the one
    input that produces no diagnostics, so every assertion sat inside an empty loop and the test
    passed on a ladder where no rung carried a fix at all. Sweep the scaffolds that *fail*, and
    assert the sweep found something before believing what it says about it."""
    seen = []
    for scaffold in (incomplete_scaffold, orphan_scaffold, widget_scaffold):
        for verdict in _verify(scaffold):
            for diagnostic in verdict.diagnostics:
                seen.append(diagnostic.code)
                assert diagnostic.fix, f"{diagnostic.code} has no fix; that is half a diagnostic"
    assert seen, "no scaffold here produced a diagnostic — this test is measuring nothing"


def test_a_contract_nothing_can_route_to_is_reported_but_does_not_refuse(orphan_scaffold):
    """The inert case. Worth telling a reviewer before they land it, and not worth
    blocking on — a lab may legitimately add a tool nothing reaches yet."""
    verdicts = _verify(orphan_scaffold)
    routes = next(v for v in verdicts if v.rung is Rung.ROUTES)
    assert routes.diagnostics
    assert routes.refused is False
    assert refuses(verdicts) is False


def test_verdicts_are_ordered_cheapest_first(complete_scaffold):
    order = [v.rung for v in _verify(complete_scaffold)]
    assert order == sorted(order, key=list(Rung).index)
