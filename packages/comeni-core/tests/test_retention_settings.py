"""Retention menu declarations and scheduler day conversion share one vocabulary."""

from comeni_core.settings import CATALOGUE
from comeni_core.settings.retention import days

DEFAULTS = {
    "retention_runs.work_succeeded_days": "0",
    "retention_runs.work_failed_days": "7",
    "retention_runs.runs_days": "keep",
    "retention.model_replies_days": "30",
    "retention.drafts_days": "keep",
}


def _settings():
    return {s.key: s for sec in CATALOGUE.sections for s in sec.settings}


def test_every_category_is_on_the_menu_with_its_default():
    found = {k: s.default for k, s in _settings().items() if k.startswith("retention")}
    assert found == DEFAULTS


def test_the_two_sections_sit_side_by_side_and_wiener_serves_its_own():
    sections = {s.key: s for s in CATALOGUE.sections}
    assert sections["retention"].served_by == "mendel"
    assert sections["retention_runs"].served_by == "wiener"
    keys = [s.key for s in CATALOGUE.sections]
    assert keys.index("retention_runs") == keys.index("retention") + 1
    assert keys.index("retention") == keys.index("privacy") + 1


def test_each_choice_says_its_limit_in_words():
    labels = {o.value: o.label for o in _settings()["retention_runs.work_failed_days"].options}
    assert labels["keep"] == "Kept until deleted" and labels["7"] == "After 7 days"
    assert labels["0"] == "When the run ends"
    assert "0" not in {o.value for o in _settings()["retention.model_replies_days"].options}


def test_each_limit_says_what_goes_and_what_stays():
    for key in DEFAULTS:
        help_text = _settings()[key].help
        assert help_text and ("stay" in help_text or "deleted" in help_text), key


def test_days_reads_a_choice():
    assert days("keep") is None and days("0") == 0 and days("30") == 30
