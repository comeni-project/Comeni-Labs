"""Build the demo's data folders (#511): real public test data, downloaded once, with a few faults
planted for *Check these* to find. Nothing here is a person's data.

Two examples, one folder each under `.run/data/`:

**demo-yeast**, RNA-seq gene counts. nf-core/test-datasets' S. cerevisiae reads (GSE110004,
subsampled) and its small genome and annotation:
- reads/WT_REP1, WT_REP2, RAP1_IAA_REP1: paired reads, as published;
- reads/WT_REP3_R1.fastq.gz with its mate named WT_REP3_2.fq.gz, which the default rule cannot
  pair, so *Check these* offers to use it;
- reads/RAP1_IAA_REP2: a copy of RAP1_IAA_REP1 cut to 50 bases, which *Check these* flags
  against the others' 101;
- reference/genome.fasta and reference/genes.gtf.

**demo-staph**, assembly quality. S. aureus genome assemblies from NCBI RefSeq, three complete
and two drafts in many contigs, and the NCTC 8325 reference with its annotation:
- assemblies/<strain>.fna;
- reference/genome.fna and reference/genes.gff.

Usage:

    python3 tools/demo_data.py [--cache .run/cache/demo] [--out .run/data]
"""

import argparse
import gzip
import shutil
import urllib.request
from pathlib import Path

_NFCORE = "https://raw.githubusercontent.com/nf-core/test-datasets/rnaseq"
_YEAST = {f"SRR63570{n}_{r}.fastq.gz": f"{_NFCORE}/testdata/GSE110004/SRR63570{n}_{r}.fastq.gz"
          for n in (70, 71, 72, 76) for r in (1, 2)}
_YEAST |= {"genome.fasta": f"{_NFCORE}/reference/genome.fasta",
           "genes.gtf": f"{_NFCORE}/reference/genes.gtf"}

_NCBI = "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF"
_STAPH_ASSEMBLIES = {  # name in the folder: the RefSeq assembly
    "USA300": "GCF_000013465.1_ASM1346v1",
    "N315": "GCF_000009645.1_ASM964v1",
    "MRSA252": "GCF_000011505.1_ASM1150v1",
    "ATCC12600": "GCF_059975795.1_PDT003322108.1",
    "BAC47": "GCF_062052982.1_PDT003448437.1",
}
_STAPH_REFERENCE = "GCF_000013425.1_ASM1342v1"  # NCTC 8325


def _ncbi(assembly: str, suffix: str) -> str:
    digits = assembly[4:13]
    return f"{_NCBI}/{digits[:3]}/{digits[3:6]}/{digits[6:]}/{assembly}/{assembly}_{suffix}"


def _fetch(url: str, cache: Path) -> Path:
    """`url`, downloaded into `cache` once."""
    target = cache / url.rsplit("/", 1)[1]
    if not target.exists():
        cache.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        partial = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.rename(target)
    return target


def _gunzip(source: Path, target: Path) -> None:
    with gzip.open(source, "rb") as packed, target.open("wb") as out:
        shutil.copyfileobj(packed, out)


def _cut(source: Path, target: Path, length: int) -> None:
    """A FASTQ with every read and quality line cut to `length`."""
    with gzip.open(source, "rt") as reads, gzip.open(target, "wt") as out:
        for n, line in enumerate(reads):
            out.write(line.rstrip("\n")[:length] + "\n" if n % 4 in (1, 3) else line)


def _fresh(folder: Path, *parts: str) -> list[Path]:
    if folder.exists():
        shutil.rmtree(folder)
    made = [folder / part for part in parts]
    for path in made:
        path.mkdir(parents=True)
    return made


def yeast(cache: Path, out: Path) -> None:
    got = {name: _fetch(url, cache / "yeast") for name, url in _YEAST.items()}
    reads, reference = _fresh(out, "reads", "reference")
    for sample, run in (("WT_REP1", 70), ("WT_REP2", 72), ("RAP1_IAA_REP1", 76)):
        shutil.copy(got[f"SRR63570{run}_1.fastq.gz"], reads / f"{sample}_R1.fastq.gz")
        shutil.copy(got[f"SRR63570{run}_2.fastq.gz"], reads / f"{sample}_R2.fastq.gz")
    shutil.copy(got["SRR6357071_1.fastq.gz"], reads / "WT_REP3_R1.fastq.gz")
    shutil.copy(got["SRR6357071_2.fastq.gz"], reads / "WT_REP3_2.fq.gz")
    _cut(got["SRR6357076_1.fastq.gz"], reads / "RAP1_IAA_REP2_R1.fastq.gz", 50)
    _cut(got["SRR6357076_2.fastq.gz"], reads / "RAP1_IAA_REP2_R2.fastq.gz", 50)
    shutil.copy(got["genome.fasta"], reference / "genome.fasta")
    shutil.copy(got["genes.gtf"], reference / "genes.gtf")
    print(f"wrote {out}")


def staph(cache: Path, out: Path) -> None:
    assemblies, reference = _fresh(out, "assemblies", "reference")
    for name, assembly in _STAPH_ASSEMBLIES.items():
        _gunzip(_fetch(_ncbi(assembly, "genomic.fna.gz"), cache / "staph"),
                assemblies / f"{name}.fna")
    _gunzip(_fetch(_ncbi(_STAPH_REFERENCE, "genomic.fna.gz"), cache / "staph"),
            reference / "genome.fna")
    _gunzip(_fetch(_ncbi(_STAPH_REFERENCE, "genomic.gff.gz"), cache / "staph"),
            reference / "genes.gff")
    print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=Path(".run/cache/demo"))
    parser.add_argument("--out", type=Path, default=Path(".run/data"))
    args = parser.parse_args()
    yeast(args.cache, args.out / "demo-yeast")
    staph(args.cache, args.out / "demo-staph")
