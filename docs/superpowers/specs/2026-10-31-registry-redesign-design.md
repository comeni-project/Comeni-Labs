# Registry redesign: from the approved canvas to the app

**Issues:** #420, #423, #424, #425, #426, #427, #429, #430. #428 and #431 stay last, with the
operator. **Status:** written for review (2026-10-31). **Parent:** the live walk, #412.
**Canvas:** *Forge redesign* (claude.ai artifact `Nm16yNgWqJUsqHUQmsuiVL`), 16 boards. The operator
approved 13 of them; Phone, Chat states and Before the first sync came after and await a look.

*(operator)* marks a choice made in chat; *(spec)* marks this document's own call. On 2026-10-31 the
operator settled D1 to D3 by asking for the best long-term option in each.

## Why

The live walk reached step 4 of 8 and rated the registry pages unusable for a person: no
feedback, no context for a question, raw JSON, a chat that hides what the AI does. The canvas is the
agreed answer. This spec says what must change in the app to match it, in what order, and what
needs a decision first.

## Goals

1. **One page frame and one set of parts:** logo, tabs, tracker and panels share their edges;
   side-by-side panels end level; actions sit at the panel's foot *(operator)*.
2. **The tool is drawn, not described:** a block with input and output pins on every forge page,
   filling in as a person decides *(spec, approved on the canvas)*.
3. **A catalogue that scales to the real data:** format flow, typed search and filters over all
   2,125 modules and 778 formats *(operator)*.
4. **Choosing from what exists:** a searchable picker wherever a person names a type, job or tool
   *(operator)*.
5. **Nothing the AI does is hidden:** live steps, tokens and an honest outcome in one chat
   *(operator)*.
6. **Each question brings its context and a reviewer's comment** *(operator: the MVP needs it, #426)*.
7. **Forged items are built with constructors, never raw JSON** *(operator)*.

## Non-goals

- Changing how Build or Runs look.
- Fixing #428 and #431; they are the operator's, and last.
- Resuming the walk; that follows this work, at step 4.
- Light-theme boards. The app's tokens already carry both themes, and each slice checks both.

## What the code already has

