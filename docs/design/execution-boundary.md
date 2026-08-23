# The execution boundary: what Mendel hands to Wiener

**Date:** 2026-08-23
**Status:** Proposed. Nothing in §6 is implemented; §2 and §5 describe code that exists.
**Constrained by:** [`clinical-data-protection.md`](clinical-data-protection.md) §3 and
invariants 10, 13 and 15.
**Settles:** a three-way contradiction between [`mendel.md`](mendel.md) §2 and
[`profiling.md`](profiling.md) §1 and §7 about whether Wiener orchestrates.

Mendel resolves a goal, emits Nextflow, and proves the emitted thing runs. Something else
runs it on a laboratory's real data. That second thing is **Wiener**, and the line between
them has never been written down.

---

## 0. Why this document exists

The boundary is not undocumented. It is documented three times, and the three do not agree.

| Where | What it says |
|---|---|
| [`mendel.md`](mendel.md) §2 | Wiener will "**run pipelines** on Azure/AWS, monitor, auto-diagnose failures" |
| [`profiling.md`](profiling.md) §1 | "The laboratory's own executor. Wiener observes later; **it never orchestrates**" |
| [`profiling.md`](profiling.md) §7 | "Wiener later adds observation and **dispatch** to specific clusters … monitoring and feedback, **not scheduling**" |

*Runs pipelines*, *never orchestrates* and *dispatch but not scheduling* are three different
products. The disagreement has cost nothing so far because Wiener does not exist — but the
question stopped being hypothetical the moment the builder grew a canvas with a place to put a
**Run** button, which is the decision this document was written to precede.

**The sentence to keep is `profiling.md` §7's:** *Mendel emits; it does not orchestrate.* It is
the narrowest of the three, it is the one already load-bearing in code, and the other two are
patched to match it rather than the reverse.

---

## 1. The decisions

| Question | Decision |
|---|---|
| Who runs a pipeline on real data? | The **laboratory's own executor**, configured by the laboratory. Never Mendel |
| What does Mendel run, then? | **Gates** — its own artifact, on curated public data, to prove the emission is sound |
| What crosses the boundary? | A gated `pipeline.yml` and the emitted files beside it. Nothing else |
| What does the runner supply? | Paths, credentials, compute, the executor, the work directory |
| Where does the executor live? | In configuration supplied **at run time** — never in `pipeline.yml`, never in `main.nf` |
| Local, Kubernetes, AWS? | One emission task for all three, because Nextflow abstracts them. Three deployments on the far side |
| Does Wiener schedule? | **No.** It dispatches to an executor the laboratory already runs, and it observes |

---

## 2. There are two runs, and they must not share a name

This is the whole boundary in one table.

| | **Gate** | **Run** |
|---|---|---|
| what it runs on | curated public test data, pinned by commit | the laboratory's real data |
| takes a path? | **no** | **yes** — a samplesheet |
| how long | 60s to 3600s, bounded | unbounded |
| what it proves | the artifact is sound | a biological result |
| where the verdict goes | `Pipeline.gate` in the artifact | the laboratory's own systems |
| whose | **Mendel** | **Wiener**, or the laboratory directly |

The gate ladder is `LINT → PREVIEW → STUB → TEST`, declared in `comeni_core/artifact/gates.py`
and run by `mendel_compiler/gates.py`. `Gate.TEST` is a genuine `nextflow run` producing a
genuine counts matrix — this is not a simulation, and Mendel has been doing it since Plan 1.5.
So *"Mendel does not run Nextflow"* is false and has always been false. The true statement is
narrower and is the one that matters:

> **Mendel runs its own artifact against data somebody else published. It never runs a
> laboratory's data.**

**The test for which side of the line you are on is one question: does the run take a
samplesheet?** If it does, it is a Run. There is no third case, and the question is decidable
by looking at the arguments.

**They must not share a label on screen.** A single control called *Run* that sometimes gates
and sometimes executes is how invariant 15 dies: not by anyone deciding to weaken it, but by a
text field appearing under a button whose meaning drifted. `docs/design/dashboard.md` has no
Run button, and it should acquire a **Gate** button first.

---

## 3. What crosses

Two things, and they are already built.

- **`pipeline.yml`** — the goal, every step and setting with a `why:`, every contract pinned by
  content digest, every layer, and `gate:` naming the strongest gate it actually passed.
- **The emitted files** — `main.nf`, `nextflow.config`, and the vendored modules, whose digests
  `Pipeline.emitted` records.

Nothing else. In particular **no run request, no input manifest and no credentials**, because
each of those is a path or a secret and neither belongs on Mendel's side.

`comeni-core` already anticipates this: it "keeps the platform name rather than the product
name because its IR is the interface Wiener will consume". This document is the first one to
say what *consuming* it means.

**The handoff is a directory, not an API call.** Wiener reads an artifact Mendel wrote; Mendel
never learns that Wiener exists. That keeps invariant 13 honest — a self-hosted install with no
Wiener at all is not a degraded tier, it is the normal case, and the laboratory runs
`nextflow run` itself.

---

## 4. What the runner supplies

Everything the artifact deliberately does not carry:

