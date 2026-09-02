# The execution boundary: what Mendel hands to Wiener

**Date:** 2026-08-23
**Status:** §1–§7 describe code that exists. **Written as a proposal on 2026-08-23 and
executed the same day** — plan `18a` landed both halves of Mendel's side, the gate loop and the
executor profiles, on branch `mendel-wiener-boundary`. §8 onward is unbuilt: **Wiener has zero
lines.** Sections describing what Mendel emits carry the state *after* that plan; where a
sentence still reads as a prediction it is a defect, because this document's own §0 is about
prose that drifted.
**Constrained by:** [`clinical-data-protection.md`](clinical-data-protection.md) §3 and
invariants 10, 13 and 15.
**Supersedes** the scattered statements in [`mendel.md`](mendel.md) §2 and
[`profiling.md`](profiling.md) §1 and §7, which are patched to point here.

Mendel resolves a goal, emits Nextflow, and proves the emitted thing runs. Something else runs
it on a laboratory's real data, watches it, and does something sensible when it fails. That
second thing is **Wiener**, and the line between them has never been written down.

---

## 0. Why this document exists

The boundary was documented three times and the three did not agree — Wiener "runs pipelines"
([`mendel.md`](mendel.md) §2), "never orchestrates" ([`profiling.md`](profiling.md) §1),
"dispatch … not scheduling" (§7).

**The disagreement was not about the design. It was about vocabulary.** *Schedule*,
*orchestrate* and *dispatch* were each used to mean two different things one section apart, and
nobody had said which. This document defines them first and decides afterwards, because the
first draft of it repeated the mistake: it wrote "Wiener does not schedule" meaning *does not
place tasks onto compute*, which reads as *does not manage runs* — the opposite of true.

The old sentences are evidence that the vocabulary was missing. They are not constraints, and
they get no deference here: Wiener has zero lines of code, so nothing about it is load-bearing
yet.

---

## 1. The decisions

| Question | Decision |
|---|---|
| Who orders tasks, retries them and resumes? | **Nextflow.** It is a workflow engine and this is what one is |
| Who accepts a run, launches it, supervises it, retries it and remembers it? | **Wiener.** Nextflow does none of this |
| Who runs a pipeline on real data? | Wiener, or the laboratory by hand. **Never Mendel** |
| What does Mendel run, then? | **Gates** — its own artifact, on curated public data, to prove the emission is sound |
| What crosses the boundary? | A gated `pipeline.yml` and the emitted files beside it. Nothing else |
| Where does the executor live? | Configuration supplied **at run time** — never in `pipeline.yml`, never in `main.nf` |
| Local, Kubernetes, AWS? | One emission task for all three on Mendel's side. Three deployments on Wiener's |

---

## 2. Three levels, and only one of them is Wiener's

The word *schedule* has been doing three jobs. Separated, the boundary is obvious.

| Level | What it means | Who | Exists? |
|---|---|---|---|
| **Task** | order STAR before samtools, submit each to compute, retry a failed task, resume from cache | **Nextflow** | yes, mature |
| **Run** | accept "run this pipeline on this batch", launch and supervise the head process, know if it is alive, relaunch it, keep history, notify | **Wiener** | **no** |
| **Fleet** | which runs matter, cost, drift, quotas across a laboratory | Wiener, later | no |

**You are right that dispatch-and-check-and-retry is Wiener's entire thing.** It is — at the
**run** level. What Wiener must not do is the **task** level, because that is a mature workflow
engine and a second one would be worse:

- ordering by dependency — Nextflow's DAG is the whole point of it
- submitting to `local` / `k8s` / `awsbatch` / SLURM / LSF — executors, built in
- retrying a failed task — `errorStrategy` and `maxRetries`, and **Mendel can already emit
  both**: they are declared directives in `comeni_core/spell/directives.py`
- not redoing finished work — `-resume`, against the content-addressed work directory

So "check if they ran correctly, rerun if needed" is true twice, at two levels, and both
answers are already right:

> A **task** fails → Nextflow retries it, per the `errorStrategy` the contract declared.
> A **run** fails → **Wiener** decides whether to relaunch it, and `-resume` means the relaunch
> does not start from zero.

**Nextflow is a workflow engine, not a service.** `nextflow run` is a foreground process that
exits and remembers nothing across invocations. There is no queue of runs, no history, no
concurrency across users, no "what is running right now", and nothing notices when the head
process dies. **Every one of those absences is Wiener**, and none of them is a reimplementation
of anything.

The one-line version:

> **Nextflow schedules tasks. Wiener manages runs. Mendel produces the thing being run and
> never runs it on a laboratory's data.**

---

## 3. There are two runs, and they must not share a name

| | **Gate** | **Run** |
|---|---|---|
| what it runs on | curated public test data, pinned by commit | the laboratory's real data |
| takes a path? | **no** | **yes** — a samplesheet |
| how long | 60s to 3600s, bounded | unbounded |
| what it proves | the artifact is sound | a biological result |
| where the verdict goes | `Pipeline.gate` in the artifact | Wiener's run history |
| whose | **Mendel** | **Wiener** |

