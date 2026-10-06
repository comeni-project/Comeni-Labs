"""A person's tool in the goal (§14.3 of the consultant build): a pin at a site."""

from comeni_core.goal.asked import Constraints, ProducerPin, Site


def test_a_goal_without_pins_dumps_as_it_did():
    """Invariant 10: an existing goal emits the same bytes, so no `producers: []` appears."""
    assert "producers" not in Constraints().model_dump(mode="json")


def test_a_pin_round_trips_with_sorted_states():
    pin = ProducerPin(
        site=Site(type_id="alignment.bam", states=frozenset({"b", "a"})),
        contract="nf-core/hisat2/align@2.2.2",
    )
    dumped = Constraints(producers=[pin]).model_dump(mode="json")
    assert dumped["producers"][0]["site"]["states"] == ["a", "b"]
    assert Constraints.model_validate(dumped).producer_at(pin.site) == pin


def test_the_last_pin_at_a_site_wins():
    site = Site(type_id="alignment.bam")
    first = ProducerPin(site=site, contract="lab/a@1")
    last = ProducerPin(site=site, contract="lab/b@1")
    assert Constraints(producers=[first, last]).producer_at(site) == last
