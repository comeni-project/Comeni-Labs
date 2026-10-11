"""One immutable filter and page description shared by task rows and their count."""

from dataclasses import dataclass
from enum import StrEnum

from wiener_core.events import TaskStatus


class TaskSort(StrEnum):
    TASK_ID = "task_id"
    MEMORY_DESC = "-peak_rss_bytes"
    MEMORY_ASC = "peak_rss_bytes"
    TIME_DESC = "-realtime_ms"
    TIME_ASC = "realtime_ms"


@dataclass(frozen=True, slots=True)
class TaskQuery:
    process: str | None = None
    status: TaskStatus | None = None
    retried_only: bool = False
    attempt: int | None = None
    tag: str | None = None
    sort: TaskSort = TaskSort.TASK_ID
    after: int = 0
    limit: int = 100

    def __post_init__(self):
        try:
            sort = TaskSort(self.sort)
        except ValueError:
            sort = TaskSort.TASK_ID
        object.__setattr__(self, "sort", sort)
        object.__setattr__(self, "limit", min(self.limit, 500))
