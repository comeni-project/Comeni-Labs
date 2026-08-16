# Federation, provider access, and curation

**Date:** 2026-08-02
**Status:** Approved.
**Extends:** [`mendel.md`](mendel.md). Read that first.
**Amended by:** [`clinical-data-protection.md`](clinical-data-protection.md)
— which constrains §4 publication to typed bundles, §5 curation to reference material a
laboratory validates, and answers §9's open question on reference datasets.

An addendum, not a replacement. It answers four questions the original spec left open: how
Mendel reaches a model, how a lab keeps private modules without forking, how a working
pipeline becomes something someone else can start from, and what licence any of this carries.

---

## 1. The decisions

| Question | Decision |
|---|---|
| Model access | BYO API key or local model. No subscription OAuth. |
| Registry | Public curated base, private overlays stack on top |
| Overlay collision | Same ID shadows and is recorded; different ID obeys tie rules |
| Pipelines | Publishable artifacts with a lockfile; private / published / curated |
| Curated stamp | A **named human** signs off. Never mechanical. |
| Code licence | Apache-2.0 |
| Data licence | CC-BY-4.0 |
| Revenue | Hosted service only. The tool is fully self-hostable. |

The through-line: **everything that makes Mendel trustworthy is public and offline-capable.**
The hosted instance sells convenience, never capability.

---

## 2. Provider access

### 2.1 Three lanes

| Lane | Auth | For |
|---|---|---|
| `--no-ai` | none | CI, air-gapped labs, reproducibility proofs |
| self-hosted | API key, or a local model over an OpenAI-compatible endpoint | institutes with data they cannot ship |
| Comeni-hosted | our keys | researchers who do not want to run infrastructure |

`mendel-ai` implements the `mendel_resolver.ports` protocols with a LiteLLM adapter. LiteLLM
remains the choice: open source, self-hostable, ~100 providers, no markup. Because the port
is a `Protocol`, replacing it later touches one package.

A local model reaches the same adapter — Ollama and vLLM both expose OpenAI-compatible
endpoints, so "self-hosted with no external network" is a base URL, not a code path.

### 2.2 No subscription OAuth

Attaching a Claude Pro/Max account to Mendel is **prohibited**. Anthropic's documentation,
updated 19 February 2026, states that using OAuth tokens obtained through Claude Free, Pro or
Max accounts in any other product, tool or service — the Agent SDK included — violates the
Consumer Terms of Service. Enforcement began in January 2026; `opencode` removed its
Pro/Max support citing legal requests.

OpenAI currently permits Codex subscriptions in third-party harnesses. We do not build on
that asymmetry: a provider-specific privilege that one vendor grants and another revokes is
not a foundation, and a feature that works for one model and is bannable for another is worse
than no feature.

There is no open-source library that solves this, because it is not a technical problem.
Every gateway in the category — LiteLLM, Portkey, Bifrost, OpenRouter, LLM Gateway — routes
**keys**. None routes subscriptions, for the same reason.

**Escape hatch, unsupported.** A user may point self-hosted Mendel at an agent CLI already
installed and authenticated on their own machine. That is the user running their own tool
locally, not us reselling their token. It ships disabled, documented as unsupported, and is
absent from the hosted instance.

### 2.3 Telemetry

**Opt-in, off by default, and never on without an explicit act by the operator.** A
self-hosted instance that has not been configured sends nothing.

Invariant 1 already enforces the boundary structurally: `comeni-core`, `mendel-resolver` and
`mendel-compiler` may not import an HTTP client, so telemetry cannot physically exist in the
packages that do the resolving. It can only live in `mendel-api`, where an operator reviewing
the deployment will find it in one place. This is a property of the architecture rather than a
promise in a privacy policy, and the AST test in `tests/test_purity.py` fails if it erodes.

Institutes running Mendel on patient or unpublished data will read the source before
deploying. What they find must match what we say.

### 2.4 Why this is cheaper for us than for anyone else

Mendel's runtime AI surface is three declared points (spec §4.2). Tiers 1–3 resolve with no
model at all. A self-hosted Mendel with no provider configured still ingests a goal, routes
it, resolves it and emits Nextflow — tier 4 flags instead of guessing, which is behaviour the
product already promises.

So **self-hosted Mendel is not a degraded tier.** Same registry, same resolver, byte-identical
output. This should be stated plainly in the README, because it is the opposite of how every
comparable tool works.

---

## 3. Registry federation

### 3.1 The stack

The registry loads as an ordered stack: the public curated base, then zero or more private
overlays, supplied by repeated `--registry` or by config. Later layers win.

```
--registry <comeni-registry checkout>       # public base, implicit default
--registry ./lab-contracts                  # the institute's own
--registry ./my-contracts                   # personal
```

