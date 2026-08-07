# Conformance: making "if it compiles, it runs" mean something

**Status:** approved 2026-08-05, unimplemented. Plan 1.6.

Plan 1.5 found five defects by running the pipeline for the first time. Not one was
reachable by any test that existed. This document asks whether that class of failure can be
made unrepresentable rather than merely fixed, what the honest ceiling is, and what it
implies for the forge.

---

## 1. The question

`mendel build` succeeding currently tells you very little. It proved the goal routes and the
Groovy is syntactically valid. It did not prove the pipeline can execute — twice over, it
emitted a workflow that could not.

The guiding light is Rust's: **if it compiles, it runs.** Worth being precise about what
Rust actually promises, because the discipline is in the narrowness. Rust guarantees freedom
from memory-safety errors and data races. It does not guarantee your program is correct. The
technique is to pick a class of failure and make it unrepresentable, then be honest about
what remains.

So: which class can Mendel close, and what stays open?

---

## 2. What the defects had in common

| Defect | Why nothing caught it |
|---|---|
| `genome.fasta` not a declared type; index builders got an empty tuple | stubs never read their inputs |
| `STAR_ALIGN` handed an empty GTF | same |
| a test profile cannot glob over https | only a real run reaches it |
| `Gate.TEST` never used containers | the gate had never been run |
| `PipelineIR` did not deserialise | nothing had read an IR back |

The first two share a root: **a contract said something untrue about a module, and nothing
compared them.** That is the largest class and the one worth designing against.

---

## 3. Prior art: this is the FFI binding problem

A `ModuleContract` is a hand-written binding to a foreign, dynamically-typed unit. The
literature on that is unambiguous. From *Effective Rust*, on `bindgen`:

> The C and Rust declarations need to be kept in sync, and the toolchain wouldn't help with
> this — mismatches would be silently ignored, hiding problems that would arise later.

That is our two defects, described by someone who had never seen this codebase. The
industry answer to hand-maintained bindings is not "review them harder": it is to generate
them from the authoritative source and check for drift. Here the authoritative source is
`main.nf`.

**Nextflow is the least statically-typed of the workflow languages.** CWL and WDL have real
type systems; Nextflow uses qualifiers, and 25.10's optional static types are editor-side.
That is not a criticism — it is the reason this project exists. **Mendel's contract layer is
the type system Nextflow does not have**, and a type system that is never checked against
reality is documentation.

---

## 4. What the module already tells us

Measured against the vendored tree, not assumed.

**From `main.nf`:** the process name; each input slot's shape (`tuple val(meta), path(fasta)`
— which slots need a real file and which take a value); tuple arity; `emit:` labels; the
container; **which `meta.*` keys the script reads**; whether it reads `task.ext.args`.

**From `meta.yml`:** input and output names with descriptions — `fasta: "Fasta file of the
reference genome"`.

**From `tests/main.nf.test`:** an executable specification of a correct call, including a
fully-specified meta map:

```groovy
input[0] = [
    [ id:'test', single_end:true, strandedness:'forward' ],
    file(...bam), file(...gtf)
]
```

**Not there, at all:** the semantic state overlay — that this BAM is coordinate-sorted — and
which `type_id` a slot corresponds to. That is the ~40% the project exists to add.

So roughly **80% of a contract is mechanically derivable and 20% requires judgement.** That
ratio is the design.

### A note on trusting specifications

nf-core's guidelines state that *"only `meta.id` and `meta.single_end` are accepted standard
keys"*. `SUBREAD_FEATURECOUNTS` reads `meta.strandedness` regardless, and its own test
supplies it. The specification and the code disagree.

**Compute conformance from source, never from the guideline.** A rule that is documented but
not enforced is a rule that will be broken by the module you most need to be right.

---

## 5. The verification ladder

| Rung | Catches | Cost | Status |
|---|---|---|---|
| contract load | undeclared states, unknown types | ms | exists |
| **conformance** | contract ↔ module drift | ms | **this document** |
| resolution | unroutable goals, ambiguity | ms | exists |
| `lint` | syntax, strict-syntax conformance | ~10s | exists, unused in CI |
| **`preview`** | name resolution, dataflow | ~15s | **exists, wired to nothing** |
| `stub` | the DAG executes | ~1 min | nightly |
| `test` | the analysis runs and counts correctly | ~10 min | nightly |

Two measurements on this machine, worth recording because they decided the design:

```
$ nextflow lint main.nf          # containing STAR_ALIGN.out.NOSUCHCHANNEL
✅ 6 files had no errors          # syntax only — no name resolution

$ nextflow run main.nf -preview  # the same file
ERROR ~ No such variable: ... 'NOSUCHCHANNEL' for nextflow.script.ChannelOut
 -- Check script 'main.nf' at line: 26
```

`preview` needs no Docker and takes seconds, so it belongs in the **fast pull-request lane**
beside `lint`, not nightly. `Gate.PREVIEW` already exists in `gates.py` and is connected to
nothing.

