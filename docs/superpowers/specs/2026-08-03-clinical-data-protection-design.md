# Clinical use, data protection, and the egress boundary

**Date:** 2026-08-03
**Status:** Approved.
**Extends:** [`2026-08-02-mendel-design.md`](2026-08-02-mendel-design.md) and
[`2026-08-02-comeni-federation-design.md`](2026-08-02-comeni-federation-design.md). Read those
first. Where this document differs from either, this one wins.

Mendel was designed for researchers. This amendment asks what changes when a clinical
laboratory uses it — a lab running translational research, clinical research, and diagnostics
in the same building, which is the normal shape of a hospital genomics unit rather than an
edge case.

The answer is smaller than it first appears, because Mendel never receives patient data. But
"never" was true by accident, and this document makes it true by construction.

---

## 1. The decisions

| Question | Decision |
|---|---|
| Can a lab use this diagnostically? | Yes — the lab is the manufacturer, we are a tool |
| Where is the safety boundary? | Egress: four declared doors, typed payloads |
| Is protection a mode? | The boundary always holds; three profiles vary the ceremony |
| Default profile | `guarded` |
| De-identification by scrubbing | **Rejected** — see §4.3 |
| Publishable artifacts | Structurally incapable of carrying free text |
| Who authenticates? | Nobody, here. Mendel consumes an identity, never issues one |
| Lockfile scope | Contracts, modules, **container digests, reference data** |
| Curation evidence | GIAB / SEQC2 truth sets; recall testing is the lab's |
| What "curated" means clinically | Reference material to validate, never a validated test |

The through-line: **Mendel does not receive patient data, and the reason is that it has
nowhere to put it.**

---

## 2. Why a clinical lab can use this at all

### 2.1 The manufacturer boundary

A compiler is not a medical device because you compiled device software with it. BWA, GATK,
Nextflow and `nf-core` are in diagnostic pipelines across Europe today, none of them CE-marked
as IVDs. They are used under two regimes that already exist:

- **EU:** the in-house exemption, IVDR Article 5(5) — devices manufactured and used within a
  single health institution, under an appropriate quality management system, meeting Annex I
  general safety and performance requirements, and **not transferred to another legal entity**.
  Most conditions have applied since 26 May 2024; the justification that no equivalent CE-marked
  device exists was extended to 31 December 2030 by Regulation (EU) 2024/1860. Institutions must
  review annually whether an equivalent CE-marked device has appeared.
- **US:** CLIA and CAP accreditation. The FDA's LDT rule was vacated in full on 31 March 2025
  (E.D. Tex.), HHS did not appeal, and FDA rescinded it in September 2025. Laboratory-developed
  tests remain under CLIA, not the device framework.

Under IVDR, device status follows the **intended purpose the manufacturer states**. So the line
is drawn by what we claim, not by what the software can do.

### 2.2 The intended purpose statement

Stated identically in the README, the dashboard, and every emitted artifact:

> Mendel constructs and documents analysis pipelines. It is not a diagnostic device and
> produces no diagnostic result. Pipelines must be validated by the laboratory before clinical
> use.

This is not boilerplate; it is the load-bearing sentence. It is what keeps the manufacturer
boundary where §2.1 needs it, and it is why §6.2 constrains what "curated" may mean.

### 2.3 What this is not

We do not claim compliance with IVDR, CLIA, CAP or ISO 15189, and no software can. Those attach
to a laboratory's processes. What Mendel supplies is the **documentation substrate** those
processes require: which modules, which versions, which parameters, at which tier, decided by
what, against which references. The lab supplies validation, sign-off and accreditation.

### 2.4 Why this is worth doing

The AMP/CAP joint recommendation on validating NGS bioinformatics pipelines (Roy et al., *J Mol
Diagn*, 2018) states that the bioinformatics pipeline **is part of the test procedure** and must
be documented to accreditation standards, and warns that poorly monitored pipelines "may
generate hidden, inaccurate, and/or inscrutable results". That is Mendel's thesis, written by
the profession eight years before this repository existed.