An overlay is a directory of the same data files. There is no second format and no separate
API. A lab that never publishes anything is the normal case, not an exception.

### 3.2 Collision

A contract ID is `namespace/name@version`. Its **module key** is the ID minus the version:
`nf-core/samtools/sort@1.21.0` has module key `nf-core/samtools/sort`. Collision is decided on
the module key, not the full ID, and only *between* layers:

**Same module key in a higher layer → shadow.** Every contract for that module key in all
lower layers is removed, and a `ShadowRecord` is written naming the module key, the layer that
won, and the layers it displaced. This is a *declaration*: whoever assembled that overlay
stated an intent to override.

**Different module key → ordinary candidate.** It competes under the existing `(-priority, id)`
ordering, and if it ties, invariant 8 applies — demote to tier 4. A private module that
happens to produce the same state as a public one is genuine ambiguity, and the resolver must
keep saying so.

**Within a single layer, nothing changes.** A layer may legitimately offer two versions of the
same module; they remain separate candidates under the existing tie rules.

Keying on the module key rather than the full ID is what makes both real cases work. A lab
correcting nf-core's contract for a module ships the same ID; a lab pinning a newer build
ships `@1.22.0`. Under full-ID matching the second would tie against `@1.21.0` and demote
every downstream build to tier 4 — a version bump is not ambiguity.

Without the shadow rule, every deliberate override degrades subsequent builds. Without the
different-key rule, installing an overlay would silently reroute pipelines based on what
happens to be on disk — the exact failure the product exists to eliminate.

### 3.3 Shadowing is visible

`PipelineIR` gains `registry_layers: list[RegistryLayer]`, each carrying the layer's source and
resolved version, and `shadowed: list[ShadowRecord]`. A build performed on a modified registry
says so, so a reviewer at another institution can tell it was not stock without having to ask.

### 3.4 Distribution

The public registry is **its own repository** — `comeni-registry`, holding every kind of
declared data with signed tags. Pulling is `git pull`. Verification is tag
signature plus a content digest recorded in the lockfile. No sync protocol is invented.

It is separate from the code repository for three reasons: pulling the registry should not
mean cloning a Python workspace; the two carry different licences (Apache-2.0 against
CC-BY-4.0), and one repository with two licences invites exactly the confusion the licence
files exist to prevent; and a lab forking the registry to build an overlay should not fork the
compiler.

**The split happens at Plan 1.7, not now.** Through Plan 1 the repository keeps a handful of
hand-written contracts under `examples/` purely as test fixtures, because the tests need data
before a registry exists. `Registry.load()` takes paths, so relocating them later is a change
to configuration rather than to code — but only because the split is decided in advance.

Contributing back is a proposal into the forge queue already designed in
[the forge review design](forge-review.md): a lab approves a
contract locally, then opens it upstream, where it meets the same curator screens.

---

## 4. Pipelines as artifacts

### 4.1 A pipeline is already publishable

No new format is required. A shareable pipeline is:

| Part | Already exists | Answers |
|---|---|---|
| `Goal` | spec §5 | what a human asked for |
| `PipelineIR` | spec §5.3 | what it resolved to |
| `DecisionRecord[]` | spec §5.4 | why each choice was made |
| **lockfile** | new | against exactly which contracts and modules |

The lockfile pins contract IDs with content digests, module versions, registry layer sources
and the vocabulary version. Loading a locked pipeline reproduces byte-identical Nextflow.

### 4.2 Visibility

| Tier | Meaning | Gate |
|---|---|---|
| private | in your overlay, never leaves | none |
| published | in the public catalogue | mechanical: stub-run green, then `-profile test` green |
| curated | "this works for X, start here" | **a named human signs off** |

Publishing a pipeline and publishing a contract are separate acts. A lab may publish neither,
either, or both.

### 4.3 Editing a curated pipeline is the point

Invariant 9 already says decision records are replayed on rerun rather than re-asking a model.
Applied to a downloaded pipeline, that yields the property that makes curation worth doing:

> Load a curated Goal, change one thing, and every untouched decision replays from its record.
> Only what you touched can move.

This is why "good starting point you can edit" is a real claim here and a slogan elsewhere.
Editing a Galaxy workflow gives you a graph you must re-audit. Editing a Mendel pipeline gives
you a diff.

`mendel upgrade` re-resolves a locked pipeline against the current registry and reports what
moved, at which tier, and why. Nothing upgrades implicitly.

---

## 5. Curation

### 5.1 Two different questions

The forge queue gains `kind: pipeline`, but it does not reuse the contract screens, because
it is not asking the same thing.

| Review | Asks | Evidence |
|---|---|---|
| contract | does the module's source support this claim? | source lines, cited per inferred field |
| pipeline | is this a defensible way to do this analysis? | a run, its inputs, its outputs, the literature |

