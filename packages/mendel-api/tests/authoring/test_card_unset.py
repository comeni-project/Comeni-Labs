"""#384: an offer card says a setting with no listed values *stays unset, and is not something you
need to provide* — true only of a setting whose route leaves the tool its own behaviour."""

from comeni_core.spell.routes import Via
from mendel_api.services import registry
from mendel_api.stages.building.cards import optional_unset
from mendel_authoring.gaps import Gap, GapKind

STAR = "nf-core/star/align@1.11.0"
GAP = Gap(kind=GapKind.NO_DOMAIN, subject="seq_platform",
          fix="registry/tools/nf-core/star/align/contract.yml")


def test_an_ext_setting_with_no_listed_values_is_said_to_stay_unset():
    contract = registry.stack().registry.get(STAR)
    assert optional_unset(contract, [GAP]) == ["seq_platform"]


def test_a_setting_the_call_cannot_leave_empty_is_not_said_to_stay_unset():
    contract = registry.stack().registry.get(STAR)
    assert any(p.name == "seq_platform" for p in contract.params)
    positional = contract.model_copy(update={"params": [
        p.model_copy(update={"via": Via.POSITIONAL, "key": None, "template": None})
        if p.name == "seq_platform" else p
        for p in contract.params
    ]})
    assert optional_unset(positional, [GAP]) == []
