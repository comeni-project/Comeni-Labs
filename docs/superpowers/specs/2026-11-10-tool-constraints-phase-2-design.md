# Tool constraints, phase 2: optional files in shared slots, input types and modes

Part 2 of #463, issue #464. Follows phase 1 (#460,
[its design](2026-11-06-tool-constraints-phase-1-design.md)).

## Why

The goal for #463 parts 2–5 (operator, 2026-11-10): **import a tool easily, and the builder
then really builds with it.** A survey of 33 widely used nf-core modules (appendix) checked
what each needs that a contract cannot say today. Two findings set this phase:

1. **The biggest blocker is not in #464 as written.** A module often passes an optional file
   in the same tuple as a required one: `tuple val(meta), path(input), path(input_index),
   path(intervals), path(dragstr_model)`. Phase 1 refuses that shape (`MD0601`, *mixes
   required and optional inputs*). It also refuses several optional files in one tuple
   unless they form one `all_or_none` group. Twelve of the 33 modules have one of these
   shapes. **The operator chose to make this fix the first piece of phase 2.**
2. #464's items, which checks depend on which file type came in, and modes, unblock five more
   (minimap2, picard markduplicates, samtools view, deeptools bamcoverage, bedtools genomecov;
   salmon quant for modes).

## Goals

- **A. Optional files in shared slots.** An `nf_inputs` entry may mix required and optional
  ports, and may hold several optional ports that are independent of each other. A port left
  out of a tuple gets `[]` in its position.
- **B. One join per port.** An entry may pair some later ports per sample and broadcast
  others. gatk's `input_index` is per sample; its `intervals` is one file for the run.
- **C. Type facts.** A constraint or `produced_when` may test which accepted type was
  connected to a port: `type.reads: alignment.bam`. Routing already picks one alternative of
  a port's `accepts`. The pipeline now records which, and constraints are evaluated with it.
- **D. Modes as constraint rows, with a gap check.** A mode is a set of rows on the same fact
  (salmon: BAM reads require `transcript_fasta` and forbid `index`; FASTQ reads require
  `index`). The load-time check also proves every accepted type of a port has at least one
  valid setup.
- **E. The forge drafts all of it.** The item guide and the draft prompt cover mixed slots,
  per-port joins and type facts. Forge checks and tests accept them, and a forge test may
  leave out a port in a shared slot.
- **F. The builder shows it.** An optional port in a shared slot behaves like any phase-1
  optional port on the step card. A type-fact row that refuses a connection shows its
  sentence.

## Non-goals

