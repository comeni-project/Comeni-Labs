# Tool constraints, phase 1 — design

**Issue:** #460 (part 1 of #463, *facts, measurers, constraints and decisions*). It blocks the quast walk (#412).
Phase 2 is #464. Brainstormed with the operator on 2026-11-05 and 2026-11-06; the whole system is
recorded on #463.

## Why

On the quast walk, GPT drafted a contract that cannot be true:

- **Optional inputs.** QUAST's `fasta` (the reference) and `gff` are optional. meta.yml says each
  "has to contain at least a non-empty string dummy value", and the script reads
  `fasta ? "-r $fasta" : ''`.
- **Conditional outputs.** Its `transcriptome`, `misassemblies` and `unaligned` outputs are
  `optional: true`; they exist only when a reference is given.
- **The contract format has no way to say either.** The model tried `optional` and `pattern`
  fields, and the engine refused both (`OutputPort` forbids extras).
- **Other tools have relations too.** Testing nf-core modules found them:
  - `gatk4/haplotypecaller` takes `dbsnp` and `dbsnp_tbi` together or not at all;
  - `fastp` writes its trimmed reads unless `discard_trimmed_pass` is set, and merges only paired
    reads;
  - `kraken2` writes its FASTQs only when `save_output_fastqs` is set.

A contract states what a tool **can** do. That is a fact about the tool, distinct from a
**decision** about what to choose, which is #461's. This phase lets a contract say which inputs are
optional, when an output exists, and how inputs and flags constrain each other, and it makes the
engine check, route and emit accordingly.

## Goals

- **Optional inputs:** an input can be marked optional, with a stated way to pass it when it is
  left out.
- **Conditional outputs:** an output can be produced always, or only under a `when`.
- **Constraint rows and groups:** a contract can declare `when` → `requires` / `forbids` rows,
  each with a reason, and the groups `one_of`, `any_of` and `all_or_none`.
- **One evaluator:** conditions use the same `when` syntax and evaluator as rules, over input and
  parameter facts.
- **Checks:** the engine finds dead inputs, fake optionals, contradictions and outputs that are
  never produced, when a contract is loaded or forged.
