# Forge review queue — visual design

**Date:** 2026-08-02
**Status:** Approved first pass. Tuning deferred to implementation.
**Mockup:** [`forge-review.html`](forge-review.html) — self-contained, open in a browser.

Design for the curator-facing screens of the forge's review queue. Shares the token system in
[the dashboard design](dashboard.md); only the additions are recorded here.

**The plan this was drawn against no longer exists.** It cited Plan 2 Tasks 8–10, and Plan 2 was
deleted on 2026-08-16 rather than corrected — [`the forge
spec`](../../notes/specs/2026-08-16-the-forge.md) replaces it. The screens survive the plan: the
forge still has a workspace of drafts a curator reviews, and §6 of that spec puts this behind the
same HTTP layer the CLI renders from. What changed underneath is that a draft now carries **typed
holes** rather than a wholly AI-drafted contract, so a review screen has a field-by-field list to
render with the evidence and the legal candidates for each — which is more than these mockups
assume, not less.

---

## 1. Different user, different tool

The builder serves a biologist who cannot code. The forge serves a **curator** deciding
whether an AI-drafted contract is correct. That is a code-review job — denser, text-led,
evidence-first. It shares Mendel's palette and type so the two read as one product, but it
does not share its canvas idiom.

**The tool reviews code, not just the drafted YAML.** A contract that looks reasonable in
isolation can still be contradicted by the module's own source, and that is the failure mode
the screen exists to catch.

---

## 2. The curator's workflow

Eight steps, in the order a curator actually performs them. Stages that can be checked
mechanically clear themselves and collapse; the three that need judgement stay open.

| # | Stage | Who clears it | What it answers |
|---|---|---|---|
| 1 | Where it came from | auto for nf-core | Is the source curated, pinned, tested? |
| 2 | **The code** | **human** | Is the container pinned? Is there a stub? Does the script do anything alarming? |
| 3 | **Does the code support the contract?** | **human** | The crux — is every inferred claim justified by a line of source? |
| 4 | Vocabulary | auto | Are all states declared, or is a new one needed? |
| 5 | **What approving this changes** | **human** | Does it create routing ties or shadow an existing module? |
| 6 | Tests | auto | Does it stub-run? Did nf-test pass? |
| 7 | Decide | human | Approve · request change · reject with reason |
| 8 | Stamp | auto | Who, when, against which source commit |

Numbered markers are used here and nowhere else in the product, because a review genuinely
**is** a sequence — the numbering carries information rather than decorating.

---

## 3. Signature: copied vs inferred

The forge exists because `meta.yml` declares `type: file` and a contract must declare
`alignment.bam [coordinate_sorted]`. So the screen's whole job is isolating **what the model
added beyond the evidence**.

Every contract field carries its origin as a left stripe, reusing the dashboard's language:

| Origin | Stripe | Meaning |
|---|---|---|
| `copied` | neutral | literally present in the source — zero risk |
| `inferred` | `--pea` solid | the model's addition, justified by a cited line |
| `unsure` | `--undecided` gapped | the model's addition, contradicted or unsupported |
| `invalid` | `--fault` solid | uses a state not in the vocabulary — blocks approval |

**Claims bind to code lines.** Every inferred field links to the exact line that justifies
it; clicking opens the code stage and highlights that line. An unjustifiable inference has
nowhere to hide.

The queue shows the same encoding as a proportion bar per row, which makes scrutiny cost
legible before you open anything: `nf-core/fastqc` is mostly copied and batch-approvable, while a contract drafted from
prose documentation is largely inferred and needs a careful read.

---

## 4. Stage 5 — routing consequences

The check no per-file review can perform, and the highest-value screen in the tool.

Approving a module that produces `alignment.bam [coordinate_sorted]` when another already
does, at equal priority, creates a **tie**. The router demotes ties to tier 4, so every
future pipeline needing a sorted BAM would flag a decision at the user instead of resolving
silently. One approval degrades every subsequent build.

The stage names the conflict, quantifies the blast radius, and offers the two real fixes
(raise this module's priority, or narrow the other's produced state).

---

## 5. Queue

- Sorted by **what needs you, not by date**. Blocked first, then attention, then clear.
- Filter by proposal kind: contracts, states, rules.
- **Batch approval is offered only** for proposals that cleared every automatic check *and*
  mostly copy from a pinned source. Anything with meaningful inference is opened individually.

## 6. Rejection is training data

The reject box asks for a reason, and the copy says why: the text returns to the forge as
drafting guidance. The intent is that the model improves rather than merely being overruled.

## 7. Vocabulary page

Types with their closed state lists and usage counts. Proposed states render dashed and
`--pea`; contracts referencing an unapproved state stay queued until it lands. Types with no
states say so explicitly — *"no states — this type is either present or absent"* — rather
than showing an ambiguous blank.

---

## 8. Known gaps

- **`copied` is currently an assertion, not a verification.** §3 calls a copied field "zero
  risk", which is only true if something compared it to the source. That something is
  conformance checking — see [conformance.md](conformance.md), Plan 1.6 — and until it
  exists the proportion bar measures the drafter's confidence rather than evidence. The
  origin taxonomy in §3 is right; it just needs a checker underneath it.

- **`Provenance` is per-contract and needs to be per-field.** §3 requires every field to
  carry its origin as a stripe and bind to the line that justifies it. The model does not
  support that: `Provenance` has `source`, `drafted_by`, `approved_by`, `approved_at` for
  the whole contract, so a contract that is 90% copied is indistinguishable from one that
  was entirely guessed. The screen cannot be built before the data model changes.

- **A drafted contract should have to *run* before a human sees it.** §5 gates batch
  approval on "cleared every automatic check" without saying what those are. One is missing
  and is worth naming: synthesise a minimal goal from the draft (`have` = its inputs,
  `want` = its outputs), resolve, emit, and put it through `preview` and `stub`. A binding
  that cannot execute is not a review problem, and the machinery already exists. Stage 4's
  routing-consequence check is the other one, and it is designed.

- **Ingesting prose documentation needs its own layout.** Where a source documents a tool
  in a `README.md` rather than a structured schema — the `pegi3s` repository, most
  in-house tools — the evidence panel would be showing English rather than declarations,
  and more fields are inferred than copied. The nf-core layout does not fit that case, and
  the review it calls for is a different kind of reading.
- **Tier-3 rule proposals are designed for but not drafted.** The queue's `kind` filter
  includes rules; no drafter emits them yet (see Plan 2 self-review).
- **Pipeline review is a separate screen set, not yet designed.** The
  [federation spec](federation.md) adds
  `kind: pipeline` to the queue, but it asks a different question — *is this a defensible way
  to do this analysis?* rather than *does the source support this claim?* — so it needs its
  own stages and its own evidence panel. Plan 1.7.
- **Keyboard shortcuts are advertised, partly wired.** Only `.` (next stage) works in the
  mockup; J/K/A/R are shown in the hints but not implemented.
- **No diff view for re-drafts.** When a rejected proposal is redrafted, a curator will want
  to see what changed since their last review rather than re-reading it whole.
