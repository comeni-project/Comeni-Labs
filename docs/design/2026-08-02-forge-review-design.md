# Forge review queue — visual design

**Date:** 2026-08-02
**Status:** Approved first pass. Tuning deferred to implementation.
**Mockup:** [`forge-review.html`](forge-review.html) — self-contained, open in a browser.

Design for the curator-facing screens described in
[Plan 2](../superpowers/plans/2026-08-02-mendel-ai-and-forge.md), Tasks 8–10. Shares the
token system in [the dashboard design](2026-08-02-mendel-dashboard-design.md); only the
additions are recorded here.

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
legible before you open anything: `nf-core/fastqc` is mostly copied and batch-approvable,
`pegi3s/blast` is 12% copied and needs a careful read.

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

- **pegi3s ingestion needs its own layout.** Its sources are a `Dockerfile` and prose
  `README.md`, so nearly every field is inferred and the evidence panel would be showing
  English rather than declarations. The nf-core layout does not fit that case well.
- **Tier-3 rule proposals are designed for but not drafted.** The queue's `kind` filter
  includes rules; no drafter emits them yet (see Plan 2 self-review).
- **Keyboard shortcuts are advertised, partly wired.** Only `.` (next stage) works in the
  mockup; J/K/A/R are shown in the hints but not implemented.
- **No diff view for re-drafts.** When a rejected proposal is redrafted, a curator will want
  to see what changed since their last review rather than re-reading it whole.
