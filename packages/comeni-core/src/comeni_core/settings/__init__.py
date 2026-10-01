"""Settings: what an installation may change, where each value came from, and why one cannot be
changed. Spec: `docs/superpowers/specs/2026-10-01-settings-design.md`."""

from comeni_core.settings.catalogue import CATALOGUE
from comeni_core.settings.declare import (
    FROM_ENV,
    ChoiceOption,
    EnvItem,
    IllegalValue,
    Kind,
    Setting,
    Where,
)
from comeni_core.settings.installation import (
    Entry,
    Installation,
    Menu,
    MenuSection,
    SecretCodec,
    SettingLocked,
    SettingsStore,
    Shown,
)
from comeni_core.settings.reasons import Designed, Needs, Pinned, ReadOnlyHere, Reason
from comeni_core.settings.resolve import SETTINGS_KEY_ENV, Resolved, Source, resolve
from comeni_core.settings.sections import Catalogue, Section

__all__ = [
    "CATALOGUE",
    "FROM_ENV",
    "SETTINGS_KEY_ENV",
    "Catalogue",
    "ChoiceOption",
    "Designed",
    "Entry",
    "EnvItem",
    "IllegalValue",
    "Installation",
    "Kind",
    "Menu",
    "MenuSection",
    "Needs",
    "Pinned",
    "ReadOnlyHere",
    "Reason",
    "Resolved",
    "SecretCodec",
    "Section",
    "Setting",
    "SettingLocked",
    "SettingsStore",
    "Shown",
    "Source",
    "Where",
    "resolve",
]