---

## 6. The design

### 6.1 `ModuleSpec` — the module, parsed

**In `mendel-compiler`, not `comeni-core`.** The purity guard settled this: `re` is not on
`comeni-core`'s closed allowlist, and parsing Groovy without it would be worse code written
to satisfy a rule. Being forced to ask *why* the rule exists gave the better answer —
`ModuleSpec` reads Nextflow DSL, and **`comeni-core` must not know what Nextflow is.** Its
IR is the platform-neutral interface Wiener will consume; the moment it can parse a
`main.nf`, that stops being true.

`mendel-compiler` already knows the language intimately — it emits it — and is under a
banlist rather than an allowlist for exactly this kind of reason. `mendel-forge` is impure
and may import it when the time comes to generate rather than check.

```python
class InputSlot(BaseModel):
    position: int
    kinds: list[str]     # ['val', 'path']
    names: list[str]     # ['meta', 'fasta']

class ModuleSpec(BaseModel):
    process: str
    inputs: list[InputSlot]
    emits: list[str]
    container: str | None
    meta_keys_read: list[str]
    reads_ext_args: bool
    documented: list[DocumentedInput]     # from meta.yml
```

This is the same component the forge later uses to *generate* the derivable 80%. Building it
for checking first means nothing is thrown away.

### 6.2 Seven checks

> **This section said *six* until Plan 1.6 shipped seven.** `MD0107` and `MD0100` were folded
> in during execution. The container match already existed as
> `test_contract_containers_match_the_vendored_modules`; it is conformance by any
> definition, and leaving it in a test file while its siblings lived in a checker would be
> filing by accident of history. `MD0100` is a diagnostic that is not a failure, which the
> six-check framing had no room for.

| Code | Check | Catches |
|---|---|---|
| `MD0100` | the module source is present at all | a claim with no evidence — **warns, never blocks** |
| `MD0101` | `nf_process` matches the module | typo → "process not found" at launch |
| `MD0102` | `nf_inputs` count matches slot count | already enforced |
| `MD0103` | `{empty: N}` width matches the slot's element count | "Path value cannot be null" |
| `MD0104` | an `{empty}` in a slot declaring `path(...)` requires `because` | **the missing genome, the empty GTF** |
| `MD0105` | every `produces[].name` appears in the module's `emit:` | `.out.bams` → crash |
| `MD0106` | meta keys, **both directions** | **the silent `-s 0`** |
| `MD0107` | `container` matches the module's directive | a claimed reproducibility the module does not have |

`MD0106` is the load-bearing one. Both directions are computable: a key a module reads that
nothing sets is a silent default, and a `meta_key` declared that no module reads is dead.
That is ordinary undefined- and unused-symbol analysis, and it is exactly the class that
produced a counts matrix full of wrong numbers while every gate stayed green.

**The unused direction needs every module.** "No module in this registry reads this
`meta_key`" is a claim about all of them, so it is withheld when any module source is
missing. Without that, a laboratory wrapping bare containers — no module directories at all
— has every declared `meta_key` reported dead, and since `MD0106` blocks, the build is
refused over an inference drawn from nothing. Evidence before assertion, which is what
`MD0100` exists to say.

**`MD0105` found three on its first run.** `nf-core/samtools/index` declared a port named
`bai` where `SAMTOOLS_INDEX` emits `index`; `comeni/profile/fastqc` declared `read_length`
against FastQC's `html`/`zip`; `comeni/profile/collect` declared `profile` against MultiQC's
`report`/`data`/`plots`. All three were latent — no goal had yet routed to one, so the
emitted spine only ever read channels that existed. The samtools case is the sharpest: the
contract's own comment reads "nf-core SAMTOOLS_INDEX emits bai/csi/crai", so the author had
read the module and still wrote the wrong name. Nothing compared them.

### 6.3 Diagnostics

A diagnostic names the code, the contract, **the module fact it contradicts**, what was
written, and what to write instead:

```
MD0104  nf-core/star/genomegenerate@1.11.0
  slot 0 of STAR_GENOMEGENERATE is declared `path(fasta)`
    main.nf:12   tuple val(meta), path(fasta)
    meta.yml     fasta: "Fasta file of the reference genome"
  the contract supplies {empty: 2}
  → declare a port with a type_id for it, or say why with `because`
```

Plus `mendel explain MD0104` for the long form, after `rustc --explain`.

**A diagnostic that does not say what to write instead is half a diagnostic.** The rule
validator already works this way — "parameters that do exist: …" — and it is the single most
useful thing about that error.

### 6.4 Where it runs

A separate stage, `mendel_compiler.conformance.check(registry, module_root) -> list[Diagnostic]`,
called by the CLI rather than folded into `Registry.load` — which could not call it anyway,
now that `ModuleSpec` lives one package out. Independently testable, and loading stays
free of filesystem archaeology.