The gate ladder is `LINT → PREVIEW → STUB → TEST`, declared in `comeni_core/artifact/gates.py`
and run by `mendel_compiler/gates.py`. `Gate.TEST` is a genuine `nextflow run` producing a
genuine counts matrix — Mendel has been doing this since Plan 1.5. So *"Mendel does not run
Nextflow"* is false and always has been. The true statement is narrower:

> **Mendel runs its own artifact against data somebody else published. It never runs a
> laboratory's data.**

**The test for which side you are on is one question: does the run take a samplesheet?** There
is no third case, and it is decidable by looking at the arguments.

**They must not share a label on screen.** A single control called *Run* that sometimes gates
and sometimes executes is how invariant 15 dies — not by anyone deciding to weaken it, but by a
file field appearing under a button whose meaning drifted. The builder should acquire a **Gate**
button; *Run* belongs to Wiener's surface even when the two are served from one deployment.

---

## 4. What crosses

Two things, and both already exist.

- **`pipeline.yml`** — the goal, every step and setting with a `why:`, every contract pinned by
  content digest, every layer, and `gate:` naming the strongest gate it actually passed.
- **The emitted files** — `main.nf`, `nextflow.config`, and the vendored modules, whose digests
  `Pipeline.emitted` records.

Nothing else. In particular **no run request, no input manifest and no credentials**.

`comeni-core` already anticipated this: it "keeps the platform name rather than the product name
because its IR is the interface Wiener will consume". This is the first document to say what
*consuming* means.

**"No run request" is a statement about one direction.** Mendel never sends one. A *person*
sends one — to Wiener, naming an artifact and a samplesheet — and that is Wiener's front door,
not a crossing of this boundary. The two were one phrase in the first draft of this section,
which is the §0 failure repeating: the same words meaning two things one section apart. §8's
first slice accepts run requests; §4 says Mendel does not emit them. Both are true.

**What Wiener still needs, and it is not in the artifact: where the artifact is.** `mendel-api`
locates a gated pipeline as `settings.draft_root / draft_id` (`services/gates.py`), and both of
those are `mendel-api`'s private facts — an environment variable and an opaque database id.
Wiener needs an artifact *location*, and today the only thing that can name one is the half this
document is trying to keep it out of. **That is §8's entanglement, already half-present.** It
wants deciding before Wiener's first slice, not after: a directory convention, a copy at
submission, or an export verb are all cheaper than a shared `draft_root` between two services.

**The handoff is an artifact, not an API call.** Wiener reads what Mendel wrote; Mendel never
learns Wiener exists and never calls it. That is what keeps invariant 13 honest — an install
with no Wiener at all is not a degraded tier, it is the normal case, and the laboratory types
`nextflow run` itself. It also means Wiener can be built, replaced or skipped without touching
a line of Mendel.

---

## 5. What the runner supplies

Everything the artifact deliberately does not carry:

| Supplied at run time | Why not in the artifact |
|---|---|
| `params.input` and every other input path | invariant 15 — a path is patient-adjacent |
| credentials, IAM roles, kubeconfig | secrets never belong in a reviewable artifact |
| `workDir` (local path, PVC, or `s3://…`) | a site fact, and where the data lands |
| the executor and queue | §6 |
| resource ceilings for the site | a lab with 8 cores and a lab with a cluster emit the same pipeline |

Same shape as `params.input`, one level up. `emit_config` already defaults every input parameter
to `null` — "the pipeline describes a shape and the laboratory supplies the data at run time,
which is invariant 15 surviving into the configuration as well as the workflow". The executor is
that argument applied to *where it runs* rather than *what it reads*.

---

## 6. The executor must not enter the artifact

**This is the rule that constrains code.**

If a pipeline built for AWS differed from the same pipeline built for local:

- **Invariant 10 breaks** — same `Goal` no longer gives byte-identical `.nf`.
- **The product claim breaks** — "same goal in → same pipeline out" gains a silent second input.
- **`Pipeline.emitted` breaks** — recorded digests would depend on a deployment choice, so
  `mendel emit` could not reproduce the file it is handed.
- **Invariant 13 breaks** — cloud and laptop would produce different artifacts, which is the
  definition of a degraded tier.

So the executor is a **profile**, and the profile is a function of nothing:

> **`emit_config(pipeline)` must never take a target as an argument.**

That is testable: a one-parameter signature cannot express a per-target emission. Every pipeline
gets the same `k8s` and `awsbatch` profiles whether or not anyone selects them, exactly as every
pipeline already gets `docker` and `singularity` blocks it may never use.

What Mendel emits (`emit_config`, `emit.py:388`):

```
profiles { stub_data · test · docker · singularity · local · k8s · awsbatch }
```

