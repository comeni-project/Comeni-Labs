"""Sections, and the catalogue that holds them (spec §4, §7).

**Uniqueness is checked when the catalogue is built**, not at the first request: a key or an env
name declared twice is a declaration error, and the earliest place to say so is import time.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core.settings.declare import Setting


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    title: str
    lede: str = ""
    """One line under the section's title: what it holds. The menu writes none of its own."""
    order: int
    served_by: Literal["mendel", "wiener"] = "mendel"
    """Which API reports it. Wiener is a separate service with its own `.env` (spec §7)."""
    settings: tuple[Setting, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _keys_are_ours(self) -> "Section":
        for setting in self.settings:
            if not setting.key.startswith(f"{self.key}."):
                raise ValueError(f"{setting.key} does not belong in section {self.key}")
        return self


class Catalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: tuple[Section, ...]

    @model_validator(mode="after")
    def _unique_and_ordered(self) -> "Catalogue":
        seen_keys: set[str] = set()
        seen_env: set[str] = set()
        for section in self.sections:
            for setting in section.settings:
                if setting.key in seen_keys:
                    raise ValueError(f"{setting.key} is declared twice")
                seen_keys.add(setting.key)
                if setting.env is not None:
                    if setting.env in seen_env:
                        raise ValueError(f"{setting.env} pins two settings")
                    seen_env.add(setting.env)
        ordered = tuple(sorted(self.sections, key=lambda s: (s.order, s.key)))
        object.__setattr__(self, "sections", ordered)
        return self

    def settings(self) -> tuple[Setting, ...]:
        return tuple(s for section in self.sections for s in section.settings)

    def setting(self, key: str) -> Setting:
        for setting in self.settings():
            if setting.key == key:
                return setting
        raise KeyError(key)

    def section_of(self, key: str) -> Section:
        for section in self.sections:
            if any(s.key == key for s in section.settings):
                return section
        raise KeyError(key)

    def served_by(self, server: Literal["mendel", "wiener"]) -> tuple[Section, ...]:
        return tuple(s for s in self.sections if s.served_by == server)