A bad contract makes one module wrong. A bad curated pipeline makes someone's paper wrong,
with our name on the shelf it came from. The bar differs accordingly.

### 5.2 The curated stamp

Curation is **human**. A pipeline earns the stamp when a named person with relevant expertise
signs off, and the stamp carries **their** name and a citation, not only ours. Supporting
evidence — typically a reference-dataset run matching expected outputs within tolerance — is
material the curator reviews, not a tier that can clear itself.

A mechanical stamp was considered and rejected. It would scale, and it would mean "the DAG
executed", which is not what a researcher reads the word *curated* to mean.

### 5.3 Provenance survives publication

A curated pipeline still carries its tier-4 flags. Curation asserts that the decisions were
reviewed and found defensible; it never rewrites a tier-4 decision into a tier-2 one. A
researcher downloading a curated pipeline still sees where the judgement calls were, and who
made them.

---

## 6. Licensing

**Code: Apache-2.0.** Bioinformatics norms are permissive — nf-core is MIT — and university
legal review treats AGPL as a procurement question, which would cost adoption in precisely
the market this tool is for. Apache-2.0 over MIT for the explicit patent grant, which
institutional users care about and individuals do not notice.

AGPL was considered. It would protect the hosted business from a third party running
Mendel-as-a-service. For a research tool that risk is small, the adoption cost is not, and
the moat is the curated registry rather than the code.

**Registry data: CC-BY-4.0**, applying to `contracts/`, `rules/`, `vocabularies/` and
published pipelines. Contracts and tier-3 rules cite papers; attribution is the currency of
the field. CC0 would discard it.

**Vendored nf-core modules** under `modules/` retain their own licences and notices.

---

## 7. What this deliberately is not

**There is no vector memory store.** The question that prompted this design was framed as
"how does a self-hosted instance get memory from past work", implying Mem0, Zep or Letta.
Mendel does not want one.

Chat memory answers *what did this user say before*. Mendel's institutional memory is
`contracts/`, `rules/`, `vocabularies/` and `DecisionRecord`s — versioned, human-approved,
diffable, citable. That is already the better kind. Adding a fuzzy recall layer beside it
would create a second memory that no one approved and that could influence resolution without
passing the forge, contradicting invariant 2 and reintroducing exactly the silent-guessing
failure the product exists to remove.

Federation is therefore a **registry distribution** problem, not a memory problem, and it is
solved by git plus a lockfile.

---

## 8. Impact on the existing plans

**Plan 1 changes.** `Registry` is built there, and stacked loading is roughly one extra task
now against surgery on a core type later. Task 5 becomes `Registry.load(layers, vocab)` with
shadowing; the single-directory form remains as the one-layer case.

**Plan 2 unchanged.** `Proposal.kind` is already a free string, so `kind: pipeline` needs no
code there. Drafting and the pipeline review screens are Plan 1.7's work.

**New Plan 1.7 — publication and curation.** Lockfiles, `mendel publish`, `mendel upgrade`,
the pipeline catalogue and the pipeline review screens. Also the registry split: moving
`contracts/`, `rules/` and `vocabularies/` out of `examples/` and into the `comeni-registry`
repository, with signed tags. It depends on the IR and decision records, so it lands after
Plan 1 and alongside or after Plan 2.

**Plan 3 unchanged.** The dashboard renders `registry_layers` and shadow markers, but that is
display of data the IR already carries.

---

## 9. Open questions

- **Curator recruitment.** The design assumes named experts willing to sign off. Finding them
  is a real dependency and is not a software problem.
- **Reference datasets.** Curation-supporting evidence needs a reference dataset per analysis
  type. nf-core test profiles are too small to demonstrate biological correctness.
- **Overlay conflict across two private layers.** Two overlays shadowing the same public
  contract resolves by stack order, which is correct but silent within the private stack. If
  labs routinely run more than two layers this may want its own warning.
- **Registry hosting — resolved enough to act on.** The registry is the `comeni-registry`
  repository under `github.com/comeni-project`, and needs no hostname at all: §3.4 already argues
  that pulling is `git pull` and verification is a signed tag plus a content digest. The earlier
  `registry.comeni.org` placeholder is **dead** — `comeni.org` was checked on 2026-08-03 and is
  registered to someone else. If a vanity host is ever wanted it hangs off whatever umbrella
  domain is bought; nothing depends on one existing.
- **GitHub namespace — resolved.** The organisation is `comeni-project`, chosen because the org
  must be the umbrella over `comeni-labs`, `comeni-code` and `comeni-registry` rather than one of
  them. `Comeni-Labs` was transferred to it on 2026-08-03.