**The last three are this document's doing, and they are one function.** Before plan `18a` there
was no executor block at all, so everything defaulted to `local` implicitly; the profiles now say
so explicitly and add the two remote executors beside it. Each is a **fragment** — `k8s` sets
`process.executor` and nothing else, because a namespace, a storage claim, a queue, a region and
an S3 `workDir` are all site facts by §5. A profile that resolves is a much weaker claim than a
pipeline that runs, and only the first is proven: see
[`../../notes/journal/2026-08-23-the-gate.md`](../notes/journal/2026-08-23-the-gate.md)
§*How far the executor half is actually proven*.

**Site-specific configuration is Nextflow's problem and Nextflow solved it.** A laboratory
needing a queue name, a storage class or a role ARN passes `-c site.config`, which Nextflow
layers over what Mendel emitted. Mendel emits what it can state generically for everyone —
including the `errorStrategy` and `maxRetries` a contract declares — and stays out of the rest.

---

## 7. Local, Kubernetes and AWS

Nextflow has executors: `local`, `k8s`, `awsbatch`. Same `main.nf`, same modules, same
containers. That makes the three-target requirement lopsided, which is worth stating because it
changes what "in the MVP" costs:

| | Mendel's side | Proven how far | Wiener's side |
|---|---|---|---|
| **local** | done | a pipeline **runs** — every gate is one | launch and supervise a subprocess |
| **Kubernetes** | a profile, landed | the profile **resolves**; nothing has run | head pod, service account, shared PVC for `workDir`, image pull |
| **AWS** | a profile, landed | the profile **resolves**; nothing has run | Batch compute environment, IAM, `workDir` on S3 |

**One emission task covers all three. Three deployments do not.** Mendel is not the bottleneck
for any of them.

**The middle column is the honest one and it is why §6 matters.** `nextflow config -profile
awsbatch .` printing `executor = 'awsbatch'` says the file parses and the profile selects; it
says nothing about whether Wave containers pull inside a Batch compute environment, or how
`workDir` orders against executor initialisation. Because the executor is inert configuration
that never enters `pipeline.yml` or `main.nf`, a profile that turns out wrong is an `emit_config`
edit — no schema change, no artifact migration, no `pipeline.yml` in the wild needing a rewrite.
**The rule that was most carefully defended is the one that makes being wrong here survivable.**

---

## 8. What this means for the MVP

Follow §2 honestly and one thing falls out that should be said out loud rather than discovered:

> **An MVP that runs pipelines on local, Kubernetes and AWS contains the first slice of Wiener.**

Run management is not a Mendel feature and Nextflow does not provide it, so if the MVP has a Run
button, something is doing level 2 — and it should be **named Wiener and live behind Wiener's
own boundary**, however small it starts. The failure mode is not building it; it is building it
inside `mendel-api` because that is where the worker already is, and discovering in six months
that run state, credentials and sample paths are entangled with the deterministic half.

The first slice is small and its shape is already clear: submit a run, launch the head process
with an executor profile and a `-c site.config`, record run state, surface progress and failure,
relaunch with `-resume`. It needs no model, no registry and no resolver — only an artifact.

**Mendel's own near-term work stops at the gate**, and it fits the machinery already present.
`mendel-api`'s worker docstring names this exact job as the thing that belongs in ARQ and was
given only `check_sources`. So: the builder queues a gate, the worker runs it, the verdict lands
on screen and in `Pipeline.gate`. That is the whole of Mendel's half.

---

## 9. What was rejected

- **A Run button in Mendel that takes a samplesheet.** The shortest path to a demo, and it makes
  "Mendel does not receive patient data" false. Non-receipt is the strongest claim in the
  clinical spec and it is structural — there is nowhere to put the data. A file field is
  somewhere to put it.
- **Baking the executor into the pipeline.** §6's four reasons. It is the version that *looks*
  more helpful — one artifact per target, ready to run — which is why it needs a written
  argument rather than an instinct.
- **Wiener re-implementing task scheduling.** §2. Ordering, retry and resume are Nextflow's, and
  a second engine would be worse at all three.
- **A Mendel→Wiener API.** The handoff is an artifact on disk. An API would make Mendel depend
  on a component that does not exist, and would give the hosted instance a capability the
  self-hosted one lacks, which invariant 13 forbids.

---

## 10. Costs, stated

- **Two runs before a result**: gate, then run. The gate proves the artifact and produces
  nothing a biologist wants.
- **Wiener is now in the MVP**, by §8. Scoping it as "later" and shipping a Run button anyway is
  the outcome this document exists to prevent.
- **A laboratory must configure its own executor.** Nothing for a laptop; real work for a
  cluster, and a hosted instance cannot do it for them without becoming their Wiener.
- **The demo is worse.** "Draw a pipeline and see your counts" beats "draw it, gate it, then run
  it over there". That gap is the price of the invariant and should be paid visibly rather than
  closed quietly.
