"""What an analysis's data is made of (#511): the files found in its ticked folders, the samples
they pair into, and what was measured on each. **Paths live here and in a submitted run's
params, never in a pipeline** (invariant 15, as level 0 loosens it)."""

from typing import Literal

from pydantic import BaseModel, Field

from mendel_api.authoring.types import SampleFact


class ScannedFile(BaseModel):
    """One file in a ticked folder, and what it turned out to be."""

    path: str
    name: str
    size: int
    sample: str | None = None
    """The sample it was paired into."""
    recognised: str | None = None
    """The data type measuring recognised it as; `None` when nothing read it."""


class DataSample(BaseModel):
    """One sample: its files (paths, read 1 first) and what was measured on it."""

    name: str = Field(min_length=1, max_length=256)
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


class AnalysisDataView(BaseModel):
    """An analysis's data as the Data pages read it: everything but the file list, which is paged
    (`files` is its count)."""

    draft_id: str
    folders: list[str] = []
    scan: Scan = Scan()
    samples: list[DataSample] = []
    files: int = 0
    revision: int = 0


class FilesPage(BaseModel):
    files: list[ScannedFile]
    total: int