- **Optional through to the run:** an optional input can be switched on as an optional pipeline
  input, which each run may supply or leave empty (Galaxy's model, within invariant 15). The
  router makes it required only when a later step needs an output that depends on it.
- **The builder** shows every input of a step, optional ones as hollow ports with what they add.
  Mendel's AI switches them on from the goal, flagged and confirmed by the person.
- **Emission:** the compiler emits a valid placeholder for an input that is left out.
- **The forge:** its AI drafts these items in the Contract piece from `main.nf` evidence, the
  engine cross-checks them, and a person approves them.
- **The quast walk** completes with a contract that says what QUAST really does.

## Non-goals

- **Inputs typed by condition and modes** (minimap2, salmon): #464. Inputs already accept several
  alternatives (`InputPort.accepts`, first match wins); phase 2 adds *type facts* and modes.
- **Decision tables, hit policies, derived facts, richer parameter values** (lists, units) and
  values shared across steps: #461.
- **Run-time facts and decisions:** #217 and #465. **Per-sample evaluation:** #466.
- **Changing curated contracts.** Every existing port stays required and every output stays
  produced always, by default, so they load unchanged.

## Anti-goals

- **A free boolean expression language.** `when` stays the existing predicate table: AND within a
  clause, `not`/`in`/comparisons, `present`/`absent`. The reasoning in `InputPort.accepts` holds:
  "why is X here?" must answer itself in a sentence, not as a solver trace.
- **A constraint that chooses.** Constraints say *allowed, required, forbidden, produced*. Whether
  to connect an optional input is a decision, recorded as one.
- **Dropping an input silently.** A left-out input is recorded with its reason and can be changed.
- **Failing at run time what the build could refuse.** A missing required input is refused at
  build time (CWL's known pitfall).

## Constraints on the design

- **Purity:** the contract model, the evaluator and the checks live in pure packages
  (`comeni-core`). The router is in `mendel-resolver`, also pure.
- **Reproducibility:** the same goal and recorded decisions give the same `pipeline.yml` and
  `.nf`. Unordered collections are sorted before serialising.
- **Diagnostics** are declared in `diagnostics.yml` and emitted through `coded()`. `MD06xx` is
  free; this design uses it.
- **No backward compatibility before v0.1.0.** But this design needs none: every new field has a
  default meaning today's behaviour.
- **`make verify`** is required: this changes resolution, emission and the saved pipeline schema.

## Decided (operator, 2026-11-05 to 11-06)

- One fact space, one `when` syntax, one evaluator and one checker serve both constraints and
  decisions. Constraints live in the contract; decisions live in rule tables (#461).
- Every constraint row can carry its own `when`.
- The groups follow Boutiques: `one_of`, `any_of`, `all_or_none`.
- Whether to connect an optional input depends on the goal: it is a decision, never hard-coded.
  Mendel's AI and the builder use the capability; the engine only says what is possible.
- An optional input stays optional through to the run: the pipeline gets an optional input, and
  each run supplies a file or leaves it empty (after Galaxy and KNIME, compared on 2026-11-06).
- A mode that changes the tool's job is a separate contract (phase 2's concern; recorded here
  because it bounds this design).
- The forge's AI drafts constraints; the engine checks them; a person approves them.

## Design

### 1. The contract

The fields are added to the models in `comeni_core/declared/contract.py`:

```yaml
consumes:
  - {name: consensus, type_id: assembly.fasta}
  - {name: fasta, type_id: genome.fasta, required: false}
  - {name: gff, type_id: annotation.gff, required: false}
produces:
  - {name: results, type_id: qc.report::assembly, format: [folder]}
  - {name: misassemblies, type_id: qc.report::assembly, format: [tsv],
     produced_when: {given.fasta: present}}
nf_inputs:
  - {ports: [consensus]}
  - {ports: [fasta], absent: 2}        # [[:], []] when fasta is left out
  - {ports: [gff], absent: 2}
constraints:
  - {when: {given.gff: present}, requires: [fasta],
     because: "QUAST reads --features only against a reference (-r)"}
groups:
  - {kind: all_or_none, members: [dbsnp, dbsnp_tbi],      # gatk4/haplotypecaller
     because: "the tabix index is read with the VCF it indexes"}
```

- **`InputPort.required: bool = True`.**
- **`OutputPort.produced_when: dict | None = None`.** `None` means always; otherwise it is a
  `when` clause.
- **`NfInput.absent: int = 0`.** The empty-tuple width to emit when every port of this entry is
  left out, with the same arity semantics as `NfInput.empty`.
  - It is required on any entry whose ports are all optional (`MD0601`).
  - It is forbidden on an entry with a required port (`MD0601`).
  - A `val` input left out is out of scope here: a parameter fills it (`NfInput.param`).
- **`ModuleContract.constraints: list[ConstraintRow]`.** A `ConstraintRow` has:
  - `when: dict = {}`;
  - `requires: list[str] = []`;
  - `forbids: list[str] = []`;
  - `because: str` (required, non-empty);
  - `cite: str = ""`.

  At least one of `requires` or `forbids` must be non-empty.
- **`ModuleContract.groups: list[Group]`.** A `Group` has:
  - `kind`: `one_of`, `any_of` or `all_or_none`;
  - `members`: at least two;
  - `when: dict = {}`;
  - `because`.

  Groups are shorthand: the checker and the evaluator expand them into rows.
- **What `requires`, `forbids` and `members` name:** contract input ports or contract `params`.
  An unknown name is refused at load (`MD0602`).
- **Defaults:** they reproduce today's contracts exactly. Serialisation leaves out default values,
  as `OutputPort` already does for an empty `format`, so existing contract digests do not change.

### 2. Facts and the evaluator

**The facts a contract's `when` can test in phase 1** (measurements wait for #466, §4):

| Fact key | Value | Example |
|---|---|---|
| `given.<port>` | `present` when the input is connected, `absent` when left out | `{given.fasta: present}` |
| `param.<name>` | the parameter's resolved value; `absent` when unset | `{param.bam_format: false}`, `{param.discard_trimmed_pass: {not: true}}` |

**The evaluator moves** from `mendel_resolver/predicates.py` to `comeni_core` (*builder's call:
the module name*). Both the router and the contract checks then use one evaluator, as #463 requires.
`mendel_resolver.predicates` re-exports nothing; callers import the new home (no aliases before
v0.1.0).
- **Unchanged:** the predicate syntax and semantics, including `present`/`absent` and the
  tier-of-row logic.
- **New:** dotted fact keys are legal. Each namespace is closed: `given.` names a port of this
  contract, and `param.` names a param of this contract.

**`evaluate(contract, setup) -> Verdict`** is pure and lives in `comeni_core`.
- **`setup`:** the connected ports, the resolved parameter values and the known facts.
- **`Verdict` lists:**
  - **`missing`:** ports that are required (by `required: true` or a row whose `when` holds) and
    not connected;
  - **`forbidden`:** ports or params a holding row forbids, that are connected or set;
  - **`produced`:** outputs that exist under this setup;
  - **`sentences`:** one plain sentence per applied row, e.g. "`gff` is used only with `fasta`
    (QUAST reads --features only against a reference)".
- **Sentence rendering is deterministic.** The order follows the contract's declaration order.

### 3. Checks

**`check_constraints(contract) -> list[Diagnostic]`** runs at `ModuleContract.load` (after
`check_against`) and in the forge on every contract read.
- **Setups it enumerates:** every subset of optional ports (required ports are always present).
- **Values it tries for each param named in a `when`:**
  - a boolean or enum: its domain;
  - a number: one value on each side of every threshold that appears;
  - a param with no domain: `absent`, plus each literal compared in a clause.
- **It refuses** more than 4,096 setups (`MD0607`), so a check never silently skips cases (*my
  call: the bound*).

| Code | Finding |
|---|---|
| `MD0603` | **Contradiction:** no setup satisfies the constraints |
| `MD0604` | **Dead input:** an optional port is connected in no valid setup |
| `MD0605` | **Fake optional:** an optional port is connected in every valid setup |
| `MD0606` | **Never produced:** an output's `produced_when` holds in no valid setup |

**What a finding does:**
- At registry load, all four refuse the contract.
- In the forge, they are engine findings on the items involved, shown as today's MF052x findings
  are. They do not refuse an answer; they refuse assembly until resolved, as an invalid contract
  is refused today (*my call*).

### 4. Optional inputs stay optional through to the run

Decided with the operator on 2026-11-06, after comparing KNIME, Galaxy, ComfyUI and n8n. Invariant
15 holds: a pipeline holds shapes, and files are bound per run. So "use a reference or not" is
split into two choices.

- **At build time, "can this pipeline take a reference?"** Switching an optional input on adds an
  **optional pipeline input**, an entry channel marked optional.
- **At run time, "is there one for this run?"** The run sheet lets the person supply the file or
  leave it empty. The same pipeline gives quast's reference reports on runs with a reference and
  the basic reports on runs without one. Nothing is rebuilt.

An optional input of a step is in one of three states. Each is recorded on the step with who set
it and why.

| State | Meaning | Emitted as |
|---|---|---|
| **off** (the default) | Not part of this pipeline | the `absent` placeholder in the call |
| **optional** | A pipeline input that may be left empty per run | `params.<name> ? <entry expression> : Channel.value(<absent placeholder>)` |
| **required** | A pipeline input that every run must supply, or a wire from another step | as any routed port |

**Who sets the state:**
- **The person**, in the builder (§6) or in chat.
- **Mendel's AI**, from the goal. It proposes switching an input on, and the person confirms
  with a click. Tier 4 still stops for a person today, and Settings → Building's "Let a model
  answer, flagged" later removes the click.
- **A rule**, once #461 lands, at tier 3.

**What the router does automatically, with the reason recorded:**
- **Required:** when a later step in the route needs an output whose `produced_when` tests
  `given.<port>`, that port becomes **required**. The run sheet then says the file is needed. A
  conditional output cannot feed a step that must always run.
- **Connected by need:** when a constraint row requires a port given what is connected (`gff`
  needs `fasta`), the router connects it. When the person switches `gff` on, `fasta` follows, and
  the person is told.
- **Never decided by the router alone:** switching an input from **off** to **optional**. That
  is the person's, the AI's (confirmed) or a rule's.

**Where the router changes:** `mendel_resolver/router.py`, in the `for port in chosen.consumes`
loop.
- **Required ports** route as today.
- **An optional port in state optional or required** routes like a required port: to an upstream
  producer, or to an entry channel.
- **An entry channel from an optional port** is marked optional unless the state is required.
- **Each step's input states** go on `RouteStep` and the IR `Step`, and are saved in
  `pipeline.yml`, so a replay reproduces them.

**Constraint checks around routing.** These answer the builder check's first question.
- **Parameter values are settled after routing**, by `resolve()`. Routing reads only what is
  known by then: goal overrides and declared defaults.
- **After parameter resolution**, `evaluate()` runs on every step's setup. A `missing` port that
  can be routed is routed; otherwise the build is refused (`MD0609`, with the row's sentence). A
  `forbidden` connection or set parameter is refused (`MD0610`). A forbidden parameter is never
  silently dropped.
- **No question is asked mid-route.**
- **A `param.` condition on a needed conditional output** must hold under the resolved settings.
  Otherwise the build is refused, naming the parameter (`MD0608`). Choosing that value is #461's.
- **For an optional entry channel, `given.<port>` is unknown at build time.** `evaluate()` treats
  it as either value. A row that would be violated by one of them is a build-time refusal when
  the run cannot avoid it. Otherwise the run sheet enforces it (§5).

**Parameter facts** (builder check, question 4):
- `param.<name>: absent` means **no value**. A parameter with a declared default always has one,
  so flags are tested by value: `{param.save_output_fastqs: true}`.
- `requires`, `forbids` and group `members` that name a parameter mean "has a value". For a
  boolean flag, write the value test in `when` instead.

**Measurements in a contract's `when`** (builder check, question 5) are left out of phase 1.
- They can vary per sample (cohorts), which is #466. Only `given.` and `param.` facts are legal,
  and anything else is `MD0602`.
- fastp's "merge only paired reads" is recorded on #466 as a case.

### 5. Emission and the run

**Emission** (`mendel_compiler/emit.py`):
- **An entry whose ports are all off** emits `_empty(entry.absent)`, as `_argument` already does
  for `NfInput.empty`.
- **An optional entry channel** emits `params.<name> ? <expression> : Channel.value(<placeholder>)`,
  built from the channel's normal expression (`_entry_channels`, with `_as_value` for run scope).
- **An output that is not produced** under a step's verdict is never wired downstream. The
  router already guaranteed that nothing that must run needs it.

**Partial entries** (builder check, question 6): an `nf_inputs` entry with several ports must have
all of them required, or all of them optional and in one `all_or_none` group. Anything else is
refused at load (`MD0601`). "Only some connected" then never arises.

**The artifact** (`comeni_core/artifact/pipeline.py`):
- `Channel` gains `optional: bool = False`, plus the placeholder it falls back to.
- Run-time constraint rows that involve optional channels are carried so the run sheet can check
  them, as rendered sentences plus the predicate (*builder's call: the shape*).
- The saved-pipeline schema changes, so `make verify` is required.

**The run sheet** (`frontend/src/build/RunSheet.tsx`, bound by Wiener):
- **An optional channel** shows as "optional", with what supplying it adds, taken from the
  `produced_when` sentences: "gives misassemblies, unaligned and alignment reports".
- **Leaving it empty** passes no `params.<name>`.
- **A run-time constraint** is checked before the run starts. For example: "give a reference with
  the GFF, or leave both empty".
- Wiener stays unaware of contracts: it reads the artifact's channels and sentences.

**Conformance** (`conformance.py`):
- An output with `produced_when` must still be an emit in `main.nf`, which is the existing
  `MD0105` path.
- **New check:** an output that `main.nf` marks `optional: true` but the contract says is produced
  always is flagged (`MD0611`). It refuses at load for a curated contract and is a finding in the
  forge.
- `ModuleSpec` needs to parse `optional:` on emits (*builder: the parser is in `modulespec.py`*).

### 6. The builder

The patterns come from KNIME (filled and hollow ports), Galaxy (optional workflow inputs),
ComfyUI and Unreal (a setting until wired) and n8n ("Add option", conditional fields).

- **A step card shows all its inputs.** Required inputs are filled ports. Optional ones are
  hollow ports, folded under "+N optional inputs", each with what it adds ("adds misassemblies,
  unaligned and alignment reports").
- **Switching one on** asks where it comes from: another step's output, or a new optional
  pipeline input. A connection that a constraint forbids explains why, with the evaluator's
  sentence: "`gff` needs `fasta` connected first".
- **A required-by-need input** shows why: "required: misassemblies feeds the report step".
- **Flags** are the step's settings (the existing Settings panel). Optional ones sit behind "Add
  option". Settings that a `when` rules out are hidden, with a line saying why.
- **Mendel's AI uses the same actions**, as authoring commands: switch an input on or off, and set
  a flag. A change it proposes is shown flagged as the AI's and waits for the person's click.
- *Builder's call:* layout within the existing canvas and panels. Inspect it in a browser at 1440
  and 390, light and dark. A Claude Design canvas comes first if the layout is not obvious.

### 7. The forge

**Drafting.** The Contract piece's prompt becomes `forge.draft.v6`. It teaches:
- the item shapes: `required` on inputs, `produced_when` on outputs, `absent` on `nf_inputs`;
- the new keys `contract:constraint:<n>` and `contract:group:<n>`;
- the evidence to read in `main.nf`:
  - `optional: true` on an emit;
  - `x ? "--flag $x" : ''` for an input or a val;
  - `error("…requires …")` lines;
  - a dummy-value note in meta.yml.

**Item validation** (`mendel_forge/forging/values.py`) accepts exactly these fields; extras are
refused as now.

**Engine findings**, advisory, from `ModuleSpec`, shown on items like the MF052x findings:
- `MF0530`: an emit that `main.nf` marks `optional: true` has no `produced_when`;
- `MF0531`: an input the script uses only under `?:` is marked required;
- `MF0532`: an `nf_inputs` entry whose ports are all optional has no `absent`;
- the `MD0603`–`MD0606` checks, applied to the current items.

**The page:** each constraint and group item reads as its sentence, with its raw value under it.
The tool diagram shows optional inputs as hollow and conditional outputs as "only with fasta".

### 8. Documentation

- **The reference page:** the contract fields and `MD0601`–`MD0611`, on the contract-format
  reference page (find its current home; give the subject one home).
- **User how-to:** optional inputs in the builder and the run sheet.
- **The explanation:** a short section on constraints versus decisions, linking #463.
- **`CHANGELOG.md`:** under `comeni-core`, `mendel-resolver`, `mendel-compiler`, `mendel-api` and
  the frontend.

## Verification

- **Unit, `comeni-core`:**
  - `evaluate` on quast, kraken2 and gatk4/haplotypecaller contracts written as test fixtures;
  - each `MD06xx` check, with a contract that triggers it and one that does not;
  - curated contracts load with unchanged digests.
- **Router:**
  - quast with only assemblies leaves `fasta` and `gff` off;
  - switching `gff` on connects `fasta`, with the reason recorded;
  - a later step needing a reference-only report makes `fasta` required;
  - a forbidden connection is refused;
  - replaying a saved pipeline reproduces every input state.
- **Compiler:**
  - golden `.nf` files for quast with the reference off, optional and required;
  - `make verify` and `make static`, including a stub run with and without `params.fasta` for the
    optional case.
- **Run sheet:** an optional channel left empty starts the run; a run-time constraint refuses a
  GFF without a reference.
- **Builder:** browser inspection of hollow ports, switching an input on, and the explanations, at
  1440 and 390, light and dark.
- **Forge:** drafting with a recorded reply; each MF053x finding; a guard that fails on today's
  code for each.
- **Live:** the quast walk resumes on GPT: redraft the Contract piece and approve it, then the
  remaining pieces.

## Order

Each stage has its own plan section, its own checks and a commit.

1. **Contract model**, the evaluator move, `evaluate`, checks (`comeni-core`).
2. **Router**, input states, IR and `pipeline.yml` (`mendel-resolver`, `comeni-core` plan).
3. **Emission**, the artifact's optional channels, conformance (`mendel-compiler`, `comeni-core`
   artifact).
4. **The forge:** prompt v6, values, findings, page. *This unblocks the quast walk's Contract
   piece.*
5. **The run sheet**, optional channels and run-time constraint checks (frontend, Wiener's binding).
6. **The builder:** hollow ports, switching inputs on, explanations, and the AI's authoring
   commands.
7. **Docs**; resume the quast walk through to assembly and a run.

This is about twice the first draft: it now includes the run sheet, the builder and the artifact
change. My estimates have run about ten times long on this project. So it is many sessions, and I
stop and report if a stage passes twice its plan's estimate. Stages 1–4 are enough to resume the
quast walk in the forge; stages 5–6 are what makes it usable in a build.

## Left to the builder

- The evaluator's new module name and the `Verdict` type's shape.
- How `producers_of` exposes the matched output port, so `satisfy()` can read its
  `produced_when`.
- The artifact's shape for run-time constraint rows.
- The layout within the existing builder and forge components.
- The exact diagnostic wording, which follows `diagnostics.yml` conventions.

## Calls I made (for the operator to check)

- **Off is the default** for every optional input. The router never switches one on by itself; it
  only makes one required, or connects one a constraint requires, and records why.
- **Mendel's AI proposes and the person confirms**, until "Let a model answer, flagged" exists.
- **Parameters:** routing reads only overrides and defaults; every step is re-checked after
  parameters resolve, and a violation is refused at build time. A parameter with a default always
  has a value.
- **Measurements in a contract's `when`** wait for #466.
- **`nf_inputs` entries:** one with several ports is all required, or one `all_or_none` group.
- **The checks:** enumeration is bounded at 4,096 setups and refuses beyond that. At registry
  load, a finding refuses the contract; in the forge, it blocks assembly but not answers.
- **`absent`** is an explicit width on the `nf_inputs` entry, not derived.
- **Digests:** new fields serialise only when they differ from their defaults, so curated digests
  stay unchanged.
