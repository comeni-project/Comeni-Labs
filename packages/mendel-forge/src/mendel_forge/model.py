"""What the forge reads about one upstream module: everything its source declares.

**A field nobody could read is `None` or empty, never a guess** (forge part 1 spec, anti-goals).
A module that could not be read at all is still a `UpstreamModule`, carrying its `problems`, so
the catalogue's counts stay honest.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Channel(_Frozen):
    """One input or output as `meta.yml` describes it."""

    name: str
    type: str | None = None
    description: str | None = None
    pattern: str | None = None
    ontologies: list[str] = []
    """EDAM URLs, as written (`http://edamontology.org/format_1930`)."""


class UpstreamTool(_Frozen):
    """One tool the module wraps, from `meta.yml`'s `tools`."""

    name: str
    description: str | None = None
    homepage: str | None = None
    documentation: str | None = None
    tool_dev_url: str | None = None
    doi: str | None = None
    licence: list[str] = []
    biotools: str | None = None


class CondaPackage(_Frozen):
    """One pinned dependency of `environment.yml` (`bioconda::star=2.7.11b`)."""

    channel: str | None
    name: str
    version: str


class NfTest(_Frozen):
    """One nf-test case and the `test-datasets` paths it reads."""

    name: str
    datasets: list[str] = []


class Problem(_Frozen):
    """Why part of a module could not be read. `code` is an `MF05xx` diagnostic."""

    code: str
    says: str


class UpstreamModule(_Frozen):
    source: str
    path: str
    """The module's path under its source (`star/align`)."""
    name: str
    description: str | None = None
    keywords: list[str] = []
    tools: list[UpstreamTool] = []
    inputs: list[Channel] = []
    outputs: list[Channel] = []
    authors: list[str] = []
    maintainers: list[str] = []
    packages: list[CondaPackage] = []
    tool_version: str | None = None
    containers: list[str] = []
    label: str | None = None
    tests: list[NfTest] = []
    topics: list[str] = []
    formats_in: list[str] = []
    formats_out: list[str] = []
    upstream_changed: datetime | None = None
    problems: list[Problem] = []