Under CLIA and ISO 15189 a pipeline must be revalidated whenever it changes — including when a
reference database updates. Revalidation is expensive, so labs freeze pipelines and let them
age. `mendel upgrade`, reporting what moved, at which tier, and why, is a change-control
document. Determinism was designed as a research honesty property; in a regulated lab it is an
economic one.

---

## 3. What Mendel receives

### 3.1 Shape, not data

`Goal` holds type IDs (`fastq.reads`, `counts.matrix`), required states, and a `DataProfile` of
measurements — read length, strandedness, sample count, paired. There is no filename field, no
sample identifier field, no path. Mendel builds against a **shape**: *paired, 150bp,
reverse-stranded, 12 samples* is true of thousands of studies and identifies no one.

Profiling happens **where the data is** — beside the FASTQs, in the lab, or as a Nextflow job —
and emits a `DataProfile`. The reads, the filenames and the sample sheet never enter Mendel's
process in any deployment.

The emitted pipeline contains no paths either. It references `params.input` as a placeholder,
exactly as `nf-core` pipelines do, and the laboratory supplies the sample sheet at run time in
its own execution environment.

Consequence worth stating plainly: with local profiling and the `sealed` profile, **nothing
identifying leaves the institution even on the Comeni-hosted instance**, because the only things
that ever cross are type IDs, four integers, and contract IDs. We will still recommend
self-hosting for patient-derived work; the architecture means the guarantee does not depend on
that advice being taken.

### 3.2 Terminology discipline

Never use the word *anonymised*. Genetic data are not reliably anonymisable, and under GDPR
pseudonymised data remains personal data and remains special-category under Article 9. Claiming
anonymisation would be both false and unnecessary, because Mendel's actual position is stronger:
it is data minimisation by non-receipt, the top of the EDPB's hierarchy rather than the middle.

The correct phrasing everywhere is: **Mendel does not receive patient data.**

---

## 4. The egress boundary

### 4.1 Four doors

Data leaves through exactly four paths. Three are model calls; the fourth is publication, and it
is the only one with no undo — a leaked prompt in a model call is an incident, while a leaked
prompt in a signed public registry is in every clone's history forever.

| Door | Payload type | Contains | Implemented in |
|---|---|---|---|
| goal extraction | `PromptRequest` | **free text** — the only taint source | `mendel-ai` |
| tier-4 resolution | `AmbiguityRequest` | contract IDs, type IDs, states, tier hints | `mendel-ai` |
| compiler repair | `RepairRequest` | the IR + `GateFailure` | `mendel-ai` |
| publication | `PublishBundle` | typed goal, IR, decision records, lockfile | `mendel-api` |

Payload **types** are declared in a new `comeni_core/egress.py`; **transmission** stays in the
impure packages. Invariant 1 already prevents a pure package from opening a socket, so pure code
decides what may leave and impure code does the leaving. Neither can do the other's job.

### 4.2 The taint rule

> Free text enters at exactly one door. Anything derived only from typed inputs is publishable;
> anything downstream of the prompt is not.

This is what preserves the explanatory value of the system. `DecisionRecord.reason` is
model-written prose, and prose cannot ride in a typed bundle — but the risk was never that a
model wrote the sentence, it is what the model was handed. Tier-4 resolution receives closed
registry vocabulary, so a reason derived from it can only be about contracts. Typed in, safe
out.

### 4.3 De-identification by scrubbing was considered and rejected

The mainstream approach is a sanitiser that strips identifiers before transmission. It is
rejected as a primary mechanism for three reasons:

1. **It does not meet the standard it appears to meet.** HIPAA Safe Harbor requires removing
   *all 18* identifier classes. NLP-based de-identification does not reliably achieve this;
   false negatives leave identifiers behind. Seventeen of eighteen scrubbed is not
   de-identified — it is confident.