**Build-time, hard error, where the source exists.** A contract whose module source is
absent loads with an `unverified` marker recorded on the IR beside `shadowed`, so it reaches
the publish bundle. A curator can then refuse to curate an unverified contract, which is the
correct consequence: a contract without a module to check it against is a claim without
evidence.

Refusing to load such contracts outright was considered and rejected — a laboratory
wrapping a bare container has no nf-core-style module directory, and that is a legitimate
case rather than an error.

---

## 7. Why this comes before the forge

The forge drafts contracts; a human approves them. That approval is only meaningful if the
human is reading the part a machine cannot decide.

[`forge-review.md`](forge-review.md) §3 already divides a contract's fields by origin —
`copied`, `inferred`, `unsure`, `invalid` — and calls `copied` "zero risk". **Conformance is
what makes that true.** Without it, "literally present in the source" is an assertion by
whoever drafted the field, and the queue's proportion bar is measuring confidence rather
than evidence.

So the split conformance creates is:

- **`copied`, and everything computable from the module** — process name, slot shapes,
  `emit:` labels, container, meta keys — is *verified*, and needs no human at all.
- **`inferred`** — `type_id`, `state`, the port-to-type mapping — is not in the source, and
  is exactly what a human must read.

That is the ~20% from §4. A reviewer opening `samtools/sort` reads one claim, not eighteen
fields, and 200 modules becomes reviewable rather than nodded through.

**Everything derivable from the module is machine-verified. Everything requiring judgement is
human-reviewed. Nothing is merely asserted.** That is invariant 2 with a sharper edge than
"AI drafts, humans approve" — it says precisely which parts a human owns, and that set
shrinks with every check added.

Two things the forge needs that it does not have yet are recorded in
[`forge-review.md`](forge-review.md) §8, where they belong.

## 8. The honest ceiling

**Provable statically, given module source:** every process exists; every input slot is
filled with the right shape; every referenced output exists; every meta key a module reads is
set or accounted for; the DAG is acyclic and reaches the goal; the emitted Groovy parses and
its names resolve.

**Provable by running stubs:** channels actually connect; the DAG executes end to end.

**Not provable without real data:** that a tool accepts its arguments; that formats are
semantically compatible; that the analysis is scientifically right.

The middle class has a lever — nf-core modules are tested upstream, so if the module works
and our call conforms, the composition is very likely right. The last class is not a compiler
problem and must never be claimed as one.

So the promise Mendel can make is:

> **If it compiles, it runs — structurally.** Every process exists, every input is fed
> something of the right shape, every output referenced is real, and every measured fact a
> module reads has been supplied. It does not promise the analysis is correct, and no
> compiler can.

Rust guarantees memory safety, not correctness. This is the same bargain, stated as narrowly.

---

## 9. The ratchet

The rule that makes this compound rather than a one-off:

> **Every defect a run finds becomes a check the build makes.**

Five defects in Plan 1.5 produced six checks and one unused gate rung. The next real run
will find something else, and that becomes the next code. A verification ladder built this
way is the only kind that stays honest, because every rung was earned by a failure somebody
actually had.

**It compounded on the first turn.** `MD0105`'s first run found three contracts declaring
output ports their modules never emit — `bai` for `SAMTOOLS_INDEX`'s `index`, `read_length`
for FastQC's `zip`, `profile` for MultiQC's `data`. All latent, none reachable by any test
that existed. Wiring `MD0106` to the CLI then found a defect in `MD0106` itself: it asserted
"no module reads this `meta_key`" over a registry where no module could be read, and refused
correct builds. That generalises into the rule this section is really about — **a check must
not assert a property over modules it could not open** — and it is the shape the next code
should be tested against before it ships.

Of Plan 1.5's five defects, two (the missing genome, the empty GTF) are now caught at build
time on any registry by `MD0104`; one (the container-less `Gate.TEST`) by a unit test; one
(`PipelineIR` deserialisation) was already covered. The fifth — a test profile cannot glob
over https — is **not catchable here and probably not anywhere static**. Comparing a
contract to a module cannot know that `fromFilePairs` brace-expands by listing a directory.
The ladder has a top, and naming it is part of staying honest.

---

## Sources

- [Effective Rust — Item 35: Prefer bindgen to manual FFI mappings](https://effective-rust.com/bindgen.html)
- [rust-bindgen user guide](https://rust-lang.github.io/rust-bindgen/)
- [nf-core module specifications](https://nf-co.re/docs/guidelines/components/modules)
- [Nextflow: migrating to static types](https://www.nextflow.io/docs/latest/tutorials/static-types.html)
- [Nextflow: strict syntax and `nextflow lint`](https://nextflow.io/docs/latest/strict-syntax.html)
- [Make illegal states unrepresentable](https://deviq.com/principles/make-illegal-states-unrepresentable/)
- The vendored tree in `vendor/modules/`, and two measurements recorded in §5.
