# Your first pipeline

Fifteen minutes. You will build a real RNA-seq pipeline, read the reason behind every choice
it made, and change one number to watch a different tool get picked.

Every command and every output on this page was run against this repository. If yours differs,
that is a bug — please [open an issue](https://github.com/comeni-project/Comeni-Labs/issues).

## 1. Get set up

You need [`uv`](https://docs.astral.sh/uv/) and Python 3.12 or later.

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
```

`--recurse-submodules` is not optional. The registry — every tool Mendel knows about — is
[its own repository](https://github.com/comeni-project/comeni-registry) mounted at `registry/`.
Without the flag that directory is empty and nothing will build. If you already cloned without
it: `git submodule update --init`.

## 2. Look at what you are asking for

Open `examples/rnaseq-goal.yml`. It describes an analysis as a **shape**:

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

*What you have, what you want, and what the data looks like.*

Notice what is missing: no filenames, no paths, no sample names. There is nowhere to put one.
That is enforced, not merely encouraged — see [what leaves](concepts/privacy-and-egress.md).

## 3. Build it

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/
```

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

Two lines, and the second is the whole point of the tool. Five tools were chosen. Four needed
nothing from you. One setting could not be decided by any rule, so it is **flagged rather than
guessed**.

You now have `build/main.nf`, `build/nextflow.config`, `build/modules/` — and
`build/pipeline.yml`, which is the one worth reading.

## 4. Read what it decided

`pipeline.yml` is not a log of the build. It **is** the pipeline: every step, every setting,
and a reason beside each one.

```bash
uv run python -c "
import yaml
p = yaml.safe_load(open('build/pipeline.yml'))
for s in p['steps']:
    print(f\"{s['id']:24s} tier {s['why']['tier']}\")
"
```

```
trimgalore               tier 2
star_genomegenerate      tier 2
star_align               tier 3
samtools_sort            tier 2
subread_featurecounts    tier 2
```

Four tools at **tier 2**: nothing else in the registry does that job, so there was no choice to
make. One at **tier 3**: a rule looked at your data and fired.

Read that rule's full reason:

```bash
uv run python -c "
import yaml
p = yaml.safe_load(open('build/pipeline.yml'))
print([s for s in p['steps'] if s['id']=='star_align'][0]['why']['reason'])
"
```

```
rule implementation:alignment where read_length is 150, asserted, not measured: STAR's
seed-and-extend search is built for long reads and is nf-core/rnaseq's default aligner; the
index cost it pays back over reads this length; Dobin et al. 2013,
doi:10.1093/bioinformatics/bts635
```

The reason names the rule, the fact it read, **that the fact was asserted rather than measured**,
and the paper. That is what "nothing was guessed silently" means in practice.

## 5. Find the thing it would not guess

```bash
uv run python -c "
import yaml
p = yaml.safe_load(open('build/pipeline.yml'))
for s in p['steps']:
    for v in s['settings']:
        if v['why']['tier'] == 4:
            print(s['id'], v['name'], '=', v['value'])
            print(' ', v['why']['reason'])
"
```

```
star_align seq_platform = None
  no rule covered 'seq_platform'; selected the first of 1 candidates without judgement — please review
```

`None`, not a plausible default. Nothing in the registry knows which sequencing platform you
used, so Mendel says so instead of picking one. **A tier-4 choice is always flagged, however
confident anything is** — that is the difference between this and asking a chatbot.

The [four tiers](concepts/tiers.md) explain the ladder. Briefly: tiers 1 and 2 are silent,
tier 3 is worth a glance, tier 4 needs you.

## 6. Change one number

This is the part worth doing yourself. Set the reads to 50bp and rebuild:

```bash
sed 's/read_length: 150/read_length: 50/' examples/rnaseq-goal.yml > /tmp/short.yml
uv run mendel build --goal /tmp/short.yml --out /tmp/short-build/
```

```
5 modules, 1 requiring review
  REVIEW  hisat2_align.seq_platform
```

**STAR became HISAT2**, and so did the index step that feeds it. You changed a fact about the
data; a declared rule read that fact and chose differently. Nothing about the goal named a tool.

Rebuild with the original number and you get STAR back, byte for byte. Same goal in, same
pipeline out.

## 7. Run it

Mendel emits a pipeline. **Your laboratory runs it** — your data never passes through Mendel,
which is why `nextflow.config` declares every input as `null` for you to fill:

```bash
cd build
nextflow run main.nf -profile docker \
  --input 'data/*_R{1,2}.fastq.gz' \
  --gtf reference/genes.gtf
```

To check the wiring before you have data, `--gate stub` runs the whole graph with dummy
outputs. It needs Docker and Nextflow, and the first run pulls containers — allow fifteen
minutes, then seconds thereafter:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
```

## Where to go next

| you want to | read |
|---|---|
| do this properly, end to end | [Driving Mendel](guides/driving-mendel.md) |
| watch a run rather than read a file | [Running the stack](guides/running-the-stack.md) |
| stop asserting `read_length` and measure it | [Measuring your data](guides/measuring-your-data.md) |
| add a tool Mendel does not know | [Driving the forge](guides/driving-the-forge.md) |
| understand why a tool was picked | [Routing](concepts/routing.md) |
