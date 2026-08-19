"""The port a hole is about must reach the candidates it offers.

`_hole` has taken a `port` since Phase 2 and spent it only on evidence. Scoring needs it too, and
a hole whose candidates are unranked is the whole of what made the forge unanswerable.
"""

from pathlib import Path

from mendel_resolver.layers import load

from mendel_forge import assemble, sources
from mendel_forge.sources import ToolRef

ROOT = Path(__file__).resolve().parents[3]


def _scaffold(ident: str, version: str):
    """The same chain `ops.draft` runs, minus the workspace write.

    Verified against `ops.py:253-255` rather than guessed: the source method is `ingest` and it
    takes a `ToolRef` plus a root, and `scaffold_for` names its keyword `ident`, not `name`.
    """
    ref = ToolRef(source="nf-core", ident=ident)
    observation = sources.get(ref.source).ingest(ref, ROOT / "vendor")
    stack = load([ROOT / "registry"])
    return assemble.scaffold_for(
        observation, stack, ident=f"{ref.source}/{ref.ident}", version=version
    )


def test_a_produces_hole_offers_its_own_type_first() -> None:
    scaffold = _scaffold("samtools/faidx", "1.21.0")

    # `SAMTOOLS_FAIDX` emits a port called `fa`. The answer is `genome.fasta` and nothing else in
    # the vocabulary is close — but alphabetical order buried it sixth among twenty-two.
    hole = next(h for h in scaffold.holes if h.subject == "produces[0].type_id")
    assert hole.candidates[0].value == "genome.fasta"
