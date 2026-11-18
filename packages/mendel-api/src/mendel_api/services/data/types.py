"""What an analysis's data is made of (#511): the files found in its ticked folders, the samples
they pair into, and what was measured on each. **Paths live here and in a submitted run's
params, never in a pipeline** (invariant 15)."""

from typing import Literal

from pydantic import BaseModel, Field

from mendel_api.authoring.types import SampleFact
from mendel_api.services.data.rule import Check, Fix, Rule
from mendel_api.services.data.summary import Summary


class ScannedFile(BaseModel):
    """One file in a ticked folder, and what it turned out to be."""

    path: str
    name: str
    size: int
    sample: str | None = None
    """The sample it was paired into."""
    recognised: str | None = None
    """The data type measuring recognised it as; `None` when nothing read it."""
    used_as: Literal["reference", "candidate"] | None = None
    """What it is for when it is not a sample's: a reference, or a candidate for one (it sits in
    a folder named for references, so it is offered on Data → References, not made a sample)."""
    left_out: bool = False
    """Its sample is left out of the analysis, so nothing uses it (#535)."""


class DataSample(BaseModel):
    """One sample: its files (paths, read 1 first) and what was measured on it."""

    name: str = Field(min_length=1, max_length=200)
    """At most 200, as `SampleName`: a longer name could reach no door a sample may cross (#505)."""
    files: list[str]
    outcome: str
    type_id: str | None = None
    facts: list[SampleFact] = []
    left_out: bool = False


class Scan(BaseModel):
    state: Literal["idle", "scanning", "done", "failed"] = "idle"
    done: int = 0
    total: int = 0
    error: str | None = None
    examples: list[tuple[str, str, str | None]] = []
    """The first three files the rule fitted: file, sample, read."""
    finished_at: str | None = None
    """When the scan finished, so the page can say how fresh the data is."""


class Reference(BaseModel):
    """A study-wide file (a genome, an annotation), named with its type by the person."""

    path: str
    name: str
    type_id: str
    origin: Literal["you", "ai"] = "you"
    reason: str | None = None
    facts: list[SampleFact] = []


class RuleResult(BaseModel):
    samples: int = 0
    unfit: int = 0
    examples: list[tuple[str, str, str | None]] = []


class AnalysisDataView(BaseModel):
    """An analysis's data as the Data pages read it: everything but the file list, which is paged
    (`files` is its count)."""

    draft_id: str
    folders: list[str] = []
    scan: Scan = Scan()
    samples: list[DataSample] = []
    files: int = 0
    revision: int = 0
    rule: Rule = Rule()
    rule_result: RuleResult = RuleResult()
    checks: list[Check] = []
    fixes: list[Fix] = []
    references: list[Reference] = []
    columns: dict[str, dict[str, str]] = {}
    summary: Summary = Summary()


class FilesPage(BaseModel):
    files: list[ScannedFile]
    total: int
