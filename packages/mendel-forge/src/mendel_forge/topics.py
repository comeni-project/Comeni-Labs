"""The catalogue's topics and formats, from what nf-core itself wrote.

**nf-core has no topic field**, so topics are derived: a keyword or an EDAM term listed here
selects its topic. The table is ours to keep and the operator's to adjust (forge part 1 spec,
§2). A module matching nothing has no topic; it is never given a likely one.
"""

import re
from pathlib import PurePosixPath

from mendel_forge.model import Channel

TOPICS: dict[str, frozenset[str]] = {
    "genomics": frozenset({
        "genomics", "genome", "wgs", "wes", "dna", "http://edamontology.org/topic_0622",
    }),
    "metagenomics": frozenset({
        "metagenomics", "metagenome", "taxonomy", "taxonomic profiling", "classification",
        "microbiome", "http://edamontology.org/topic_3174",
    }),
    "alignment": frozenset({
        "align", "alignment", "aligner", "mapping", "map", "msa", "multiple sequence alignment",
        "http://edamontology.org/operation_0292", "http://edamontology.org/operation_0492",
    }),
    "assembly": frozenset({
        "assembly", "assembler", "de novo assembly", "contigs", "scaffolding",
        "http://edamontology.org/operation_0310", "http://edamontology.org/topic_0196",
    }),
    "variant calling": frozenset({
        "variant calling", "variant", "variants", "snp", "vcf", "genotyping",
        "http://edamontology.org/operation_3227", "http://edamontology.org/topic_0199",
    }),
    "quality control": frozenset({
        "quality control", "qc", "quality", "trimming", "adapters",
        "http://edamontology.org/operation_3218", "http://edamontology.org/operation_2428",
    }),
    "transcriptomics": frozenset({
        "rna-seq", "rnaseq", "transcriptomics", "transcriptome", "expression", "quantification",
        "http://edamontology.org/topic_3308",
    }),
    "epigenomics": frozenset({
        "chip-seq", "chipseq", "atac-seq", "methylation", "peak calling", "peaks",
        "http://edamontology.org/topic_3295",
    }),
    "proteomics": frozenset({
        "proteomics", "mass spectrometry", "peptide", "protein identification", "openms",
        "http://edamontology.org/topic_0121",
    }),
    "imaging": frozenset({
        "imaging", "image", "microscopy", "segmentation", "cell segmentation",
        "http://edamontology.org/topic_3383",
    }),
    "phylogenetics": frozenset({
        "phylogenetics", "phylogeny", "tree", "phylogenetic",
        "http://edamontology.org/topic_0084",
    }),
}

COMPRESSION = frozenset({"gz", "bz2", "zst", "xz", "zip"})
"""Suffixes that say how a file is packed, not what it is: `reads.fastq.gz` is a fastq."""

_BRACES = re.compile(r"\{([^{}]*)\}")


def topics_of(keywords: list[str], ontologies: list[str]) -> list[str]:
    terms = {term.strip().lower() for term in keywords} | set(ontologies)
    return sorted(topic for topic, selects in TOPICS.items() if terms & selects)


def formats_of(channels: list[Channel]) -> list[str]:
    found = set()
    for channel in channels:
        for pattern in _expand(channel.pattern or ""):
            found.update(_extension(pattern))
    return sorted(found)


def _expand(pattern: str) -> list[str]:
    """`*.{fastq,fq}.gz` → `*.fastq.gz`, `*.fq.gz`; nested or repeated braces expand fully."""
    match = _BRACES.search(pattern)
    if match is None:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end():]
    return [p for option in match.group(1).split(",") for p in _expand(head + option + tail)]


def _extension(pattern: str) -> list[str]:
    suffixes = [s.lstrip(".").lower() for s in PurePosixPath(pattern).suffixes]
    meaningful = [s for s in suffixes if s and s not in COMPRESSION and re.fullmatch(r"\w+", s)]
    return meaningful[-1:]