- **An optional per-sample file left blank in the samplesheet.** That is part 5 (#466). Phase
  1 refuses it at emission; this phase keeps that refusal for ports joined `by_sample`.
- **Derived facts and data-dependent settings** (macs3 `gsize`, STAR's index size): part 3,
  #461.
- **Facts measured over the whole file during a run:** part 4, #465.
- **Pairings between samples** (IP and control, tumour and normal): part 5.
- **A named `mode` concept.** Rows plus type facts already say what salmon needs (decision D).
- **minimap2 with no reference** (reads mapped against themselves) is a different job, so it
  becomes a separate contract (operator, 2026-11-06). That is registry data, not engine work.

## Anti-goals

- A pipeline that runs green with a file silently dropped or paired with the wrong sample. A
  `[]` slot is emitted only where the contract declares the port optional and it is off.
- A type fact that a model invents. Its values must be the port's `type_id` or one of its
  `accepts`, checked at load.

## Constraints

- Invariants as in `CLAUDE.md`: `comeni-core` and `mendel-resolver` stay pure; same inputs and
  recorded decisions give the same output; vocabularies are closed.
- No compatibility before v0.1.0. Existing contracts in registry v0.8.1 must still load,
  because the registry's CI checks the layer against this engine.
- **Vocabulary.** v0.8.1 has `alignment.bam` but no CRAM or SAM type. Type facts compare
  vocabulary type ids, so picard's "CRAM needs the reference" needs `alignment.cram`. That
  type comes through the forge's vocabulary flow (#441) or by hand in the registry, not
  through this engine change. Test overlays declare the types they need.

## Design

### A. Optional files in shared slots (`comeni-core`, `mendel-compiler`)

- **MD0601 narrows.** It still refuses:
  - an entry with optional ports and no `absent` width when **all** its ports are optional and
    all may be off together;
  - `absent` on an entry whose ports are all required.

  It no longer refuses mixing, or several independent optional ports. The rule "several
  optional ports must be one `all_or_none` group" goes. Groups still say which ports go
  together, and constraint checks enforce them.
- **Emission.** For each entry, the compiler builds the tuple from the ports that are **on**:
  - The first port that is on is the head. Later ones are added per their join.
  - Then one `.map { meta, a, c -> [meta, a, [], c] }` puts `[]` in the position of each port
    that is off, so the order matches the module's input block.
  - An entry whose ports are all off still uses `absent` (phase 1's empty tuple).
  - *My call:* joins are declared relative to the first declared port. When that port is
    optional, the first port that is on takes its place. This is only sound if the later
    ports all join the same way, so MD0601 refuses an entry whose first port is optional and
    whose later ports mix `by_sample` and `broadcast`. spades (all per sample) passes.
- **An optional port switched to "optional at run"** (run-scoped) inside a shared slot uses
  phase 1's ternary, `params.x ? (channel) : Channel.value([[:], []])`. It joins by
  `broadcast`, so when it is empty its slot reads `[]`. Such a port joined `by_sample` is
  refused (part 5, as now).

### B. One join per port (`comeni-core`, `mendel-compiler`)

- `NfInput.join` accepts either a `Join` (as now, for every later port) or a map from each
  later port to a `Join`. *My call:* the scalar stays as shorthand rather than being migrated,
  because featureCounts in the released registry uses it and it is not a legacy form.
- Validation: with a map, every port after the first is named exactly once.
- Emission chooses `.join(...)` or `.combine(... .map { it[1] })` per port, as today per
  entry.

### C. Type facts (`comeni-core`, `mendel-resolver`, artifact)

- **Syntax:** `type.<port>: <type id>` or `type.<port>: [<type id>, …]`, in a constraint's
  `when`, a group's `when` and `produced_when`. Load-time validation (`MD0602`) refuses a port
  that does not exist and a type that is not that port's `type_id` or one of its `accepts`.
- **Recording:** `StepInput.type_id`, the type of the source routing connected (the value
  `_source_for` already returns, or the goal input's type for an entry channel). It is sorted
  and serialised like the other fields. `pipeline_authoring_turn` and `SERIALISED_SHAPE`
  change as phase 1's did.
- **Evaluation:** `Setup` gains `types: dict[str, str]`. `_facts` adds `type.<port>` for each
  port that is on. The resolver passes the recorded types when it checks constraints after
  resolution, so phase 1's "switch on by need" turns on salmon's `transcript_fasta` for BAM
  reads.
- **Run time:** none. A port's type is fixed at build time, so no type fact holds at run time.

### D. Modes as rows, and the gap check (`comeni-core`)

- `check_constraints` enumerates, for each port with `accepts`, its type id and each
  alternative, in the product with the optional inputs and params. `SETUP_BOUND` and `MD0607`
  still apply.
- **New `MD0608`:** for an accepted type of a port, no combination is valid. For example,
  "salmon: with `reads` as `alignment.bam`, no combination of inputs satisfies its
  constraints". This is the *gap* check. An *overlap*, two rows that contradict for the same
  type, has no valid setup either, so it is caught the same way.
- `MD0604` and `MD0605` still judge optional ports across all valid setups, now including
  types.

### E. The forge (`mendel-forge`, prompts)

- The item guide (`parts/items.v1.md` → `v2`) covers a port that is optional inside a shared
  slot, a per-port `join` and `type.` conditions. The draft prompt moves to the next version.
  The test that keeps the guide in step with the item kinds still holds.
- Forge drafting reads `meta.yml` patterns. When an input's pattern lists several formats
  that map to different vocabulary types, the draft proposes `accepts`. A type the vocabulary
  lacks becomes a vocabulary question (#441), never an invented id.
- Forge checks run `check_constraints` (so `MD0608` reaches the draft's findings). Forge tests
  may leave out a port in a shared slot (extending #470's fix).

### F. The builder (`mendel-api`, `frontend`)

- The step card already draws optional ports (#460, Task 14). An optional port in a shared
  slot needs no new drawing. Its view model must report it the same way.
- A row on a type fact that refuses or requires something gives the step card its sentence,
  through the existing verdict path.

## Proof

These module shapes are built as test overlays, routed, materialised and emitted, and their
emitted text is pinned:

| Module | Shows |
|---|---|
| gatk4/haplotypecaller | a mixed slot with a per-sample index and a broadcast `intervals`; `dbsnp`/`dbsnp_tbi` all-or-none |
| spades | three independent optional reads in one slot, `any_of` |
| salmon/quant | type facts: BAM reads require `transcript_fasta` and forbid `index` |
| picard/markduplicates | type facts: CRAM requires `fasta` (an overlay declares `alignment.cram`) |
| quast | phase 1 unchanged |

The live forge import of these modules, and running them, happen in the walk at the end of
parts 2–5 (operator, 2026-11-10).

## Left to the builder

- How the reorder `.map` is spelled, as long as the emitted tuple order is pinned by tests.
- Diagnostic wording, following `docs/design/voice.md`.
- Whether `StepInput.type_id` is omitted when it equals the port's own `type_id`, as long as
  the digest is stable.

## Appendix: the module survey (2026-11-10)

nf-core/modules at `86a1000af` (2026-11-04). "Shared slot" means an optional file inside a
tuple with other files.

| Module | Needs | Phase |
|---|---|---|
| fastp | optional adapter in the reads tuple; merge only for paired-end | 2 (A); 5 |
| cutadapt | none | — |
| bwa/mem, bwa/index | none (`ext.args2` already reachable) | — |
| bowtie2/align, bowtie2/build | none | — |
| minimap2/align | FASTQ or BAM reads; BAM requires reference; no reference is a separate contract | 2 (C) |
| minimap2/index | none | — |
| salmon/quant | index, gtf, transcript FASTA in one tuple, which ones depending on reads type | 2 (A, C, D) |
| salmon/index | optional genome FASTA in the transcript tuple | 2 (A) |
| kallisto/quant | optional gtf and chromosomes in the index tuple; fragment length for single-end | 2 (A); 5 |
| picard/markduplicates | CRAM requires the reference | 2 (C) |
| gatk4/haplotypecaller | optional intervals and DRAGstr model in the input tuple | 2 (A, B) |
| bcftools/mpileup | optional interval files in the BAM tuple | 2 (A) |
| bcftools/call | none | — |
| freebayes | optional second input and targets in one tuple; tumour/normal pairing | 2 (A); 5 |
| spades | three optional read kinds in one tuple | 2 (A) |
| megahit | optional second reads file in the tuple | 2 (A) |
| prokka | none | — |
| kraken2, bracken | none | — |
| deeptools/bamcoverage | BAM or CRAM; CRAM needs the reference | 2 (C) |
| macs3/callpeak | optional control in the IP tuple; `gsize` from genome size; IP/control pairing | 2 (A); 3, 4; 5 |
| bedtools/genomecov | BAM, BED, GFF or VCF; sizes unless BAM | 2 (C) |
| samtools/view | optional index in the input tuple; CRAM needs the reference | 2 (A, C) |
| samtools/flagstat | none | — |
| untar, gunzip, cat/fastq | none | — |
| mosdepth | optional BED in the BAM tuple | 2 (A) |
| bismark/align | none | — |
| star/align | none | — |
| star/genomegenerate | index size from genome length | 3, 4 |
| subread/featurecounts | none (strandedness travels in `meta`) | — |
