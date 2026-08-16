"""A source shaped like pegi3s, so the protocol has two implementations from day one.

**Not a pegi3s adapter** — that is issue #65, and it needs a container registry and a
decision about what may honestly be read out of documentation prose. This is the *shape*:
a container, a name, no Nextflow module, and everything else a hole.

It lives in `tests/` and is never registered at package import, so it cannot reach a user.
Its job is to fail loudly if `Source` ever grows a member only nf-core can supply — which
is how a pluggable seam quietly becomes a single-implementation one.
"""

from pathlib import Path

from comeni_core import yaml_strict
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef


class OpaqueSource:
    name = "opaque"

    def discover(self, root: Path) -> list[ToolRef]:
        found = [
            ToolRef(source=self.name, ident=path.parent.name)
            for path in (root / "tools").rglob("tool.yml")
        ]
        return sorted(found, key=lambda r: r.ident)

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        path = root / "tools" / ref.ident / "tool.yml"
        data = yaml_strict.load(path)
        at = str(path)
        facts = {}
        if isinstance(data, dict) and isinstance(data.get("container"), str):
            facts["container"] = Fact(
                value=data["container"],
                evidence=Excerpt(locator=f"{at}:container", text=data["container"]),
            )
        prose = []
        if isinstance(data, dict) and isinstance(data.get("description"), str):
            prose.append(Excerpt(locator=f"{at}:description", text=data["description"]))
        return Observation(source=self.name, ref_id=str(ref), facts=facts, prose=prose)
