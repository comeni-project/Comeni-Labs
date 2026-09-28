# The invariants, and why each one exists

`CLAUDE.md` states each invariant in one line. **This page holds the argument**: why the rule
exists, what it protects, and where it was once defeated. Violating any of these breaks the
product claim, not just a test.

Moved here from `CLAUDE.md` on 2026-09-28 (#118), word for word where still true. A citation to a
design document deleted on 2026-09-02 is given as `git show 83c873d^:<path>`, which prints the
file as it was.

## The invariants

Violating any of these breaks the product claim, not just a test.

### 1. `comeni-core`, `mendel-resolver`, `mendel-compiler` and `wiener-core` do not reach the network

Two partial guards, and the claim is their union — say *do not*, never *cannot*. A
static AST scan (`tests/guards/test_purity.py`) rejects the imports, the dynamic import forms, bare
`exec`/`eval`/`compile`, and a module reached as an attribute of an allowed one; a runtime
assertion (`tests/guards/test_purity_runtime.py`) installs an audit hook over a real build and fails
if any socket or process event comes from a frame in those packages. Neither is complete: the
scan cannot see a two-link attribute chain or a `getattr`, and the hook only covers code a
build reaches. **Audit A1 defeated the scan alone** — a file importing only `pathlib` and
`typing` reached `os.system` via `pathlib.os` and delivered a serialised `Goal` over TCP while
the guard reported green. **Audit A17 then defeated both**, with a libc socket obtained
through `ctypes`: FFI raises `ctypes.dlopen`/`dlsym` rather than any `socket.*` event, so it
was outside the union rather than a gap in either half. `ctypes` is now banned statically and
watched at runtime — a pure package has no legitimate FFI need, which is what makes that entry
costless in a way `subprocess` never could be. If a change to those packages seems to need
such an import, the design is wrong.
**`wiener-core` joined on 2026-08-24** (`git show 83c873d^:docs/design/wiener.md` §3.1), and it is the first
time this list has grown. A fold over events has no legitimate need to open a socket, which
is the same argument that made `ctypes` costless — and it is load-bearing in a place nobody
planned: **the OpenTelemetry SDK is a network client**, so this guard is what keeps the span
*mapping* pure and the *export* on the other side of the line, without anybody having to
remember. What it does **not** yet cover is a clock: `datetime` is on that package's
allowlist for the class and must never be `datetime.now`, because §6.1's claim — same events
in, same decisions out — dies the first week one is read inside the fold. The allowlist
cannot express *this name but not that attribute*, so a separate scan holds it.

### 2. AI authors artifacts offline; humans approve; runtime is pure lookup

The forge drafts
contracts, rules and vocabulary states — a person approves them into the registry layer.
Nothing writes there automatically.

### 3. Runtime AI is confined to three declared points

They are prompt → goal extraction (user
corrects the result before anything runs), tier-4 resolution (always flagged, always
recorded), and compiler repair (bounded to 3 attempts). Nothing else calls a model.

### 4. A tier-3 rule miss demotes to tier 4. It never calls a model inside tier 3

That keeps
the tier labels meaningful and the common case free and reproducible.

### 5. Repair patches the IR and re-emits. It never edits generated `.nf` text

Text patching
is a last resort that sets `PipelineIR.diverged = True` and is surfaced loudly.

### 6. Tier 4 is always flagged, even at high model confidence

This is the honesty mechanism
and the difference from a chat window.

### 7. Vocabularies are closed

A contract using an undeclared state fails to load. New states
arrive through the forge's approval queue as reviewed data changes, never code changes.

### 8. Routing ties are ambiguity, not a coin flip

If several contracts tie after
`(-priority, id)` ordering, demote to tier 4 rather than picking arbitrarily.

### 9. Every ambiguity emits a `DecisionRecord`

That includes one resolved by `FlagOnlyResolver`.
Records are replayed on rerun rather than re-asking the model — that is how determinism
survives having a model in the loop.

### 10. Determinism is a test, not an aspiration

Same `Goal` → byte-identical `.nf`.

### 11. The registry is a stack

A public curated base, then private overlays. A layer is a
**directory of declared files, each of which says what it is** — a `declares:` line
naming one of `DeclaredKind`, and for a vocabulary or a measurement an `id:` beside it.
**The layout is free**, and the convention the public registry uses is to group a tool's
files together: `registry/tools/nf-core/star/align/contract.yml` beside the type it produces.
Every kind stacks **through one mechanism** — `comeni_core.layered.stack()`,
parameterised by a `Kind` that declares only how its files parse, key and merge.
Hand-written loaders disagreeing on six axes is what audit root B was.
**The count lives in `DeclaredKind` and not in this sentence.** It said "four" from Plan
1.9 to Plan 1.15 and would have been wrong the day a fifth kind arrived, which is A33's
lesson and A71/A72's: a number repeated in prose is a number that goes stale while
everything around it stays true. `len(DeclaredKind)` is the honest count.
**What weakened, recorded rather than discovered** (comeni-registry#1): the directory used
to make a misfiled document impossible — a *contracts* directory held contracts, and a
misspelled *contract* directory was caught by `MD0003` because nothing read it. That was prevention *by
construction*, and a misspelled `declares:` can only be *detected*, which is `MD0011`.
Same class of error, one guarantee fewer, and `MD0003` is retired rather than emptied.
Load a stack through `mendel_resolver.layers.load()`, never by hand: the kinds are not
independent, and the wrong order fails inside a contract rather than at the caller. Every
loader takes **layer roots**, never a directory of one kind: a loader handed a slice of a
layer cannot know which layer it is reading, which is why displacement went unrecorded.
A higher layer sharing a **module key** (the contract ID minus `@version`) displaces every
lower-layer contract for that module. A different module key is an ordinary candidate and
obeys invariant 8. Keying on the module key rather than the full ID is what lets a lab pin
`@1.22.0` over `@1.21.0` without the two tying — a version bump is not ambiguity.
**Identity is `Layer.index`, never `Layer.name`**: two layers may share a name and the
lockfile's own docstring says `registry/` over `registry/` is a day-one collision.
Replacement is legal and **`Displacement` is the record that it happened** — one shape for
every kind, carried on `PipelineIR.displaced` and printed in the `OVERLAY` block, so a
measurement or a vocabulary type finally has somewhere to be reported. `states:` replaces a
type's states, `add_states:` extends them; `values:` and `add_values:` say the same pair for
a measurement. Never let an installed overlay reroute a pipeline silently.

### 12. No subscription OAuth

Claude Pro/Max tokens in third-party tools violate Anthropic's
Consumer ToS (documented 2026-02-19, enforced since 2026-01). API keys or local models only.

### 13. Self-hosted is not a degraded tier

Same registry, same resolver, byte-identical
output. The hosted instance sells convenience, never capability. Anything that would only
work on our infrastructure is a design error.

### 14. Data leaves through five declared doors and no others, on two paths

Four carry
**pipeline** data — goal extraction, tier-4 resolution, compiler repair, publication — and
the fifth carries **forge review**. `DoorPath` is the distinction and `doors_on()` is how
each half stays separately checkable.
**Why this exists, in the order the reasons actually hold** — restated 2026-09-05, because
the first reason below is the one that survives whether or not anybody is talking about
clinical data, and a rule whose stated purpose has gone quiet is a rule the next reader
deletes.
**First: it is what makes a model call reproducible and auditable.** Every crossing has a
declared input type, which is what lets a response be recorded and replayed, a prompt be
held to a golden file, and `admit()` check an answer against the question that was asked.
Untyped model calls take dicts, and nothing about a dict is reproducible. This is the
differentiator's machinery, not a compliance feature: *a reader can see exactly which parts
a model touched* is only true if there is a boundary to point at.
**Second: the pipeline doors track the prompt taint path.** *Free text enters at exactly
one door*, and the question for anything else is whether it is downstream of it — those
four are one path, prompt → goal → build → pipeline → publish.
**Third, and as a consequence rather than a purpose: clinical non-receipt.**
`git show 83c873d^:docs/design/clinical-data-protection.md` §4.2 is the long form. The claim is real and it is
*downstream* of the two above — the doors were not built to satisfy it, and it would not
survive without them. **The expensive half of that story is deliberately unbuilt**: no
`EgressRecord` exists for any door, and the three protection profiles are
[#71](https://github.com/comeni-project/Comeni-Labs/issues/71), which nothing has started.
Do not start them on privacy grounds alone.
**The forge was not a door until 2026-09-05, and the leg that changed is named.** The
2026-08-17 exemption (`git show 83c873d^:docs/notes/specs/2026-08-17-forge-phase-2.md` §1) stood on three: it has
no prompt, takes no `Goal`, and writes no `pipeline.yml`. A **review chat breaks the first**
— `ReviewTurn.content` is a string a curator types, at request time, and it goes to a
provider, which is exactly what `AuthoringRequest.prompt` is on the pipeline side. The other
two legs still hold, and `DoorPath.FORGE` is what records that. `AiPoint` is unchanged and
still corroborates the rest: invariant 3 declares three runtime AI points and the forge is
not one of them.
**Generating a proposal is deliberately not a door**, and the line drawn is *who authored
the string* rather than *how much text crosses*: a dossier is composed entirely from
vendored modules and registry files, the same public bound that keeps `Excerpt` honest.
**One list rather than two.** A separate `FORGE_DOORS` was the tidy option and is the wrong
one — the mechanism this buys is that widening the boundary means editing a file saying
*these are all the ways data leaves*, and two files creates a cheaper file, which is where
a door belonging on the other list eventually goes.
Each door carries one declared payload type, and a **named set** of fields across the whole
surface may hold free text: `AuthoringRequest.prompt`, `GateFailure.tool_message`,
`ResolvedValue.reason`, one `reason` per decision kind, `Why.reason` — the citation beside
every value in `pipeline.yml` — the `axis_reason` on `Why` and `ResolvedValue` plus
`ParamDecision.override_reason` since Plan 1.14, `ReviewTurn.content` with
`ForgeReviewRequest.candidate` since door 5, and `AuthoringTurn.content` since door 1 became
a conversation on 2026-09-09.
**Door 1's payload is `AuthoringRequest`, and it is still one door.** `PromptRequest` carried
a single string because goal extraction was assumed to be a single call; it is not — a person
reads back what the engine understood and corrects it, so the second call has to know what
the first established. Everything it gained beside the bounded tail is typed vocabulary the
engine itself issued: a `Goal` (which already crosses door 4 inside a `Pipeline`), node and
contract ids, and the **option ids** a model must answer with. That last one is the product
claim made enforceable at the boundary — a reply addressed by id cannot name a value nobody
offered. `AiPoint.PROMPT` is unchanged, and invariant 3 still declares three runtime AI
points.
**The count is deliberately not written here any more** (2026-09-05). It said "exactly two"
for a plan and a half, then four, six, seven, ten and fourteen, and it was wrong within a
day of every one of those. `FREE_TEXT_FIELDS` in `tests/guards/test_egress.py` is the count,
it is executable, and a number beside it is a second source of truth that only ever drifts —
which is A33, in the file A33 is about.
**The tenth is the first genuinely new author**: the nine before it are written by a
contract author, a rule author or the resolver, and `override_reason` is written by the
person answering a tier-4 question, in the artifact, after resolution. It exists because
until Plan 1.14 that person had nowhere to say why, and `upgrade` replaced what they wrote
with "selected the first of 1 candidates without judgement" (A77).
**Every increase up to the ninth arrived by a refactor rather than by a new kind of string
crossing** — A16 splitting `DecisionRecord` into three, `Pipeline` taking door 4, and Plan
1.14 splitting `reason` in two because it was answering both *why this axis* and *why this
answer*, which is how the registry came to cite the STAR paper as the reason HISAT2 was
chosen (A79/A107). **The tenth broke that run**, and it is written down here rather than
absorbed: `override_reason` is a new author writing at a new moment, and the argument for
it is that the alternative is a reviewer's reasoning living nowhere. Whether that argument
holds is the sort of thing a literal list exists to put in front of somebody, and it has
now done so five times.
**Eleven through fourteen arrived together, with Plan 2.5**, and they are a *refactor*
increase of the A16 kind rather than four new kinds of string: `Ambiguity` became a
`comeni_core.review.Question`, so `what` and `why_open` — which the forge had carried on
every `Hole` since Phase 1 — reach door 2 too, along with `Excerpt.locator` and
`Excerpt.text`. They were **let through rather than stripped**, on a measurement: the
forge's prompt search took a local model from 69% to 88%, and two of the three fixes
behind that were *the question never said what it was about* and *the evidence was not
readable*. A door handing a model bare candidates rebuilds the 69% configuration on the
build path. `test_the_door_carries_what_the_forge_measured_a_model_needs` holds it, so
removing them fails rather than quietly regressing.
**`Excerpt` is the first entry that is not an author.** Every other field is composed by
somebody; these two are *quoted* — a source file already holds the text and an excerpt
copies it. That is a weaker claim than the rest of the list makes, and it is written down
because *"it is only quoted"* is exactly the reasoning that widens a boundary unnoticed.
What bounds it is the source: excerpts come from vendored modules and registry files,
which are public, and never from a prompt or a goal.
**`ReviewTurn.content` is the second genuinely new author, after `override_reason`** —
2026-09-05, and it arrives with a whole door rather than by a refactor. A curator types it
at request time and it reaches a model, which is what door 1 is on the pipeline side. That
is the leg the forge's exemption stood on, and it is why the answer was to declare a door
rather than stretch the argument. `ForgeReviewRequest.candidate` beside it is *composed*
from the same public sources as `Excerpt`, so it is on the weaker footing that entry
already documents. **`ForgeReviewRequest.validation` is the field that is deliberately
not free text**: it carries `DiagnosticCode` and never a tool's output, which is
`GateFailure`'s lesson one level up — Nextflow's stderr names work directories and input
filenames, and a code is the whole of what a reader needs to look something up.
**Door 4 carries a `Pipeline`**: the artifact on disk *is* the payload, so what a person
reads before publishing and what crosses the boundary cannot disagree. `PublishBundle` is
retired. The guard's roots come from `DOORS` rather than from what happens to live in
`egress.py` — scanning the module found three doors out of four the moment the publication
payload moved, and the one it missed was the door with no undo. Everything
else is closed vocabulary; no payload may carry an `Any`-typed field, and none may carry
a plain `str` — every string is a declared ID alias or marked `Mark.FREE_TEXT`, because a
bare `str` bypasses the marker in one line and a prompt fits in it perfectly. The rule is
now an **allowlist**: `test_every_payload_field_is_a_declared_shape` enumerates what a
leaf may be rather than what it may not, because a blocklist can only forbid what
somebody named — which is how `object`, `Path` and `Any` each arrived one audit apart.
Enforced by `tests/guards/test_egress.py`, which holds both lists literally, so widening the
boundary means editing a test that says these are all the ways data leaves. Publication
is the door with no undo.

### 15. Mendel does not receive patient data

No input accepts a sample identifier, filename or
path. `Goal` holds type IDs, states and declared measurements — a shape, not data. Profiling
happens where the data is; the emitted pipeline references `params.input` as a placeholder
the lab fills at run time, and `mendel profile` writes `value: null` because it has emitted
a pipeline and not run one.
Since measurements became declared data the model can no longer refuse an undeclared key, so
the guard moved rather than weakened: `MeasurementRegistry.profile()` is the only validating
constructor, `tests/guards/test_construction.py` enforces that nothing else builds a `DataProfile`,
and `mendel build` re-routes every goal's profile through it. Delete that one call and
`profile: {sample_name: ...}` builds cleanly — which is how it was watched failing.

## The four tiers

Every module choice and parameter exits at exactly one tier and carries it forever.

| Tier | Fires when | Review level | UI |
|---|---|---|---|
| 1 structural | no choice exists — inputs force it | `none` | silent |
| 2 convention | a documented default exists | `none` | green |
| 3 data-profiled | a declared rule matched measured data | `advisory` | yellow |
| 4 ambiguous | no rule matched | `required` | red |

Tier 3 is yellow rather than silent on purpose: a rule match is only as good as the
measurement behind it. Yellow means "the machinery worked, check the premise."

Module choices carry a tier too, in `IRNode.selection`, and `needs_review()` lists a tier-4 one
by node rather than only as a `DecisionRecord` a reviewer would have to join by hand.

## The three protection profiles

Clinical labs are a target user, not a later market. Three ladders now exist and must never be
conflated: **four resolution tiers** (above), **three visibility tiers** (private / published /
curated, federation §4.2), and **three protection profiles** — below.

| | `open` | `guarded` (default) | `sealed` |
|---|---|---|---|
| prompt door | sends | shows the payload, waits for confirmation | closed — typed goals only |
| `GateFailure.tool_message` | included | `None` | `None` |
| repair | proposes and applies | proposes and applies | proposes only; a human applies |
| tier 4 | flags | flags | **blocks the build** |
| attribution | optional | when available | required |
| reference pinning | tags | tags | digests required |

Never configurable at any level: the declared doors, typed payloads, an `EgressRecord` per
crossing, tier 4 always flagged, typed-only publish bundles, no patient data received.
`guarded` is the default because the unconfigured install is the one most likely to exist.

**None of this table is implemented yet, and saying so is the point** —
[#71](https://github.com/comeni-project/Comeni-Labs/issues/71). A search for
`ProtectionProfile`, `SEALED` or `GUARDED` across every package returns nothing, because every
row describes a subsystem that does not exist: the prompt door, compiler repair and tier-4
resolution are all Plan 3 or later.

**Deprioritised 2026-09-05, by the operator's PI**, and it costs nothing today because it was
never started. Do not open #71 on privacy grounds alone; open it when a *user* needs a posture,
or when `sealed` closing the forge review chat is something somebody has asked for. **The doors
themselves stay** — they are cheap, and invariant 14 now states the reasons in the order that
survives this decision: reproducibility of a model call first, the taint path second, clinical
non-receipt as a consequence. **The profiles govern the build path**, and deterministic
scaffolding in `mendel-forge` is outside them for the same reason it is not a door: nothing a
person typed crosses it.
**The forge review chat is the exception, and it is where the table gains a real row** — door 5
is somewhere `sealed` can honestly close while scaffolding, generation and landing keep working,
which is a coherent posture for a lab curating a private registry. That row is not written yet;
the door being declared is what makes it writable.
A laboratory wanting no model calls from an installation does not configure `MENDEL_MODEL`,
which is stronger than a check: there is nothing to reach a provider *with*.

**Say "Mendel does not receive patient data" — never "anonymised".** Genetic data are not
reliably anonymisable and pseudonymised data stays personal data under GDPR Art. 9. The accurate
claim is also the stronger one: minimisation by non-receipt.

**Scrubbing was considered and rejected.** Safe Harbor needs all 18 identifier classes gone;
NLP de-identification leaves false negatives, and it fails silently. Pattern matching survives
only inverted, in `guarded`, where it halts the send and asks a human.

**We are a tool; the lab is the manufacturer.** Never claim IVDR/CLIA/CAP/ISO 15189 compliance —
those attach to a laboratory's processes. Mendel supplies the documentation substrate. Curated
means reference material a lab validates, never a validated test, because distributing across
legal entities forfeits the IVDR Art. 5(5) in-house exemption.
