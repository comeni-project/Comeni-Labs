from comeni_core.settings import CATALOGUE
from comeni_core.settings.declare import Kind


def test_dev_mode_is_a_toggle_off_by_default_in_the_last_section():
    setting = CATALOGUE.setting("dev.mode")
    assert setting.kind is Kind.TOGGLE and setting.default is False
    assert CATALOGUE.section_of("dev.mode").key == "dev"
    assert CATALOGUE.sections[-1].key == "dev"


def test_pacing_is_live():
    assert CATALOGUE.setting("building.pacing").unavailable is None
