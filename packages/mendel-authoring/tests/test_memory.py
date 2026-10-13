"""What is known, as every conversational prompt is told it (Part I.0 spec §6.3)."""

import os
from pathlib import Path

from mendel_authoring import memory
from mendel_authoring.memory import Known, KnownItem

GOLDEN = Path(__file__).parent / "golden"


def _golden(name: str, text: str) -> None:
    """Compare against the stored text. `COMENI_WRITE_GOLDEN=1` writes it — then read it."""
    path = GOLDEN / name
    if os.environ.get("COMENI_WRITE_GOLDEN") == "1" and not path.exists():
        path.write_text(text)
    assert path.exists(), f"{name} missing: run once with COMENI_WRITE_GOLDEN=1 and review it"
    assert text == path.read_text()


GATHERING = Known(
    wants=[KnownItem(label="gene counts matrix", source="said", heard="gene counts")],
    not_offered=["differential expression"],
    inputs=[KnownItem(label="sequencing reads (FASTQ)", source="said", heard="Illumina reads")],
    facts=[KnownItem(label="read length", value="150 bp", source="said", heard="150 bp"),
           KnownItem(label="paired", value="yes", source="measured")],
    suggested=["strandedness: reverse"],
    open=["gene annotation (GTF)"],
)


def test_before_the_goal_is_confirmed():
    _golden("memory-gathering.txt", memory.render(GATHERING))


def test_once_confirmed_changes_are_offered():
    _golden("memory-confirmed.txt",
            memory.render(GATHERING.model_copy(update={"confirmed": True, "open": []})))


def test_nothing_known_says_so():
    assert "Nothing is known yet" in memory.render(Known())


def test_the_same_known_renders_the_same_text():
    assert memory.render(GATHERING) == memory.render(GATHERING)
