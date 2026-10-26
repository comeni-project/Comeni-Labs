"""Closed, user-facing reasons why a setting is locked or unavailable."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class _Reason(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _says_is_derived(cls, data: Any) -> Any:
        """Drop serialized `says` because it is derived; continue to forbid other extras."""
        if isinstance(data, dict) and "says" in data:
            return {k: v for k, v in data.items() if k != "says"}
        return data


class Pinned(_Reason):
    """A value in `.env` beats every layer. The variable is named so a person knows where to go."""

    kind: Literal["pinned"] = "pinned"
    env: str

    @computed_field
    @property
    def says(self) -> str:
        return f"Pinned by .env ({self.env}). Change it there and restart."


class Designed(_Reason):
    """Designed, not built: shown so the menu tells the truth about what is coming."""

    kind: Literal["designed"] = "designed"
    where: str

    @computed_field
    @property
    def says(self) -> str:
        return f"Designed, not built yet: {self.where}."


class Needs(_Reason):
    """Something else has to be set first."""

    kind: Literal["needs"] = "needs"
    what: str

    @computed_field
    @property
    def says(self) -> str:
        return f"Needs something first: {self.what}."


class ReadOnlyHere(_Reason):
    """Reported here, set somewhere else."""

    kind: Literal["read_only_here"] = "read_only_here"
    why: str

    @computed_field
    @property
    def says(self) -> str:
        return f"Shown here, set elsewhere: {self.why}."


Reason = Annotated[Pinned | Designed | Needs | ReadOnlyHere, Field(discriminator="kind")]

REASON_KINDS: tuple[str, ...] = ("pinned", "designed", "needs", "read_only_here")
"""Supported reason discriminators in display order."""
