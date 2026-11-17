"""pegi3s, **shown, not imported** (2026-11-17): a fixed sample of the pegi3s Bioinformatics
Docker Images Project as a second catalogue source, so Registry · Tools can show tools from more
than nf-core. Every row it makes is a *preview* (`PREVIEW_SOURCES`): the page says so, and nothing
claims a live connection.

Making it real is replacing `SAMPLE` with a fetch of the project's image list, behind the same
`CatalogueSource`: nothing outside this module knows the layout. The sample names images, their
job and the formats they read and write; it states **no versions**, since it did not read them.
"""

from collections.abc import Iterator
from pathlib import Path

from mendel_forge.model import UpstreamModule
from mendel_forge.source import Snapshot

PREVIEW_SOURCES = frozenset({"pegi3s"})
"""Sources whose rows are a sample shown for what they would look like, not a catalogue read."""

# (image, what it does, topics, reads, makes)
SAMPLE: list[tuple[str, str, list[str], list[str], list[str]]] = [
    ("clustalomega", "Multiple sequence alignment of protein or nucleotide sequences",
     ["Phylogenetics", "Alignment"], ["fasta"], ["fasta"]),
    ("mafft", "Multiple sequence alignment, fast and scalable to thousands of sequences",
     ["Phylogenetics", "Alignment"], ["fasta"], ["fasta"]),
    ("muscle", "Multiple sequence alignment with high accuracy",
     ["Phylogenetics", "Alignment"], ["fasta"], ["fasta"]),
    ("tcoffee", "Multiple sequence alignment combining several aligners' results",
     ["Phylogenetics", "Alignment"], ["fasta"], ["fasta"]),
    ("prank", "Phylogeny-aware multiple sequence alignment",
     ["Phylogenetics", "Alignment"], ["fasta"], ["fasta"]),
    ("trimal", "Trims poorly aligned positions from a multiple sequence alignment",
     ["Phylogenetics"], ["fasta"], ["fasta"]),
    ("gblocks", "Selects conserved blocks of a multiple sequence alignment",
     ["Phylogenetics"], ["fasta"], ["fasta"]),
    ("iqtree", "Maximum-likelihood phylogenetic trees with model selection",
     ["Phylogenetics"], ["fasta"], ["newick"]),
    ("phyml", "Maximum-likelihood phylogenetic trees",
     ["Phylogenetics"], ["fasta"], ["newick"]),
    ("mrbayes", "Bayesian phylogenetic inference",
     ["Phylogenetics"], ["nexus"], ["newick"]),
    ("paml", "Selection analyses on codon alignments (codeml)",
     ["Phylogenetics"], ["fasta"], ["txt"]),
    ("blast", "Similarity search of sequences against a database",
     ["Genomics"], ["fasta"], ["tsv"]),
    ("cd-hit", "Clusters sequences to remove redundancy",
     ["Genomics"], ["fasta"], ["fasta"]),
    ("seqkit", "Converts, filters and summarises FASTA and FASTQ files",
     ["Genomics", "Quality control"], ["fasta", "fastq"], ["fasta", "tsv"]),
    ("emboss", "A suite of sequence analysis tools (translation, alignment, conversion)",
     ["Genomics"], ["fasta"], ["fasta"]),
]


class Pegi3sSample:
    """A `CatalogueSource` over `SAMPLE`: nothing is fetched, so a sync never fails."""

    name = "pegi3s"

    def sync(self, cache: Path) -> Snapshot:
        return Snapshot(source=self.name, commit="sample-2026-11", root=cache)

    def modules(self, snapshot: Snapshot) -> Iterator[UpstreamModule]:
        for image, does, topics, reads, makes in SAMPLE:
            yield UpstreamModule(
                source=self.name, path=image, name=image, description=does,
                keywords=["pegi3s", "docker"], containers=[f"pegi3s/{image}"],
                topics=topics, formats_in=reads, formats_out=makes, label="preview",
            )
