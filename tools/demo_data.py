"""Build the demo's data folder (#511): yeast RNA-seq reads and a reference, with two faults
planted for *Check these* to find.

The source is nf-core/test-datasets' RNA-seq test data (S. cerevisiae, `SRR6357070` reads and a
one-chromosome genome with its annotation), which `make dev` walks have kept in `.run/wiener/data`.
Nothing here is a person's data. Usage:

    python3 tools/demo_data.py [--source .run/wiener/data] [--out .run/data/demo-yeast]

Written:
- reads/Y1, Y2: the test pair, as two samples;
- reads/Y3: the same reads cut to 50 bases, which *Check these* flags against the others' 101;
- reads/Y4_R1.fastq.gz with its mate named Y4_2.fq.gz, which the default rule cannot pair, so
  *Check these* offers to use it;
- reference/genome.fasta and reference/genes.gtf.
"""

import argparse
import gzip
import shutil
from pathlib import Path


def _cut(source: Path, target: Path, length: int) -> None:
    """A FASTQ with every read and quality line cut to `length`."""
    with gzip.open(source, "rt") as reads, gzip.open(target, "wt") as out:
        for n, line in enumerate(reads):
            out.write(line[:length] + "\n" if n % 4 in (1, 3) else line)


def build(source: Path, out: Path) -> None:
    r1, r2 = source / "SRR6357070_1.fastq.gz", source / "SRR6357070_2.fastq.gz"
    missing = [p for p in (r1, r2, source / "genome.fasta", source / "genes.gtf") if not p.exists()]
    if missing:
        raise SystemExit(f"missing test data: {', '.join(map(str, missing))}")
    reads, reference = out / "reads", out / "reference"
    if out.exists():
        shutil.rmtree(out)
    reads.mkdir(parents=True)
    reference.mkdir()
    for sample in ("Y1", "Y2"):
        shutil.copy(r1, reads / f"{sample}_R1.fastq.gz")
        shutil.copy(r2, reads / f"{sample}_R2.fastq.gz")
    _cut(r1, reads / "Y3_R1.fastq.gz", 50)
    _cut(r2, reads / "Y3_R2.fastq.gz", 50)
    shutil.copy(r1, reads / "Y4_R1.fastq.gz")
    shutil.copy(r2, reads / "Y4_2.fq.gz")
    shutil.copy(source / "genome.fasta", reference / "genome.fasta")
    shutil.copy(source / "genes.gtf", reference / "genes.gtf")
    print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=Path(".run/wiener/data"))
    parser.add_argument("--out", type=Path, default=Path(".run/data/demo-yeast"))
    args = parser.parse_args()
    build(args.source, args.out)
