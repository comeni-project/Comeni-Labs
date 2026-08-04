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

### 6.2 Six checks

| Code | Check | Catches |
|---|---|---|
| `M0101` | `nf_process` matches the module | typo → "process not found" at launch |
| `M0102` | `nf_inputs` count matches slot count | already enforced |
| `M0103` | `{empty: N}` width matches the slot's element count | "Path value cannot be null" |
| `M0104` | an `{empty}` in a slot declaring `path(...)` requires `because` | **the missing genome, the empty GTF** |
| `M0105` | every `produces[].name` appears in the module's `emit:` | `.out.bams` → crash |
| `M0106` | meta keys, **both directions** | **the silent `-s 0`** |

`M0106` is the load-bearing one. Both directions are computable: a key a module reads that
nothing sets is a silent default, and a `meta_key` declared that no module reads is dead.
That is ordinary undefined- and unused-symbol analysis, and it is exactly the class that
produced a counts matrix full of wrong numbers while every gate stayed green.

### 6.3 Diagnostics

A diagnostic names the code, the contract, **the module fact it contradicts**, what was
written, and what to write instead:

```
M0104  nf-core/star/genomegenerate@1.11.0
  slot 0 of STAR_GENOMEGENERATE is declared `path(fasta)`
    main.nf:12   tuple val(meta), path(fasta)
    meta.yml     fasta: "Fasta file of the reference genome"
  the contract supplies {empty: 2}
  → declare a port with a type_id for it, or say why with `because`
```

Plus `mendel explain M0104` for the long form, after `rustc --explain`.

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

## 7. What this means for the forge

The same design seen from the other end, and the reason it is worth building before Plan 2.

A human approving two hundred machine-drafted contracts cannot meaningfully review each one.
Approval without mechanical checks is rubber-stamping with extra steps. But every field in a
draft has an origin, and the origin decides who is responsible for it:

| Origin | Example | Machine-verifiable? | Human reads it? |
|---|---|---|---|
| copied | `nf_process`, `container`, arity | yes | no |
| derived | `emit:` names, meta keys, slot shapes | yes | no |
| **inferred** | `type_id`, **`state`**, port→type mapping | **no — not in the source** | **yes** |

**Conformance turns "inferred" into "verified" for everything except the semantic overlay.**
A reviewer looking at `samtools/sort` reads one line — *"produces `alignment.bam[coordinate_sorted]`,
inferred from the description 'Sorted BAM file'"* — instead of eighteen fields. That is what
makes two hundred modules reviewable rather than nodded through.

### Four gates a draft clears before a human sees it

1. **Conformance** — `M0101`–`M0106`. A draft that disagrees with its module is not a review
   problem.
2. **It routes** — a contract producing a type nothing consumes, or consuming one nothing
   produces, is dead weight. Graph reachability, free.
3. **It runs** — synthesise a minimal goal (`have` = its inputs, `want` = its outputs),
   resolve, emit, `preview` and `stub` it. Uses machinery that already exists.
4. **It changes nothing** — resolve every example goal before and after and diff the IR.
   *"Adding this contract reroutes 2 existing pipelines"* is invariant 11's concern, and it
   belongs at approval rather than in someone's next build.

The module's own `tests/main.nf.test` verifies the *module* upstream, so the only open
question is whether our *call* is correct — which is what conformance answers.

### The consequence for `provenance`

`Provenance` is currently per-contract: `source`, `drafted_by`, `approved_by`, `approved_at`.
For the queue to tell a reviewer where to look, origin has to be **per field**. Otherwise a
contract that is 90% copied and 10% inferred is indistinguishable from one that is entirely
guessed. That change belongs with the forge, and is named here so it is not discovered then.

---

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
will find something else, and that becomes `M0107`. A verification ladder built this way is
the only kind that stays honest, because every rung was earned by a failure somebody actually
had.

---

## Sources

- [Effective Rust — Item 35: Prefer bindgen to manual FFI mappings](https://effective-rust.com/bindgen.html)
- [rust-bindgen user guide](https://rust-lang.github.io/rust-bindgen/)
- [nf-core module specifications](https://nf-co.re/docs/guidelines/components/modules)
- [Nextflow: migrating to static types](https://www.nextflow.io/docs/latest/tutorials/static-types.html)
- [Nextflow: strict syntax and `nextflow lint`](https://nextflow.io/docs/latest/strict-syntax.html)
- [Make illegal states unrepresentable](https://deviq.com/principles/make-illegal-states-unrepresentable/)
- The vendored tree in `vendor/modules/`, and two measurements recorded in §5.