| Need | Existing | Use |
|---|---|---|
| Composer, waiting line, *What is this?* | `frontend/src/build/living/` (`Composer`, `Waiting`, `blocks/Explain`) | Reuse in the forge chat. |
| Picker | `frontend/src/build/Picker.tsx` ranks what fits a port on the server | Keep its rule: no type logic in the browser, the server orders the list. The forge picker is a new part, because it lists the registry rather than what fits a port. |
| Port shape | `frontend/src/build/Port.tsx` draws ports on the graph | Not reused: forge pins carry text and state. |
| Type details | `GET /registry/types/{id}` gives states and using contracts | Extend, and add a listing. |
| Token columns | `ai_invocation` holds them; `_record` in `forging_ai.py` leaves them empty (#420) | Fill them. |
| Filters in the address | `useFilters` in `useCatalogue.ts` | Keep; add `reads`, `makes`, `suite`. |

`docs/design/voice.md`, which #426 cites, no longer exists at that path. The voice rules are to be
found before slice 3 writes any question copy.

## Decisions

### D1. What to call a generic output *(operator: best long term)*

Raised by the operator: `tsv` and `json` say nothing about what a file holds. There are three
separate problems, and `tsv::quast` touches only the last.

- **The port's name is not ours.** `against` in `mendel_compiler/conformance.py` refuses a port not
  named after a channel the module emits, so `tsv` must stay in the contract while nf-core calls it
  that.
- **The catalogue's formats** are file extensions from nf-core's patterns. Its rows already name the
  module, so `tsv::quast` would add nothing there.
- **The type** is what can carry the meaning. Matching is exact: `port.type_id == type_id and states
  <= port.state` (`router.py`, `declared/registry.py`), with no hierarchy.

| Option | Example | Cost | Effect |
|---|---|---|---|
| **A. A state, decided** | `qc.report[assembly]` | Declare the state on the type. No engine change. | `multiqc`, which wants `qc.report`, still reads it. A step needing this table can require the state. |
| B. A new specific type | `qc.assembly_metrics` | None: `genome.index.star` already works this way. | Nothing general reads it, so `multiqc` loses quast's report unless its contract changes. |
| C. A real hierarchy | `tsv::quast` | Every exact comparison in the router, registry and validation changes, plus the type grammar. A protocol change. | Most expressive, and names a tool inside a type, so swapping the tool breaks the pipeline's wiring. |

**Decided:** A for an output a general reader should accept, B only where the file really belongs
to one tool, as an index does. C is declined: states already mean *this, and more specific*, so a
hierarchy would be a second matching rule doing the same job. Name what the file holds, not the tool.

Tested on 2026-10-31 on a scratch copy of the registry, through its real validation, resolving real
goals. The rnaseq pipeline came out the same in every scenario, and `qc.report[assembly]` and
`qc.report[reads]` each found exactly their tool. An undeclared state is refused (`MD0009`), so a new
one is a reviewed vocabulary change. Once `fastqc` carries a state too, nothing is plainer than
anything else, so a plain `qc.report` request ties and becomes a flagged tier-4 question instead of
choosing silently. That is the intended behaviour, and a hierarchy would tie the same way.

**Exposed by that test:** `multiqc`'s `*` input is fed by one chosen producer, so fastqc and quast
cannot both reach it. It is a limit of fan-in, independent of this decision, and gets its own issue.

**How it reads** *(operator)*: `::` is the one notation, on the page and in the files:
`type_id: qc.report::assembly` and `alignment.bam::coordinate_sorted`, replacing the `state` fields
and `[...]` signatures. With nothing to keep compatible this is a mechanical change: the parser splits
it into the same type and states, so matching is untouched. A type may hold several, written
`::assembly::aggregated`, sorted.

**The file type stays explicit** *(operator)*: `OutputPort` gains an optional `format` (`tsv`), which
the forge fills from the module's emit pattern and conformance checks against `main.nf`. A pattern
may give several (`bai`, `csi`, `crai`) or a folder (`hisat2`), so it is a list. It is shown
beside the type, `qc.report::assembly · tsv`, and takes no part in matching, so two tools making the
same content in different layouts stay interchangeable unless a reader says otherwise. Pins lead with
the human name, with the emit name and format small beneath it.

**Costs:** a new `format` field, checked by conformance, and one state declared on the type per new
kind of content. A type's states are one flat list, so a state cannot have children of its own.

### D2. Reviewer AI *(operator: best long term)*

A new declared AI point: a prompt, an `InvocationPurpose` and a typed reply.

| Option | Cost on a local model | Effect |
|---|---|---|
| **One call per piece, decided** | One extra call per drafted piece | Returns a comment for every item, so each question still has its own, and can see conflicts between items. |
| One call per question | One call for each item; about 5 on quast's questions | Simplest prompt, slowest by far. |

**Fixed either way** *(spec)*: the comment is advice, stored and shown as a model's, and it changes
nothing. A quote is shown only if the engine finds it verbatim in the named file; otherwise the
quote is dropped and the comment stays. Which model reviews is a Settings purpose, off when unset,
and a piece works without it. A reviewer may use a different model from the drafter.

### D3. Live progress *(operator: best long term)*

| Option | Cost | Effect |
|---|---|---|
| Polled steps | Least | Works, but the record of what happened stays scattered across messages and jobs. |
| **Stored events, pushed, decided** | A table and a stream route, following Runs' `useRunStream` | Each step, attempt, refusal and call total is an ordered, durable event. The page follows them live, and reloading replays them. |
| Streaming tokens from the model | Streaming through `comeni-ai`, which has none today | A count that moves during a call. |

**Decided:** stored events, pushed to the page, with polling as the fallback when the stream drops.
The chat draws from those events, so progress and history are one record, and the shape is kept
free of forge-only fields so the builder can adopt it. Token streaming from the model is left out:
a reply can only be checked once it is complete, so it would show motion and not results. It can
later add an event kind without changing this design. Per-call token totals are recorded either way.

### D4. Format data *(spec)*

- **Aliases:** a table beside `TOPICS` in `mendel_forge/topics.py` folds `fa`, `fna` and `fq` into
  their format, ours to adjust, as topics are. Stored names stay as nf-core wrote them.
- **Mentions:** a format named only in a channel's description is stored apart from declared ones
  and never counted as declared, so the forge's rule against guessing holds. The page offers these
  as a separate widening. EDAM tags cannot fill this gap: FastQC and quast have none.
- **Suites** are derived from the path's first segment, so they cover every module, including the
  977 with no topic.

### D5. Order *(spec)*

Merge #433 and `forge-walk-fixes` first, then the slices below. Each is its own branch and plan.

## Slices

Sizes are relative. Estimates on this project have run long, so each plan states its own and stops
at twice that.

### 1. Shared parts (S)

Page frame; `PiecesTracker`; `ToolDiagram` with pin states; shared control states (#424);
`RegistryPicker`. The background and word-break findings of #429.

### 1b. `::` and `format` (S)

The notation of D1 in the parser, contracts and signatures, and the checked `format` field. Before
the catalogue and pieces show them. Multi-input routing is out of scope and tracked in #435.

### 2. Catalogue (L)

- **API:** split `formats` into `formats_in` and `formats_out` columns, with a migration and a
  re-sync; add `mentions`. `read_page` takes `reads`, `makes`, `suite` and `no_topic`. Counts follow
  the filters, each facet leaving out its own pick, where `_counts` today is over everything.
- **New read:** the top format pairs under the current filters, for the ribbons.
- **Page:** search with chips and grouped suggestions, format flow, Your registry diagram from the
  contracts, list and preview. All counts come from the server; 2,125 rows do not go to the browser
  as the prototype's did.

### 3. Chat and progress (M): #420, #423, #425, #430

Record tokens. One message shape with sender and time; `MessageView` gains a kind and an outcome.
Progress arrives as the stored events of D3. Failures collapse once resolved. Every AI reply states what it changed, including nothing, from the
commands it actually sent. Resizable, pinned column, and a sheet at 390 wide.

### 4. Question context and reviewer (L): #426

Each question carries the module's line, the registry's words about the type or role, its scope,
the tools using it, and what the answer decides, drawn from declared data and the module's files
rather than from the model. Then the reviewer, per D2, and questions that ask what an output holds, per D1.

### 5. Constructors and pickers (M): #427

*Write an item yourself* and *Change* become forms per piece, building the key and value, with
inline refusals. Settings get a kind, a default and a live preview. No JSON box remains.

### 6. Piece pages and the rest (L): #429

Contract, Parameters, Vocabulary, Rules (with the read-length slider running the real rule through
the server), Tests, Assembly, Pull request, Releases, the Forging board and the Tool page.

## Testing

- Pure format and alias logic gets deterministic unit tests; model calls use recorded replies.
- A guard must fail against the defect it names: the reviewer's quote check is tested with a quote
  absent from the file.
- `make check WIENER_API_TOKEN= COMENI_FORGE_GITHUB_TOKEN=`, and the frontend tests.
- Every page is opened in a browser at 1440 and 390 wide, in both themes, and compared with its
  board. Alignment is checked by eye: DOM tests cannot establish it.
- **Acceptance:** the walk resumes at step 4 and finishes, and the operator rates each page again.

## Risks

- **Re-syncing changes the catalogue's columns.** It is a read cache, rebuilt from nf-core, so
  nothing is lost; the first sync after the migration must be run.
- **Gemma took 2m29s for two attempts.** A reviewer call adds to that on local models, which is why
  it is optional and per piece.
- **The boards use sample data in places.** The megahit and spades cards, and the reviewer's
  wording, show the design and are not results.