2. **It fails silently.** A scrubber returns success whether or not it caught anything, so the
   failure mode is a false sense of safety, which is worse than known absence of protection.
3. **Identifiers are not the only re-identifiers.** A rare diagnosis in free text can identify a
   person with no identifier present at all.

Pattern matching survives in one inverted form: in `guarded`, a detector **halts the send and
shows the user what it found**. A machine asking a human "this looks like an MRN, is it?" is
useful. A machine silently deleting what it thinks it recognised is a liability.

### 4.4 `GateFailure` — the door nobody watches

The validation gates execute Nextflow. If a laboratory points the `test` gate at real data,
stderr contains work-directory paths and input filenames, and the repair loop would forward it
to a model. Machine-generated text is the most likely leak precisely because no human wrote it
and no human reads it.

So `RepairRequest` never receives stderr. It receives:

```
GateFailure(process: NodeId, exit_code: int, category: ErrorCategory, tool_message: FreeText | None)
```

`ErrorCategory` is a closed vocabulary — `missing_input`, `channel_cardinality`, `syntax`,
`container_pull`, `tool_error` — parsed from the output the same way type vocabularies work. Raw
stderr is retained locally for the human and never crosses. `tool_message` is `None` in `guarded`
and `sealed`; where it is populated it is marked free text, so §4.5's test forces the admission
rather than letting it hide.

### 4.5 How the boundary is enforced

Two tests beside `tests/test_purity.py`, in the same register: mechanical, not aspirational.

**The allowlist is literal.** `tests/test_egress.py` holds the four payload type names as a
constant and asserts the declared set equals exactly that. Adding a door means editing a test
that says *these are all the ways data leaves this building*, which is the moment a person
should be thinking rather than a moment they can skip.

**The free-text marker.** Every string field in a payload type is either a declared ID type
(`ContractId`, `TypeId`, `NodeId`, `Subject` — `Annotated[str, ...]` aliases) or explicitly
annotated `FreeText`. The test walks each payload's annotations and asserts the set of
free-text-carrying fields equals a literal allowlist of **exactly two**:

```
("PromptRequest", "prompt")     the human's prompt — the taint source
("GateFailure", "tool_message") raw tool output, populated only in `open`
```

`tool_message` is on that list rather than exempted from it. It genuinely is free text, and
§4.4's design depends on that being admitted where a reader can see it rather than argued away.
A third entry — someone adding `user_note` to `RepairRequest` — fails the suite until the
allowlist is edited. Leaking by accident is unavailable; leaking requires editing the file named
after the thing being defeated.

The same test forbids any payload field annotated `Any`, because a `dict[str, Any]` carries
anything and would make the rest of the guard decorative. That constraint is what shaped
`AmbiguityRequest`: it declares `node_id`, `subject`, `candidates`, `states` and `tier_hint`
rather than the free-form context dict `Ambiguity` uses internally.

---

## 5. The three protection profiles

Mendel now has three distinct ladders. They are unrelated and must not be conflated:

- **four resolution tiers** — structural / convention / data-profiled / ambiguous (spec §6.1)
- **three visibility tiers** — private / published / curated (federation §4.2)
- **three protection profiles** — `open` / `guarded` / `sealed`, below

### 5.1 What varies

| | `open` | `guarded` (default) | `sealed` |
|---|---|---|---|
| prompt door | sends | shows the exact payload, waits for confirmation | closed — typed goals or templates only |
| `GateFailure.tool_message` | included | `None` | `None` |
| repair | proposes and applies, ≤3 attempts | proposes and applies, ≤3 attempts | proposes only; a human applies |
| tier 4 | flags | flags | **blocks the build** |
| attribution | optional | recorded when available | required |
| publication | typed bundle | typed bundle | typed bundle + named approver |
| reference pinning | tags accepted | tags accepted | digests required (§6.1) |

### 5.2 What never varies

Not configurable at any level, in any deployment:

- data leaves through the four declared doors and no others
- payloads are typed; only `PromptRequest` may carry free text
- every crossing writes an `EgressRecord`
- tier 4 is always flagged and always emits a `DecisionRecord`
- published bundles are typed-only
- Mendel receives no patient data

### 5.3 Why `guarded` is the default

`open` would mean the unconfigured install is the unsafe one, and the unconfigured install is
the one most likely to exist. `sealed` would mean a first-time researcher's first build stops
with errors, which reads as broken rather than careful. `guarded` costs a researcher one
confirmation they can turn off, and protects a clinical lab that installed Mendel and never read
this document. Safety should not depend on having read the manual.

### 5.4 Why `sealed` splits repair

An AI-proposed patch to a validated artifact is a change to a validated artifact, and under CLIA
and ISO 15189 that is a revalidation trigger. The model may still do the diagnostic work —
reading the failure, proposing an IR patch — and a human takes the action. Invariant 5 is
untouched: repair patches the IR, never the generated `.nf`.

### 5.5 Records and identity

**`EgressRecord`**, one per crossing: door, profile, timestamp, actor, destination (provider and
model, or registry URL), and a **digest of the payload rather than the payload**. A log that
stores prompts is a second store of personal data wearing an audit trail's clothes. The digest
proves what left and proves it has not changed, without becoming minable.

