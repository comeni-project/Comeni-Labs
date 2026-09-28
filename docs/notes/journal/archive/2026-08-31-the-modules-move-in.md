# The modules move into the layer — Plan 5A, 2026-08-31

**Start here.** Plan 5A is complete, all four phases, 56 of 56 boxes. The registry half is
[comeni-registry#5](https://github.com/comeni-project/comeni-registry/pull/5) and
[#6](https://github.com/comeni-project/comeni-registry/pull/6), both merged; the submodule points
at `824f3d0`. `make verify` green at 1743, `gate stub: PASS`, `docker build` green.

**Plan 5B has not started.** It is
[`../plans/2026-08-31-plan-5b-what-a-pipeline-takes.md`](../plans/2026-08-31-plan-5b-what-a-pipeline-takes.md),
five phases, and **phase B1 is independent and can land alone**.

---

## What changed

`--registry X` is the whole input to a build. A layer carries the module source beside the
contract that is a binding for it, and `vendor/` is deleted from this repository — 16,024 lines.

```
registry/
  registry.yml                       name, licence, and `layout:` — the lint's argument
  LICENSES/MIT.txt                   one file per licence. REUSE convention
  roles/<role>.yml                   one job each, saying what the job is
  rules/alignment.yml                decisions between tools, belonging to neither
  types/                             types many tools touch
  tools/nf-core/star/
      genome.index.star.yml          shared by the subtools, so it sits at the TOOL level
      align/
          contract.yml               the binding
          module.yml                 where module/ came from, and under what terms
          module/                    upstream's tree, verbatim. NEVER hand-edited
      genomegenerate/  contract.yml  module.yml  module/
```

**A thing belongs at the shallowest level that owns it.** `genome.index.star` is produced by
`star/genomegenerate` and consumed by `star/align`, so it is the *tool's*. A contract binds to
exactly one module, so it sits in that module's directory. Subtool directories are **required**,
not stylistic: nf-core ships `star/align` and `star/genomegenerate` as separate modules with
separate pins.

**`module/` is the one directory name that is not free.** Everywhere else the loader reads
`declares:` and ignores the path. A tool's source is found by its directory because upstream ships
whatever it ships — `main.nf`, `environment.yml`, `.conda-lock/`, helper scripts — and none of it
carries a `declares:` line.

## Three checks exist that could not before

All three run in `comeni-registry`'s own CI, whose `CONTRIBUTING.md` carried a paragraph
beginning *"Not checked, and it cannot be here."*

| verb | asks |
|---|---|
| `mendel conformance --registry X` | does every contract agree with its own module? **All of them**, not only the ones a goal happens to route to |
| `comeni-vendor check --registry X` | has a `module/` been hand-edited? **Offline**, so it gates like anything else. `--upstream` re-fetches and is a different question |
| `mendel lint --registry X` | is the layer arranged the way its own manifest says? |

`comeni-vendor` is its own **impure** package and the name is the point: `mendel` is
`mendel_compiler.cli:main`, `mendel-compiler` is pure, and a subcommand that fetches from GitHub
could not live there and should not look as though it could.

## The measurement that mattered was not a test

**12 contracts, 12 verified, 0 unverified — before the move and after.** Taken on the unmodified
tree first, then repeated.

A conformance check that finds no module source reports `MD0100 unverified`, which is a
**diagnostic** rather than a crash. So a move that silently lost every module would have been a
green suite with every contract quietly downgraded, and nothing existing would have said a word.
That is the shape of failure this plan had to be measured against, and no test in the repository
would have caught it.

`git status --ignored` was the second such measurement. `build/` in a `.gitignore` swallowed
`vendor/modules/nf-core/hisat2/build/` once already; **that directory moved in this plan**, and
`hisat2/build/module/main.nf` was confirmed staged by name rather than by hoping. The registry has
no `.gitignore` at all.

---

## Four things the plan did not predict

### 1. A contract's module source stopped being *derivable*

`conformance.module_path` computed `module_root / f"{nf_include}.nf"`. With the source **in** the
layer there is no root to compute against, so it became a lookup by **module key** — derived from
the contract's own `nf_include` by `comeni_core.declared.module.key_of`.

A second field saying `module: nf-core/star/align` was rejected: two fields that must agree are a
field that will one day disagree, and a lint would then have to check them against each other.

That changed one signature and everything downstream — `check`, `_meta_keys`,
`orchestrate.build`, `diagnostics_for`, the API, three forge sites — and **154 tests** with them.
The number was reported with three options before any sweeping happened; the operator chose the
sweep. There was no behavioural failure among the 154.

### 2. The stated order was impossible

A2.1 says *"the registry PR merges first"*. It cannot:

- the layer will not load under an engine that has never heard of the `module` kind, and
- the engine's suite will not pass against a layer with no modules in it.

**`ENGINE_REF` in the registry's CI is what breaks the cycle.** It pins a Comeni-Labs *commit*,
which only has to exist on a pushed branch — not on `main`. The sequence that works:

1. push the engine branch
2. bump `ENGINE_REF` in the registry PR
3. merge the registry PR
4. bump the submodule here

**Do this for any future two-repo change.** The first attempt failed CI with
`MD0010: tools/nf-core/bedtools/sort/module/environment.yml does not say what it is` — a message
about a file, for a problem about a version.

### 3. The Dockerfile had been broken since A1

`docker build` died on `Distribution not found at: file:///app/packages/comeni-vendor`. A package
added in A1, never added to a hand-maintained COPY block, and **nothing caught it for two phases
because `make check` builds no image**.

The file's own comment says *"a missing line here fails the build with `Distribution not found`,
which is how this was found"* — that was `dag-core`, and `mendel-ai` before it. **Third
occurrence**, so `tests/test_dockerfile.py` now holds the COPY block against `packages/` in both
directions, with a guard-of-the-guard for a regex that matches nothing.

### 4. A guard that would have been inert, caught before it shipped

`registry_lint` was written with a `Finding` class of its own. `tests/test_diagnostics_ownership.py`
matches exactly two emission shapes and says so — *"there are only two"* — so a positional
`Finding("MD0014", …)` was **invisible to it**. Six codes were declared, documented, answerable by
`mendel explain`, and emitted by nothing the scan could find.

That scan caught it. `Finding` was deleted rather than the scan widened: `Diagnostic` already
exists, already validates its `code` against the registry at construction, and a third shape would
put the next author back in the same position.

---

## Two guards worth knowing about

### Partial coverage is worse than none, and the tempting fix passes the first test

The layer digest now covers `module/`, because a `pipeline.yml` pins a layer and a digest covering
the declarations but not the code they describe **reads as a guarantee and is not one** —
re-vendoring at a different commit would leave the digest untouched while the pipeline changed
behaviour, provenance apparently intact.

The obvious fix is `_DECLARED_SUFFIXES += (".nf",)` and **it passes that guard**. A second guard
refuses it, because nf-core already ships `.py`, `.sh` and `.R` helpers beside `main.nf`. It was
watched failing against exactly the extension shortcut — one failure, not two.

**Running it found a third case.** nf-core ships `.conda-lock/` *inside* a module — the pinned
environment, which decides which build of the tool actually runs — and the dot rule written for
`.git` at a layer root was excluding it. `_in_module` is checked **before** the dot rule now.

### Seven checks, seven reverts, one test each

`lint()` composes seven independent checks and all eleven tests passed on the first run, which is
exactly when a suite deserves to be doubted. Reverting each check in turn (`found += []`) produced
a clean diagonal: every check has one test, no test covers two checks, nothing is inert.

That is a stronger statement than *"the tests pass"* and it cost one script.
`notes/audits/guard-ledger.md` has the table.

---

## The forge is deprecated, and there is a grep for it

Operator's decision, 2026-08-31, and stronger than the *"needs testing and general rework"*
`CLAUDE.md` said before: **it is not in use, the product is deployed nowhere, and nothing should
be invested in making its code or its tests correct until the redesign says what it is.**

**`make forge-rework`** lists what the rework must revisit — ten `FORGE-REWORK` markers.

Plan 5A changed three forge files anyway, because leaving them would have made `forge land` write
into a layout the registry no longer uses — *more* broken rather than equally broken. The markers
on those three carry the question the rework inherits rather than just "this changed": **should the
forge be authoring registry *modules* at all**, as opposed to contracts over modules
`comeni-vendor` fetched?

One frontend test is skipped rather than repointed, and it is `it.skip` **not a comment**: a skip
still typechecks and prints in every run (`321 passed | 1 skipped`), where commented code rots
invisibly and is what nobody greps for.

**Do not repoint a forge fixture.** One updated against a layout that will change again is one
updated twice.

---

## Two things recorded rather than fixed

**Role descriptions are comments, not data.** `roles/<role>.yml` opens with what the job is, in
prose a contract author reads — a role is the only thing a tier-3 rule may target and was a bare
name with nothing distinguishing `qc_per_sample` from `qc_aggregation`. It is a **comment** because
the parse reads `roles:` and a `description:` field it ignored would be a key that can be misspelled
in silence (A10). Making it data belongs to whoever next touches that kind.

**Two digests that should disagree.** A *layer* digest must move when a vendored `main.nf` does; a
*pipeline* digest must not, because re-vendoring a module must not make the same pipeline look like
a different one. Both are right — *is this the same layer* versus *is this the same pipeline* — and
the note is on both functions plus `docs/design/federation.md` §3.6, so nobody reconciles one into
the other on the reasonable-sounding grounds that two digests over one subject ought to agree.

---

## The threat model, said out loud

**`--registry X` used to mean *parse this person's YAML*. It now means *execute this person's
Groovy*.** A layer carries `main.nf` and Nextflow runs it.

Not a reason to reverse the decision — it is exactly nf-core's property, and a pipeline is code.
What changes is that **signed tags stop being a nicety**: `docs/design/federation.md` §3.4 already
specified tag signature plus a content digest, and that verification is now the only thing between
a third-party overlay and arbitrary execution. It is a **prerequisite for publishing an overlay**
rather than a later refinement.

**No sandbox is invented and none is claimed.** Nextflow runs containers; the trust boundary is the
container runtime, and a half-measure that looked like isolation would be worse than a true
sentence, because somebody would rely on it. `federation.md` §3.5 and the registry's own
`CONTRIBUTING.md`.

---

## What is next

**Plan 5B**, five phases, unstarted. Named channels, two channels of one type, custom labels on
inputs and outputs, value-vs-queue scope, and the samplesheet.

**Phase B4 is a correctness phase, not a feature one.** The attack pass found a live bug:
`tests/golden/spine/main.nf` builds references with `Channel.fromPath` — queue channels of one
item — so `STAR_ALIGN` runs as many times as the *shortest* of its three inputs. **With 24 samples
it runs once and 23 are silently dropped.** Invisible today because the stub profile globs one
sample pair. The operator's decision was to fix it in B4 rather than now: *"no thats fine no one is
using this, keep it organized and efficient"*.

**B1 and B2 are frontend phases.** Run `cd frontend && npx tsc -b && npx vitest run && npm run
lint` **from the start there**. Plan 5A's A1 and A2 both landed without it running once, which is
Plan 4 phase 6's lesson repeating — five phases shipped green while nobody opened the pages.

**Plan 4 phase 6 Task 6 is still open** — the write-up for the chrome pass, and driving the whole
builder by hand in the browser. The runs screens have never been checked against their artboards.
Serve `.design/` with `python3 -m http.server 8899` and open `http://localhost:8899/<Board>.dc.html`;
`file://` is blocked by the browser tool.