| Supplied at run time | Why not in the artifact |
|---|---|
| `params.input` and every other input path | invariant 15 — a path is patient-adjacent data |
| credentials, IAM roles, kubeconfig | secrets never belong in a reviewable artifact |
| `workDir` (local path, PVC, or `s3://…`) | a site fact, and it is where the data lands |
| the executor and queue | §5 |
| resource ceilings for the site | a lab with 8 cores and a lab with a cluster emit the same pipeline |

This is the same shape as `params.input`, one level up. `emit_config` already defaults every
input parameter to `null` — "the pipeline describes a shape and the laboratory supplies the
data at run time, which is invariant 15 surviving into the configuration as well as the
workflow". The executor is that argument applied to *where it runs* rather than *what it reads*.

---

## 5. The executor must not enter the artifact

**This is the rule that constrains code, and it is the reason to write this page before
building anything.**

If a pipeline built for AWS differed from the same pipeline built for local, then:

- **Invariant 10 breaks** — same `Goal` no longer gives byte-identical `.nf`.
- **The product claim breaks** — "same goal in → same pipeline out" acquires a silent second
  input nobody named.
- **`Pipeline.emitted` breaks** — the recorded digests would depend on a deployment choice, so
  `mendel emit` could not reproduce the file it is handed.
- **Invariant 13 breaks** — a cloud target and a laptop target would produce different
  artifacts, which is the definition of a degraded tier.

So the executor is a **profile**, and the profile is a function of nothing:

> **`emit_config(pipeline)` must never take a target as an argument.**

That is testable, and it is the guard this decision deserves: a signature with one parameter
cannot express a per-target emission. Every pipeline gets the same `k8s` and `awsbatch`
profiles whether or not anyone will use them, exactly as every pipeline already gets `docker`
and `singularity` blocks it may never select.

What Mendel emits today (`emit.py:388`):

```
profiles { stub_data · test · docker · singularity }
```

There is **no executor block at all**, so everything defaults to `local`. That is the gap, and
it is one function.

**Site-specific configuration is Nextflow's own problem and it already solved it.** A
laboratory needing a queue name, a storage class or a role ARN passes `-c site.config`;
Nextflow layers it over what Mendel emitted. Mendel emits what it can state generically for
everyone and stays out of the rest — the same division as `params.input`.

---

## 6. Local, Kubernetes and AWS

Nextflow has executors: `local`, `k8s`, `awsbatch`. Same `main.nf`, same modules, same
containers; the backend is a configuration concern. That makes the three-target requirement
lopsided in a way worth stating plainly, because it changes what "in the MVP" costs:

| | Mendel's side | The runner's side |
|---|---|---|
| **local** | done | done |
| **Kubernetes** | a profile | head pod, service account, a shared PVC for `workDir`, image pull |
| **AWS** | a profile | Batch compute environment, IAM, `workDir` on S3 |

**One emission task covers all three. Three deployments do not.** Mendel is not the bottleneck
for any of them, and finishing Mendel's side of all three costs about what finishing local
alone costs.

---

## 7. What this means for the gate loop

The near-term work — putting a **Gate** button on the builder — sits entirely inside Mendel's
half, and `profiling.md` §7 already wrote its warning:

> `run_gate` shells out to `nextflow run` **synchronously with a timeout**. That is right for a
> stub run of a minute and wrong for profiling five hundred genomes.

A gate is the bounded case, so synchronous execution is not wrong for it — but 900s cold for a
stub gate is still far outside a request. `mendel-api`'s worker docstring already names this
exact job as the thing that belongs in ARQ, and was given only `check_sources`. So the loop is:
the builder queues a gate, the worker runs it, the verdict lands on screen and in
`Pipeline.gate`, and the flow **stops there**. The next thing a person does with that artifact
is outside Mendel.

---

## 8. What was rejected

- **A Run button in Mendel that takes a samplesheet.** It is the shortest path to a demo and it
  makes "Mendel does not receive patient data" false. Non-receipt is the strongest claim in the
  clinical spec and it is structural: there is nowhere to put the data. A file input field is
  somewhere to put it.
- **Baking the executor into the pipeline.** Rejected for §5's four reasons. It is also the
  version that *looks* more helpful — one artifact per target, ready to run — which is why it
  needs a written argument rather than an instinct.
- **Mendel scheduling work.** `profiling.md` §7 settled it: Nextflow already dispatches to
  SLURM, LSF and Kubernetes, so a scheduler here would be a second, worse one. Wiener dispatches
  *to* an executor; neither Lab replaces it.
- **A Mendel→Wiener API.** The handoff is an artifact on disk. An API would make Mendel depend
  on a component that does not exist, and would give the hosted instance a capability the
  self-hosted one lacks, which invariant 13 forbids.

---

## 9. Costs, stated

- **Two runs before a result**, as with profiling: gate, then run. The gate proves the artifact
  and produces nothing a biologist wants.
- **A laboratory must configure its own executor.** For a single laptop that is nothing; for a
  cluster it is real work Mendel does not help with, and a hosted instance cannot do it for
  them without becoming Wiener.
- **The demo is worse.** "Draw a pipeline and see your counts" is a better ten minutes than
  "draw a pipeline, gate it, then go and run it yourself". That gap is the price of the
  invariant, and it should be paid visibly rather than closed quietly.
- **Wiener is now scoped by subtraction** — it is everything this document hands away — and it
  still has no spec.