**Attribution consumes identity, it never issues it.** Spec §12 excluded authentication from v1
and that exclusion stands. `Actor(id, display_name, method)` where `method` is `local_user` (the
OS user), `api_token`, or `oidc` (the institution's existing SSO). `sealed` refuses to run when
the deployment asserts no identity. We never mint accounts — no hospital wants a genomics tool
running its own identity provider, and building one would be weeks of work to arrive somewhere
worse than what they already operate.

### 5.6 The prompt store, and why erasure costs nothing

The prompt is the only place Mendel holds personal data, so it is stored on its own: a
`PromptRecord` keyed by ID and referenced from the `Goal`, never inlined. Retention is bounded
by default in every profile. `mendel forget <build-id>` deletes it.

GDPR erasure and audit retention normally pull against each other, and the usual resolution is a
compromise. The taint rule dissolves the conflict: because every downstream artifact derives
only from typed inputs, **deleting the prompt destroys nothing else**. The IR still resolves, the
decision records still explain, the lockfile still reproduces, the pipeline still runs. An
erasure request can be honoured in full with no loss of audit trail.

This fell out of the boundary rather than being designed for, which is usually a sign the
boundary is in the right place.

---

## 6. Clinical-grade artifacts

### 6.1 The lockfile pins what determines the result

Federation §4.1 defined a lockfile over contract digests, module versions, registry layers and
vocabulary version. That documents half of what decides an output. It gains:

- **container digests** (`@sha256:…`), not tags
- **reference data** — genome build, annotation version, any variant database, each with a digest
- the **profile** the build ran under, and the **actor**

Reference data belongs here because CLIA and ISO 15189 treat a reference database update as a
revalidation trigger exactly like a tool update. A silently updated GTF changes results.

`nf-core` already forbids `latest`, `dev` and `master` and requires pinned versions, and is
migrating toward immutable hosted container URIs — so the residual risk is narrower than mutable
tags in general: it is chiefly third-party deletion, which `nf-core` cites as its own reason for
mirroring. `sealed` refuses to build against a reference that cannot be resolved to a digest;
`open` and `guarded` accept tags and record what they resolved to.

### 6.2 Curation, constrained by §2

Federation §5.2 says a curated pipeline is signed off by a named human. Clinically that is not
sufficient, because distributing a pipeline to a laboratory is a transfer **between legal
entities** and therefore forfeits the Art. 5(5) in-house exemption for anything riding on it.

So: **curated means reference material the laboratory must validate. It never means a validated
test.** The curated stamp carries the curator's name and institution, the truth-set evidence
behind it, and the intended-purpose statement. It does not travel with any claim of clinical
fitness.

Supporting evidence is a truth-set run — **GIAB** for germline, **SEQC2** for somatic. This
closes federation §9's open question about reference datasets: `nf-core` test profiles are
indeed too small to demonstrate biological correctness, and the field's answer is standard truth
sets. Recall testing against real samples previously run on a validated method is named
explicitly as **the laboratory's responsibility, not ours**.

### 6.3 Intended purpose travels with the artifact

The statement in §2.2 appears in the README, in the dashboard, and as a header comment in every
emitted `.nf`, carrying the profile, the build ID and the validation requirement. The `.nf` is
what gets emailed, committed and pasted into a methods section with everything else stripped
away, so it must carry its own label.

---

## 7. New invariants

Numbered continuing from CLAUDE.md's existing thirteen.

> **14. Data leaves through four declared doors and no others.** Each carries one declared
> payload type, and exactly two fields in the whole surface may hold free text —
> `PromptRequest.prompt` and `GateFailure.tool_message`. Everything else is closed vocabulary.
> Enforced by `tests/test_egress.py`, which holds both lists literally.
>
> **15. Mendel does not receive patient data.** No input accepts a sample identifier, filename
> or path. Profiling happens where the data is and yields measurements only. The emitted
> pipeline references `params.input` as a placeholder the laboratory fills at run time.

Invariant 15 is currently true by accident. It is one plausible dashboard feature — "upload your
sample sheet" — away from being false, and it cannot be reclaimed once lost.

---

## 8. Testing

Mirrors the existing split; all of it runs offline.

| Test | Asserts |
|---|---|
| `tests/test_egress.py` | the payload allowlist is exactly four; only `PromptRequest` carries `FreeText` |
| `test_gate_failure_carries_no_paths` | a `GateFailure` built from stderr containing paths serialises without them |
| `test_profile_matrix` | each profile permits and forbids exactly what §5.1 says |
| `test_forget_preserves_replay` | after `mendel forget`, the IR still resolves and the pipeline still emits byte-identically |
| `test_sealed_requires_actor` | `sealed` refuses to run with an anonymous deployment |
| `test_sealed_requires_digests` | `sealed` refuses a reference that resolves only to a tag |
| `test_publish_bundle_is_typed` | no `FreeText` field can reach a `PublishBundle` |

---

## 9. Impact on the plans

**Plan 1** — three small additions, all cheap now and expensive later: the intended-purpose
header in emitted `.nf` (Task 11), a container reference field on `ModuleContract` (Tasks 3 and
10), and invariant 15 written into the goal model so it is a stated property rather than an
accident (Task 6).

**Plan 2** — the bulk. Payload types, the four doors, `GateFailure` parsing, profiles,
`EgressRecord`, the prompt store and `mendel forget`. `tests/test_egress.py` lands with the
first port implementation.

**Plan 2.5** — lockfile contents (§6.1), `PublishBundle`, curation evidence and the curated-tier
labelling (§6.2). Still not to be written until Plan 1 runs green.

**Plan 3** — the `guarded` confirmation screen, profile display, actor plumbing. And a standing
constraint: the dashboard must never accept a sample sheet.

---

## 10. Open questions

- **Who profiles the data?** §3.1 assumes a profiler running beside the FASTQs, but that
  component does not exist and is unassigned. It may belong to Wiener, to a small standalone
  tool, or to a Nextflow job Mendel emits. It is the one piece of this design with no owner.
- **Retention defaults.** "Bounded by default" needs a number per profile, and the number is a
  policy question a DPO should answer, not a developer.
- **Template goals for `sealed`.** Closing the prompt door means goals are typed or chosen from
  templates. The template library does not exist and is not designed.
- **Does the Porto laboratory recognise this?** Every workflow assumption here is inferred from
  published guidance rather than observed practice. The cheapest possible validation of this
  document is showing it to people who run the process daily.
