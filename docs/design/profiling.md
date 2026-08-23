# Profiling: where measurements come from

**Date:** 2026-08-03
**Status:** Approved. Not yet implemented.
**Extends:** [`rule-tables-and-port-logic.md`](rule-tables-and-port-logic.md)
§6, which declares what a measurement *is*. This document says where its value comes from.
**Constrained by:** [`clinical-data-protection.md`](clinical-data-protection.md)
§3 and invariant 15.

Tier 3 resolves against measured data. Nothing in Mendel produces a measurement, and the
component that would has never had an owner.

---

## 1. The decisions

| Question | Decision |
|---|---|
| Who profiles? | A **generated Nextflow pipeline** the laboratory runs. Mendel opens no files |
| What is a measurement, mechanically? | A **type** that modules produce — `measurement.<id>` |
| How is a profiling pipeline built? | By routing, exactly like any other build |
| CLI | `mendel profile` is sugar for `mendel build --want measurement.*` — one code path |
| Measurable vs asserted | Falls out of routability. No flag to maintain |
| Provenance | Per value. A bare scalar **is** an assertion |
| Clinical | `sealed` blocks a tier-3 decision driven by an asserted measurement |
| Execution at scale | The laboratory's own executor. Wiener later dispatches and observes; it never **schedules** — [execution-boundary.md](execution-boundary.md) |

---

## 2. The constraint that rules out the obvious answer

The obvious design is `mendel profile` reading FASTQs and printing four numbers.

It cannot be built, because **"Mendel does not receive patient data" would become false.** Not
weakened — false. That sentence is the strongest claim in the clinical spec, and its strength is
non-receipt: minimisation because there is nowhere to put the data, not because we promise to be
careful with it. A subcommand that opens a patient's reads ends it.

So profiling must happen where the data already is, in the laboratory's own execution
environment, and only values may come back.

---

## 3. Profiling is the compiler pointed at a different target

*"Given some input data, produce some values"* is the same sentence as *"given some input data,
produce a counts matrix."* Mendel already solves that.

**A measurement is a type that modules produce.**

```yaml
id: comeni/profile/fastqc@0.12.1
consumes: [{name: reads, type_id: fastq.reads}]
produces: [{name: read_length, type_id: measurement.read_length}]
```

```yaml
id: comeni/profile/seqkit-stats@2.8.0
consumes: [{name: sequences, type_id: alignment.fasta}]
produces:
  - {name: n_taxa,        type_id: measurement.n_taxa}
  - {name: gap_fraction,  type_id: measurement.gap_fraction}
```

A profiling build is a build whose `want` is a set of measurements. Backward chaining, gap
insertion, the four tiers, decision records, emission and the gates all apply unchanged. There is
no profiler subsystem, because there is nothing for one to do.

The measurement declaration (rules spec §6.2) keeps its job — `kind`, `values`, `unit`, `cite`,
`extensible`, `deprecated` — and additionally **derives** the type `measurement.<id>` carrying no
states, so vocabularies and measurements remain one source rather than two that drift.

### 3.1 Why this generalises, which the first draft did not

An earlier sketch had measurements name their producer directly:
`measured_by: {module: nf-core/fastqc, multiqc_key: fastqc.avg_sequence_length}`. That works for
sequencing QC because MultiQC exists to parse it, and for nothing else. It described one domain's
pipeline and called it *the profiler*.

Routing has no such bias. Nothing in `mendel-resolver` knows what a FASTQ is:

| Domain | Input type | Measurements | Measured by |
|---|---|---|---|
| RNA-seq | `fastq.reads` | read length, strandedness | FastQC, RSeQC |
| Phylogenetics | `alignment.fasta` | taxa count, gap fraction, residue alphabet | seqkit |
| Variant calling | `alignment.bam` | mean depth, target coverage | mosdepth |
| Metagenomics | `fastq.reads` | host fraction, diversity | kraken2, bbduk |
| Proteomics | `spectra.mzml` | instrument, fragmentation mode | ThermoRawFileParser |

Domain support is contracts in a registry layer. A phylogenetics laboratory installs phylogenetics
profiling contracts; `mendel-resolver` never changes. This is what makes "all of bioinformatics"
a registry question rather than a roadmap.

### 3.2 Collection

Modules emit files; a goal needs scalars. One contract closes the loop —
`comeni/profile/collect` consumes `measurement.*` and produces `profile.yml`. That is MultiQC's
role generalised and declared rather than special-cased, so it works for a domain MultiQC has
never heard of.

---

## 4. `mendel profile` is sugar

```bash
mendel profile --have fastq.reads --out profile.yml       # what a user looks for
mendel build --want measurement.read_length,measurement.strandedness   # the same operation
```

**One resolver, one emitter, one set of decision records.** The verb exists for discoverability;
the general form stays available for anyone who wants to mix measurements and analysis in a single
build, or who wants only the two measurements they actually lack.

