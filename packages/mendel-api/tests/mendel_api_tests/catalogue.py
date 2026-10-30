"""A catalogue source made of the forge's fixture modules, for API tests (no network)."""

from collections.abc import Iterator
from pathlib import Path

from mendel_forge.model import UpstreamModule
from mendel_forge.nfcore.parse import parse_module
from mendel_forge.source import Snapshot, SourceUnavailable
from support.paths import ROOT

FIXTURES = ROOT / "packages" / "mendel-forge" / "tests" / "fixtures" / "nf-core"


class FakeSource:
    """Yields fixture modules; `fail_after` raises once that many have been yielded."""

    name = "nf-core"

    def __init__(self, paths: list[str], commit: str = "c1", fail_after: int | None = None):
        self.paths, self.commit, self.fail_after = paths, commit, fail_after

    def sync(self, cache: Path) -> Snapshot:
        return Snapshot(source=self.name, commit=self.commit, root=FIXTURES,
                        test_data_commit="c0ffee")

    def modules(self, snapshot: Snapshot) -> Iterator[UpstreamModule]:
        for n, path in enumerate(self.paths):
            if self.fail_after is not None and n == self.fail_after:
                raise SourceUnavailable("the network went away")
            yield parse_module(FIXTURES / path, path)
