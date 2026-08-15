# Getting started

Build a pipeline, read what it decided, and understand what the flags mean. Fifteen
minutes.

## What you need

- [`uv`](https://docs.astral.sh/uv/) and Python 3.12 or later
- Docker and [Nextflow](https://www.nextflow.io/) — only for the `stub` gate at the end

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
uv run pytest -q
```

`--recurse-submodules` matters: the registry is [its own
repository](https://github.com/comeni-project/comeni-registry) mounted at `registry/`, and
without it that directory is empty. If you already cloned without it, run `git submodule update
--init`.

## Build something

`examples/rnaseq-goal.yml` describes an RNA-seq analysis as a *shape*: what you have,
what you want, and what the data looks like.

```yaml
have:
  - type_id: fastq.reads
  - type_id: annotation.gtf
want:
  - counts.matrix
constraints:
  required_states:
    counts.matrix: [gene_level]
profile:
  read_length: 150
  strandedness: reverse
  n_samples: 12
  paired: true
```

Note what is *not* there: no filenames, no paths, no sample identifiers. There is nowhere
to put one, and a test asserts that. See [concepts/privacy-and-egress.md](../concepts/privacy-and-egress.md).

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/
```

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

You now have `build/main.nf`, `build/nextflow.config`, `build/modules/` — and
`build/pipeline.yml`, which is the one to read.

## Read what it decided

The second line is the point of the whole tool. Four modules were chosen without needing
you, and one parameter could not be settled by any rule — so it is flagged rather than
guessed. Nothing was decided silently.

Every choice carries a tier, and its reason sits beside it. Open `build/pipeline.yml`, or:

```bash
uv run python -c "
import yaml
p = yaml.safe_load(open('build/pipeline.yml'))
for s in p['steps']:
    print(s['id'], '→ tier', s['why']['tier'], '—', s['why']['reason'])
"
```

```
trimgalore            → tier 1 — the only contract that produces this
star_genomegenerate   → tier 1 — the only contract that produces this
star_align            → tier 3 — rule producer_of:alignment.bam matched
                                 {'read_length': '>= 70'}: Dobin et al. 2013, …
samtools_sort         → tier 1 — the only contract that produces this
subread_featurecounts → tier 1 — the only contract that produces this
```

STAR was chosen because your reads are 150bp and a declared rule says so, citing the
paper. Change `read_length` to `50` and rebuild: you get HISAT2, and the reason names the
rule that fired.

The four tiers are explained in [concepts/tiers.md](../concepts/tiers.md). In short:
tier 1 and 2 are silent, tier 3 is worth a glance, tier 4 needs you.

## Check that it runs

`-stub-run` executes the whole graph with dummy outputs, which proves the wiring without
processing any data:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
```

```
gate stub: PASS
```

The first run pulls containers and can take fifteen minutes. After that it is seconds.

## Run it for real

Mendel emits a pipeline; your laboratory runs it. The generated `nextflow.config`
declares every input as `null` for you to fill in:

```bash
cd build
nextflow run main.nf -profile docker \
  --input 'data/*_R{1,2}.fastq.gz' \
  --gtf reference/genes.gtf
```

Your data never passes through Mendel. That is the design, not a convention.

## Where next

- Your tool is missing → [writing-a-contract.md](writing-a-contract.md)
- A choice should depend on your data → [writing-a-rule.md](writing-a-rule.md)
- You do not know your `read_length` → [measuring-your-data.md](measuring-your-data.md)
- You want your lab's own registry → [registry-layers.md](registry-layers.md)