---

## 5. Measurable or asserted

Some measurements cannot be computed from data by any tool: `library_kit`, `sample_source: ffpe`,
`tumour_normal_paired`. Others can, but the laboratory already knows them and would rather not
pay for a pass over a cohort.

**No flag records which is which.** If no contract in the installed registry produces
`measurement.organism`, a profiling build reports it unroutable, and the user asserts it instead.
So "is this measurable?" is a property of the registry you installed, computed on demand, and it
cannot go stale the way a hand-maintained flag would.

### 5.1 Provenance is per value, and a bare scalar is an assertion

Spec §6.1 justifies tier 3 being yellow rather than green because *"a rule match is only as good
as the rule **and the measurement**"*. A rule firing on a number FastQC computed and the same rule
firing on a number somebody typed are not equally trustworthy, and today nothing can tell them
apart.

A generated profile carries provenance:

```yaml
measurements:
  read_length:  {value: 150, source: measured, by: comeni/profile/fastqc@0.12.1}
  strandedness: {value: reverse, source: measured, by: comeni/profile/rseqc@5.0.3}
```

A hand-written goal does not, and does not need to:

```yaml
profile:
  read_length: 150        # a human typed this, so it is asserted
  library_kit: nextera
```

**The shorthand is not an abbreviation, it is the meaning.** A scalar in a file a person wrote is
an assertion by that person. The syntax matches the semantics, so nothing has to be remembered.

Provenance flows into the IR, the decision record and the lockfile. A tier-3 decision driven by an
asserted value stays tier 3 — the rule did match, and the tier describes how the *value* was
decided, not how its input was obtained — but its `reason` says so, and it appears in review.

### 5.2 `sealed` requires measured values

Under the `sealed` protection profile, a tier-3 decision driven by an asserted measurement
**blocks the build**, as an unresolved tier 4 does. Needs `ProfilePolicy` from Plan 2 — tracked as
[#2](https://github.com/comeni-project/Comeni-Labs/issues/2). A clinical pipeline should not select an
aligner because somebody typed a read length. `open` and `guarded` flag it and continue.

This is the first time the protection profiles constrain *correctness* rather than *egress*, and
it is deliberate: the profiles describe how much a deployment is willing to take on trust, and an
asserted measurement is exactly that.

---

## 6. The regress, and how it is stopped

A build resolves tier-3 parameters against a profile. A profiling build is a build. Left alone,
profiling would require a profile.

**A profiling build runs with an empty `DataProfile`.** Profiling contracts therefore resolve at
tiers 1, 2 and 4 only, and a tier-3 rule on a profiling module simply never fires.

The rule is cheap; leaving it unwritten is not. The first person to add a tier-3 rule to a
profiling contract creates a loop that is confusing to diagnose, so this is stated as a constraint
and enforced by a test.

---

## 7. Execution belongs to the laboratory

`run_gate` shells out to `nextflow run` synchronously with a timeout. That is right for a stub run
of a minute and wrong for profiling five hundred genomes, where a mosdepth pass is hours: no
progress, no resume, no diagnosis of which sample failed, and a timeout that must exceed the
longest imaginable job.

Nothing needs building. Nextflow already dispatches to SLURM, LSF and Kubernetes, so the
laboratory points the emitted pipeline at its own executor. **Mendel emits; it does not
orchestrate.**

Wiener later adds observation and dispatch to specific clusters on top of that — monitoring and
feedback, not scheduling. It is a decoupled concern and stays deferred.

---

## 8. Costs, stated

- **Two runs.** Profile, then build. Heavy for four numbers. A small local fast path — peek at the
  first thousand reads, answer in seconds without Docker — is a plausible later addition for cheap
  measurements over common types. It is a shortcut for the slow path, not a competing design, and
  it is YAGNI until the slow path exists to compare against.
- **Profiling costs compute.** Deliberately visible: the pipeline is emitted before it runs, so a
  user can see that `mean_depth` means a pass over every BAM and choose to assert instead.
- **A second product surface.** Profiling contracts are contracts, but somebody must write them
  per domain, and the RNA-seq set is the only one this project will ship.

---

## 9. Open questions

- **Naming.** `measurement.read_length` as a type and `read_length` as a declaration are close
  enough to confuse in error messages. Worth settling before either reaches a registry.
- **Where an assertion's author is recorded.** A generated profile names the tool; a hand-written
  one names nobody. Under `sealed`, attribution already exists (clinical spec §5.5) and could
  carry it, but a goal written outside a build has no actor.
- **Profiling a cohort versus a sample.** Measurements like `read_length` are per-sample, and a
  build needs one value. Mean, median, or a per-sample profile the pipeline fans out over, is
  unresolved and is the question most likely to change the shape of `profile.yml`.
