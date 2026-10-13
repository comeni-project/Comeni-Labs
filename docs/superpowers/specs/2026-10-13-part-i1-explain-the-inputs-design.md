# Explain the inputs (14.7.8.3d Part I.1) — design

**Status: written for review (2026-10-13).**
Each choice below was made by the operator in the brainstorm of 2026-10-13.

Scope: the first of Part I's three pieces ([293](https://github.com/comeni-project/Comeni-Labs/issues/293)):
[267](https://github.com/comeni-project/Comeni-Labs/issues/267) items 1–3, and the voice the rest
of Part I speaks in. I.2 (*say what was narrowed or already known*) and I.3 (*a conversation, not a
form*, with part 4's ask-anything folded in) get their own specs. Code baseline: `70b5d602`, after
Part H. No model is called by anything here.

## 1. What a researcher gets

Every question about their data says what the thing is, where people usually get it, and why this
analysis needs it, open beneath the question unless they turned that off. A file is called by its
name (*a gene annotation (GTF)*), not by an id (*annotation.gtf*). Where a sample can answer
questions, the question says which ones, before they choose, and the upload card reads like a
person wrote it.

## 2. Choices agreed with the operator

| Question | Choice |
|---|---|
| What "too mechanical" means | **All of it, in order**: the words (I.1, I.2), then turn-taking and the AI leading (I.3). |
| Where *what is this* comes from | **Curated text in the registry**, shown as written and marked *curated*. If it reads stiff on the walk, a model words it from the same text (I.3). |
| *What the pipeline does with it* | **Derived by the engine** for this analysis, marked *engine*; never curated. |
| The future | The curated text and the engine's facts are the **sources** I.3's AI is handed and speaks from (protocol rule 12), so each field is short, factual, one idea. |
| Open or collapsed | **Open by default; a setting** (*Explain each question*) collapses it. Each panel can still be folded by hand. |
| A type's name | **A curated `name:`**, used wherever a person reads the type. |
| How much in the registry | **The minimum**: optional `name` and `explain` on a type, optional `explain` on a measurement. No sub-fields, no lint rule, no extension override. |
| Upload copy | Plain, and says what a sample settles. **Nothing about bytes, megabytes or the AI read** on the card: on a self-hosted tool it reads as a warning and stops people uploading. The AI may say it in conversation (I.3). This replaces issue 135's decision for the card; Settings → Privacy still states it. |
| Tone | **Confident, slightly caring, professional, scientific**, written down once in `docs/design/voice.md`. |
| Dev mode's help text (268) | Already fixed in `0f231f0b`; its checkbox is ticked, nothing built here. |

## 3. The registry: two optional fields

```yaml
# registry/vocabulary/types/annotation.gtf.yml
name: gene annotation (GTF)
explain: >-
  A table of where each gene and its exons lie on the genome. It comes from the same source and
  release as your reference genome (Ensembl, GENCODE or UCSC), so that the two agree.
```

```yaml
# registry/vocabulary/measurements/read_length.yml
explain: >-
  How many bases each read holds. Your sequencing facility's run report states it, and so does
  the first line of sequence in any of your FASTQ files.
```

- A **type** gains `name` (one line, lower case unless a proper noun, the way it reads mid-sentence)
  and `explain` (one short paragraph: what it is, where it comes from). Both optional.
- A **measurement** gains `explain` only; its `description` is already its name.
- Missing fields fall back: the name to the id, a measurement's name to its description, and the
  panel to the engine's half alone (§4).
- **Written for the shipped registry:** all eight types' names; `explain` for every type gathering
  can ask for (the leaves: `fastq.reads`, `genome.fasta`, `annotation.gtf` today) and the three
  measurements it can ask (`read_length`, `paired`, `strandedness`). A repository test holds that
  every gap the shipped registry can produce has both; it is a test of our data, not a lint rule a
  lab's layer must pass.
- **No pin moves.** A lockfile pins each contract's digest, which these fields do not touch, and
  each layer's whole-directory digest, which every registry commit already changes (ordinary
  layer drift). Neither field reaches the resolver or the emitter: same goal → byte-identical
  `.nf` holds, and the existing determinism tests say so.
- These are registry commits on a `comeni-registry` branch, with the submodule pointer moved here,
  as Part 3c's inspectors were.

## 4. The engine: why each question is asked

Today a gap carries one string, `why`. It becomes structured, computed by the same walk
(`services/gaps.py`), deterministic, in a stable order:

| Gap | Carries | From |
|---|---|---|
| an input | `used_by`: each candidate contract on the walk that consumes it, with its tool's declared description, in walk order, deduplicated | `producers_of` over every candidate, as the walk already does |
| a measurement | `decides`: each rule whose `when` reads it, directly or through a derivation, as its `because` and `cite` | `_premise_measurements`, extended to say *which* decision reads each |
| a measurement read through a `meta_key` | `used_by`: the consumers of the type it `describes` | the leaf it describes |

Rendered beneath the question (*Why it's needed*, marked *engine*):

- *Read by STAR_ALIGN or HISAT2_ALIGN (whichever is chosen), then FEATURECOUNTS.* Each step name
  carries its tool's one-line description on hover; a tool without one shows its name alone.
- *Decides the aligner: read length determines which aligner is appropriate (Dobin et al. 2013).*

**What a sample settles.** For an input gap whose type an inspector reads, the question also
carries `settles`: the measurements the inspectors for that type declare **and** that are still
open gaps, by their names. That is the list the upload headline names, and only those: a
measurement already answered is not promised. A type no inspector reads carries none. A new
inspector changes the list with no copy edit.

**The question's own words** use the name: *This analysis needs a gene annotation (GTF). Do you
have one?* `builder.ask.v1` receives that sentence as `{{gap}}`, unchanged in shape; no prompt
version changes.

## 5. The card

Under the question, before its answers:

```
What is this?                                          curated
  A table of where each gene and its exons lie on the genome. It
  comes from the same source and release as your reference genome
  (Ensembl, GENCODE or UCSC), so that the two agree.
Why it's needed                                        engine
  Read by STAR_ALIGN or HISAT2_ALIGN (whichever is chosen), then
  FEATURECOUNTS.
```

- Open or collapsed per **`building.explain`** (*Explain each question*: *Open* · *Collapsed*,
  default *Open*), in Settings → Building beside Pacing. The disclosure is per question and is
  component state; the setting only picks how it starts.
- A half with nothing to say is not drawn; with neither, no panel.
- The marks are the consultant build's minimal source marks (*curated*, *engine*), the same words
  part 4 will put on every message.

**The upload, when the type is inspected and `settles` is non-empty:**

> **Have a sample to hand? Upload it and we'll measure the rest:** your read length, and whether
> your reads are paired. You won't need to answer those yourself.

**When no inspector reads the type** (the AI will read it):

> **Have a sample to hand? Upload it and the AI will read it for you.** It shows you what it found,
> and nothing is used until you've confirmed it.

**On the upload card**, replacing *one file, or a pair (R1 and R2) · only the first 4 MB is read…*:

> Choose one file, or both files if your reads are paired. Paired files are usually named `_R1`
> and `_R2`, or `_1` and `_2`.

The option labels keep their ids and get the voice: *I have it, and I'll upload a sample* →
*Yes — I'll upload a sample*; *Not sure: upload a sample and I'll measure it* → *Not sure —
measure it from a sample*.

## 6. The voice page

`docs/design/voice.md`, about a page:

- the four words, and what each rules out (confident: no *might*, *perhaps*, *please note*;
  caring: says what the person gets and what happens next; professional: no exclamation marks,
  no jokes; scientific: the term, then what it means, never the term alone);
- do / don't pairs taken from this brainstorm (the R1/R2 line; *annotation.gtf* → *a gene
  annotation (GTF)*; the upload headline);
- **say what the person gets, not how the machine works**: mechanics a person did not ask about
  stay out of the copy;
- written so I.3 can quote its body into a prompt verbatim: no links, no tables inside the quoted
  part.

Every string this spec adds follows it, and the curated `explain` entries are written to it.

## 7. When it goes wrong

| Case | What happens |
|---|---|
| a type or measurement with no `name` / `explain` | the fallbacks of §3; nothing refuses |
| a consumer contract whose tool has no description | its step name alone |
| a rule with no `cite` | its `because` alone |
| `settles` empty for an inspected type (everything already answered) | the generic headline: *Upload it and we'll measure it* |
| the setting unreadable | *Open*, the default |

## 8. Testing

- **The shipped registry's coverage** (§3): every gap the shipped registry can produce has its
  name and explanation. Asserts the gap list is non-empty first.
- **Gap context:** `used_by`, `decides` and `settles` for scenario 1's want, with read length known
  and unknown; same inputs → same lists in the same order.
- **The question's words** carry the name, and fall back to the id.
- **The card** (Vitest): both halves and their marks; open and collapsed by the setting; a half
  missing; the upload headlines per case; no *MB*, *KB* or *8 KB* in any card copy.
- **The setting** in the catalogue test, and on the Settings page.
- **The walk:** scenario 1 with no model, on a throwaway database, looked at in the browser;
  compared against the voice page.

## 9. Not here

The model wording any of this (I.3); what was narrowed or already known (I.2); asking anything
(I.3); revisiting `TypeExtension` to focus on the tool (operator: later); explanations for steps
or settings (the step card already carries its four things).
