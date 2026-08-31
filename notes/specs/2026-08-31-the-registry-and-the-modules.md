# The registry, and where the modules live

*Written 2026-08-31, at the operator's instruction: `vendor/` does not belong in this repository,
and the registry itself is confusing to use. This spec is Part A of Plan 5;
[`2026-08-31-what-a-pipeline-takes.md`](2026-08-31-what-a-pipeline-takes.md) is Part B and runs
after it, because both change `registry/` and doing them in the other order edits the same files
twice.*

---

## 1. The complaint, and what it turned out to be

> *"Why is vendor in this repo? The entire point of the registry is to split the maintainability
> of the modules and the maintainability of the tool."*

The premise is right and the conclusion needs one correction. **Three things are conflated here,
not two:**

| | what it is | whose it is | licence | today |
|---|---|---|---|---|
| **declarations** | contracts, types, rules, measurements, roles | ours, curated | CC-BY-4.0 | `registry/`, a submodule |
| **module source** | the real `process STAR_ALIGN { … }` | nf-core's, verbatim | MIT | **`vendor/`, in this repo** |
| **the shipped copy** | a snapshot beside the emitted artifact so it runs with no registry and no network | derived | inherited | written by `keep` |

`vendor/` being in the code repository is wrong on every count: nobody here maintains it, it is
not code, and the only thing that ever writes to it is `uvx nf-core modules install`.

**It moves into the registry, beside the contracts that bind it, one self-contained directory per
tool.** §2.2 is the argument — a Comeni registry is a *layer* rather than an index, and a layer
has to be self-sufficient — and §3 is the shape.

### 1.1 What reads it today

Worth stating, because it bounds the change:

- **`mendel-compiler`'s conformance check** — a contract is a hand-written FFI binding, and
  `mendel build` refuses to emit when a contract and its module disagree (`MD0104`, `MD0105`).
  This is the load-bearing consumer.
- **`services/bundle.py`** — `keep` copies the vendored source next to the artifact, which is
  what `MD0210` requires and what makes an emitted pipeline runnable years later.
- **the forge** — `forge discover` reads `vendor/modules/` and therefore sees **13 tools**
  (issue #77).
- **`mendel-api`** — `settings.source_root` defaults to `./vendor`, and `docker-compose.yml`
  bind-mounts it into two services.

### 1.2 Two things inside `vendor/` are read by nothing — and `vendor/modules/` is not one of them

Stated this way round because the first draft of this section was read as *vendor is unused*, and
it is the opposite: `vendor/modules/` is load-bearing, and §1.1 lists the five readers.

**What is dead is `vendor/conf/`**

— eight nf-core container-config files, and **no code path opens any of them.** The
label→resource mappings that Mendel emits are *transcribed* into `emit.py` as a quoted
convention; its own docstring says so: *"nf-core's `conf/base.config`, quoted rather than a
judgement invented"*. Deleted rather than moved.

**And `vendor/modules.json` is orphaned**, which is the more interesting of the two. It holds the
git SHA of every vendored module — the thing that makes `vendor/` reproducible — and it is
written by `nf-core modules install` and **read by nothing we own**. The pins that guarantee our
provenance are maintained by somebody else's tool and consulted by none of our code. §3.3 is
where they end up.

---

## 2. What comparable systems do

Researched rather than asserted, because the answer is not obvious and this repository has been
wrong about it once already.

**Every catalogue at scale separates declarations from artifact bytes, and links them by pinned
revision or content hash:**

| System | declarations | bytes | link |
|---|---|---|---|
| **nixpkgs** | derivations, in-repo | never in-repo | fixed-output derivation, by hash |
| **Homebrew** | formulae in `homebrew-core` | bottles in GitHub Packages | version + sha256 |
| **Bioconda / conda-forge** | recipes in git | packages on anaconda.org | recipe → build |
| **Galaxy ToolShed** | tool wrappers (XML) | binaries via conda | requirement |
| **Terraform Registry** | metadata index | modules are git repos | version tag |
| **crates.io** | index | tarballs on a CDN | version + checksum |

**nf-core is the one counterexample, and it is the most relevant one** — so it is worth being
precise about what it actually says. An nf-core **pipeline** vendors modules into `modules/` with
`modules.json` pinning git SHAs. `nf-core/modules`, the **catalogue**, vendors nothing: it *is*
the source. The thing that vendors is the artifact, not the index.

Mendel has both roles and they are different objects: **`registry/` is the catalogue and the
emitted pipeline is the artifact.** So the general pattern says *the registry declares, the
emitted pipeline vendors, and nothing in between keeps a mirror.*

### 2.1 The nixpkgs precedent matters twice

nixpkgs is the closest analogue for the second half of this spec too. Its tree was free-form —
`pkgs/development/libraries/…`, by category, by taste — and at scale it became unnavigable, so
nixpkgs introduced **`pkgs/by-name/<shard>/<name>/package.nix`**: a strict, mechanically-checked
layout, enforced by CI, with the old tree kept for what predates it.

That is exactly the situation in §4. A catalogue whose layout is a matter of judgement stops
being navigable somewhere between ten and a hundred entries, and the fix everybody converges on
is a stated layout a machine can check.

---

### 2.2 Why the general pattern does not decide this, and what does

**A Comeni registry is not an index. It is a LAYER, and a layer has to be self-sufficient.**

That is the difference from every row of the table above, and it is the argument that settles
this — the operator's instruction on 2026-08-31 was *"the vendor folder needs to move to the
registry, that code should not live in this repo"* and *"all the modules need to be
self-isolated"*, and the design reason is stronger than the tidiness reason.

Invariant 11: a layer is *a directory of declared files, each of which says what it is*, and
every loader *"takes layer roots, never a directory of one kind"*. The module source is the one
declared thing that lives **outside** the layer. Three consequences, and the third is a hole:

- **Two roots where the design has one.** `mendel build --registry X --vendor Y`, and `mendel-api`
  carries `registry_root` and `source_root` separately for the same reason.
- **A layer's self-consistency is not checkable.** A registry tag and a vendor SHA live in
  different repositories and can drift; `MD0104` only notices at build time.
- **An overlay cannot ship its own tool.** A laboratory's private layer can declare a contract for
  an in-house process and has **nowhere to put that process's code**. It can ship a binding for a
  program it cannot ship. That is not an inconvenience — stacking is invariant 11 and this is a
  case it cannot express.

None of that is true of nixpkgs or Homebrew, because a nixpkgs *channel* is not something you
hand to a colleague and expect to build offline. A Comeni layer is exactly that: invariant 13
says self-hosted is not a degraded tier, and a clinical site with no route to github.com is a
normal customer here rather than an edge case.

### 2.3 The three objections, and why each is weaker than it looked

Recorded because they were raised in the first draft of this spec and answered, rather than
quietly dropped:

- **Licences.** `docs/design/federation.md` §6 was cited against co-location. Read again, it says
  *"Vendored nf-core modules under `modules/` retain their own licences and notices"* — and it
  says it **inside the registry's own licensing section**. The design already put them there. The
  mechanism is a per-tool notice file, not a repository split.
- **Size.** 748 KB for 13 modules, so roughly 57 KB each: ~90 MB at the nf-core-plus-pegi3s
  corpus of ~1,600. That is the order of nf-core/modules itself and a twentieth of a nixpkgs
  checkout. It is a real cost and it is a partial-clone problem, not a design problem. **The
  threshold to watch** is a fresh clone crossing ~30 s on a normal connection; `git sparse-checkout`
  by namespace is the answer when it does, and nothing about this layout prevents it.
- **Mirroring.** It is a mirror and it does have to be kept in step. That work is already
  scheduled: issue #64 is `forge check` against **upstream** rather than against the vendored
  copy, which is exactly the drift detector a mirror needs. The pin (§3.3) is what makes it
  answerable.

## 3. Where the modules go: into the layer, one self-contained directory per tool

**`vendor/` moves into `comeni-registry` and is deleted from this repository. A tool is a
directory holding everything about that tool and nothing about any other.**

```
registry/tools/nf-core/star/align/
    contract.yml          the binding — ports, roles, routes, ext args
    module/               UPSTREAM SOURCE, verbatim, unmodified
        main.nf
        meta.yml
        environment.yml
    module.yml            provenance: repo, sha, path, excluded, and an SPDX licence id (§3.4)
    types/                types this tool introduces — genome.index.star
    docs.md               generated by `mendel docs`, never hand-written
```

### 3.1 Self-isolated, and what that has to mean to be worth saying

The operator's word was **self-isolated**, and it is a stronger requirement than *co-located*.
Four properties, each of which is checkable:

- **Nothing outside the directory is needed to understand the tool.** Contract, source, the types
  it introduces, its documentation and its licence.
- **Nothing inside it is referenced from outside** except by id. No relative path from one tool's
  files into another's, so a directory can be copied into another layer and still work.
- **Deleting the directory removes the tool completely**, leaving no dangling reference the
  loader does not report. `mendel registry lint` (§4.3) is what makes that true rather than
  hoped-for.
- **`module/` is upstream's, byte for byte.** Nothing in this repository or the registry edits a
  vendored `main.nf`. That is what makes `forge check` against upstream a diff rather than a
  judgement, and it is the same rule as invariant 5's *repair patches the IR and never edits
  generated `.nf` text*, applied one level up.

### 3.2 Why this is the design and not merely the instruction

§2.2 is the argument: **a layer must be self-sufficient**, and the module is the one declared
thing that was outside it. Three things fall out immediately and all three are simplifications:

- **One root, not two.** `mendel build --registry X --vendor Y` becomes `--registry X`.
  `mendel-api` loses `source_root` as a separate setting; `docker-compose.yml` loses a bind mount.
- **A layer is internally consistent by construction.** The contract and the module it binds are
  in the same commit of the same repository, so the drift `MD0104` catches at build time cannot
  be introduced by a tag bump in one repository and not the other.
- **An overlay can ship a private tool.** The hole §2.2 names closes: a laboratory's layer puts
  its in-house process's `main.nf` in `module/` exactly as the public registry does, and the
  stacking rules — module key, displacement, `Displacement` records — apply unchanged.

### 3.3 `module.yml` — provenance, not a fetch instruction

The pins that live in `vendor/modules.json` today are written by `nf-core modules install` and
read by nothing we own (§1.2). They become a declared kind, one per tool, beside the source they
describe:

```yaml
# registry/tools/nf-core/star/align/module.yml
declares: module
id: nf-core/star/align
upstream:
  repo: https://github.com/nf-core/modules.git
  sha: 6d46786420b4d7bc88eba026eb389c0c5535d120   # immutable, never a branch
  path: modules/nf-core/star/align
excluded: [tests]        # what was NOT copied, and therefore what a diff must ignore
licence: MIT
```

**It does not cause a fetch.** The source is already there; this says where it came from, so that
`forge check` (issue #64) can ask *has upstream moved* and answer it with a diff rather than a
guess. A tool with no upstream — a laboratory's own process — declares no `upstream:` block, and
that absence is the honest statement that there is nothing to check it against.

`excluded:` is load-bearing for the size question (§2.3): nf-core ships a `tests/` directory per
module, and a mirror that copies them is carrying test data for tools it is not testing. Excluding
them is a decision that has to be **recorded**, because otherwise a drift check reports every
module as differing from upstream forever.

### 3.4 Licences, concretely

`docs/design/federation.md` §6 already provides for this — *"vendored nf-core modules retain their
own licences and notices"*. **The mechanism is `LICENSES/<spdx>.txt` at the registry root plus an
SPDX identifier in `module.yml`**, which is the REUSE convention. A per-module `NOTICE` was the
first proposal and §8.2 is why it is wrong: at the target corpus it is ~1,600 near-identical
copies of the MIT licence, in every diff, that nobody reads.

The registry's root `LICENSE` stays CC-BY-4.0 and gains one sentence: **it covers the
declarations, and `tools/**/module/` is upstream's under the licence its `NOTICE` names.** That is
the same shape every distribution uses for a vendored tree and it is less confusing than a second
repository, which was the first draft's proposal.

### 3.5 What `keep` copies, unchanged

`services/bundle.py` copies module source next to the emitted artifact so a pipeline runs with no
registry and no network. It copies from the layer instead of from `vendor/`, and **that is the
whole of the change** — one path. `MD0210` is unaffected, and a laboratory receiving a
`pipeline.yml` still needs nothing but the artifact.

### 3.6 How a module gets in

```
mendel registry vendor nf-core:star/align --sha <sha> --registry ../comeni-registry
```

An **impure CLI verb** — it reaches the network, so it cannot live in `comeni-core`,
`mendel-resolver`, `mendel-compiler` or `wiener-core` (invariant 1). It fetches at the pinned SHA,
writes `module/`, `module.yml` and `NOTICE`, and applies `excluded:`. It is the successor to
`uvx nf-core modules install --dir vendor`, and unlike that command it writes a record of what it
did.

**Nothing else in the system fetches.** A build reads a layer on disk, which is what keeps
`make check` offline and an air-gapped site a first-class customer.

## 4. The registry's layout: free for the loader, strict for the curated one

### 4.1 What is confusing, precisely

Invariant 11 says **the layout is free** — every file declares its own kind, the loader globs the
whole layer and buckets by content. That freedom is load-bearing for *overlays*: a laboratory's
private layer must be able to be organised however that laboratory likes.

What it has produced in the **public** registry is four different granularities for five kinds,
and one kind in two places:

```
registry/types/genome.fasta.yml                          a type, in types/
registry/tools/nf-core/star/genome.index.star.type.yml   a type, NOT in types/
registry/roles.yml                                       EVERY role, one file, at the root
registry/measurements/read_length.yml                    one measurement per file
registry/rules/alignment.rule.yml                        one file, several rules
```

A newcomer has no way to infer where their file goes. And `registry.yml`'s own `kinds:` list is,
by its own comment, *"read by nobody"* — a self-description with nothing holding it true.

**A guarantee was traded away for this and it was recorded at the time.** Invariant 11:
*the directory used to make a misfiled document impossible — `contracts/` held contracts, and a
misspelled `contract/` was caught by `MD0003` because nothing read it. That was prevention by
construction, and a misspelled `declares:` can only be detected.* `MD0003` is retired. §4.3 buys
back most of what it did without touching the loader.

### 4.2 The layout

**One rule: a thing a tool owns lives with the tool; everything else lives in one directory per
kind, one file per thing, named for its id.**

```
registry/
  registry.yml                          the layer's manifest — and now read (§4.4)
  LICENSES/<spdx>.txt                 one file per LICENCE, not per module — §8.2
  tools/<org>/<tool>/
      types/<id>.yml                    types the SUBTOOLS share — genome.index.star, §8.1
      <subtool>/                        SELF-ISOLATED — §3.1
          contract.yml                  the binding
          module/                       upstream source, verbatim: main.nf, meta.yml
          module.yml                    provenance: repo, sha, path, excluded, licence
          types/<id>.yml                types only this subtool introduces
          docs.md                       generated by `mendel docs`, never hand-written
  types/<id>.yml                        types no single tool owns — fastq.reads, alignment.bam
  measurements/<id>.yml                 one per file
  roles/<id>.yml                        one per file        ← was one roles.yml
  rules/<id>.yml                        one per file        ← was one file, several rules
```

**Why a tool's files stay together**, when "every type in one place" is the more obviously
intuitive answer: the two questions have two different askers.

- *"I am adding STAR — where do my files go?"* is a **writer's** question, answered by
  one folder.
- *"What types exist?"* is a **reader's** question, and a directory listing is a poor answer to
  it even when it is complete. It is answered by a **generated index** — `mendel docs`, and the
  Tools board — which is already how the registry documents itself.

So the filesystem is optimised for the writer and the index for the reader. `genome.index.star`
is meaningless without STAR and belongs beside it; `fastq.reads` belongs to nobody and lives in
`types/`. The current registry already does this and CLAUDE.md already calls it the convention —
what is missing is that it is *stated* and *checked*, which §4.3 fixes.

### 4.3 The loader stays free. The curated registry holds itself to this, and its CI checks it.

**No change to `comeni_core.layered.stack()` or to invariant 11.** A layer is still a directory
of files that each say what they are, and an overlay is still free-form. What changes is that
`comeni-registry` — one specific layer — adopts a layout and **enforces it in its own CI**, which
is exactly nixpkgs's `by-name` move.

```
mendel registry lint --registry registry/
```

refuses: a file in the wrong directory for its kind, a filename that is not its id, a `roles.yml`
holding more than one role, a type under `tools/` whose id is not namespaced by that tool, a
`module/` with no `module.yml` or no `NOTICE` — and **a relative path crossing out of a tool's own
directory**, which is what makes §3.1's *self-isolated* a checked property rather than a hope. It runs in `comeni-registry`'s CI beside
`mendel docs --check`, which already runs there.

This is prevention-by-construction restored *where it is affordable*: the public registry is one
repository with one set of conventions and a CI that can hold them, and a laboratory's overlay
keeps the freedom invariant 11 grants it.

### 4.4 `registry.yml` gets read

Today its `kinds:` list is pinned by a test and read by nothing — a self-description that can
only rot. It becomes the **input to the lint**: the layer declares which kinds it holds and how
it lays them out, and `mendel registry lint` checks the tree against that declaration. A manifest
that nothing reads is worse than no manifest; a manifest that is the lint's argument cannot drift.

---

## 5. The forge — a known consequence, deliberately not addressed

**Explicit operator instruction, 2026-08-31: the forge is deferred until its own rework, and this
plan does not touch it.** What that means concretely, so nobody discovers it later:

- **`forge discover` reads `vendor/modules/` directly** and will find nothing once it is gone.
  Issue #77 is already open on this (discovery sees 13 tools rather than ~1,600), and the fix is
  the same fix: read the registry's pins, not a directory somebody happened to populate.
- **`forge draft` scaffolds from a vendored `main.nf`/`meta.yml`** and needs the cache.
- **`forge land` writes into the registry** and must write the new layout.
- **`mendel-api`'s `settings.source_root` defaults to `./vendor`**, and `docker-compose.yml`
  bind-mounts it into two services.

**Minimum viable action during this plan:** point `source_root` at the module cache and leave
every forge code path otherwise untouched, so the forge is *no more broken than it is today*
rather than newly broken. The forge already needs a rework; this must not become the reason for
one.

---

## 6. Phases

| Phase | What | Ends with |
|---|---|---|
| **A1** | **`module` as a declared kind, and the vendor verb.** `module.yml`, `NOTICE`, `mendel registry vendor`, and `DeclaredKind` gains a member — so `len(DeclaredKind)` is the count, as invariant 11 insists. Modules copied into a scratch layer; `vendor/` still present and still read. | the registry can hold a module, and nothing depends on it yet |
| **A2** | **The move.** The 13 modules land in `comeni-registry` beside their contracts; conformance, `bundle.py` and `settings.source_root` read the layer; `--vendor` is retired; `docker-compose.yml` loses a mount. A comeni-registry PR plus a submodule bump here. | `mendel build --registry X` with no second root |
| **A3** | **`vendor/` deleted**, including `vendor/conf/`, which nothing reads. `MD0100`'s `fix:` changes from *vendor the module* to naming the layer. | `vendor/` gone, nightly stub gate green |
| **A4** | **The layout.** The tool/subtool split (§8.1), `roles.yml` → `roles/`, rules one per file, contracts renamed to `contract.yml`, `LICENSES/` (§8.2), the generated-file markers (§8.4), the module displacement rule (§8.5), `registry.yml` rewritten as the lint's input, `mendel registry lint`, and comeni-registry's CI running it. | the lint refuses a misfiled file, watched failing |

Then Part B — [`2026-08-31-what-a-pipeline-takes.md`](2026-08-31-what-a-pipeline-takes.md) — lands
`entry_channel` templates and `scope:` **into the new layout**, which is why this half runs first.

---

## 7. What to be suspicious of

- **`make check` will pass while the world is broken.** It has no Nextflow and no Docker, and a
  conformance check that finds no module source reports `MD0100 unverified` — a *diagnostic*,
  not a crash. So a move that silently loses every module is a green suite with every contract
  quietly downgraded. **Run `make verify`**, treat A3's nightly stub gate as the real checkpoint,
  and add the check that has to exist either way: **the count of verified contracts before and
  after the move is the same.**
- **`.gitignore` has swallowed a module before, and this move walks straight into it.** `build/`
  matched `vendor/modules/nf-core/hisat2/build/`, so the module every short-read decision depends
  on was never committed, no test noticed, and the main checkout had the files untracked on disk
  — a worktree is what surfaced it. **`hisat2/build/` moves in this plan**, into a repository with
  its own `.gitignore`. Check `git status --ignored` in `comeni-registry` after A2, and anchor
  every pattern there (`/build/`, not `build/`).
- **A2 lands in two repositories and the order matters.** The registry PR must merge before the
  submodule bump, and until it does `make check` refuses in one sentence naming
  `git submodule update --init` — the honest failure, and a confusing one to hit mid-review.
- **`vendor/` is deleted in A3, not A2.** If something still reads it after the move, that is the
  phase where it shows up, and it shows up as a missing path rather than as silently stale
  content read from a directory nobody is updating any more.
- **The submodule bump is two repositories and one review.** A3's registry change and this
  repository's pin must land together or `make check` refuses in one sentence naming
  `git submodule update --init`, which is the honest failure but a confusing one mid-review.

---

## 8. Attacking this design — a maintainer review

*Run 2026-08-31 at the operator's instruction: "is it easy to navigate, read and maintain?" Six
findings. The first is a layout the spec got wrong and would have shipped.*

### 8.1 The tree in §4.2 has no home for a type two subtools share — corrected here

**What the registry does today**, and the spec did not look before proposing:

```
registry/tools/nf-core/star/align.contract.yml
registry/tools/nf-core/star/genomegenerate.contract.yml
registry/tools/nf-core/star/genome.index.star.type.yml     ← shared by BOTH
```

Contracts sit at the **tool** level, named for the subtool. §4.2 proposed
`tools/<org>/<tool>[/<subtool>]/`, which gives every subtool its own directory — and then
`genome.index.star`, **produced by `genomegenerate` and consumed by `align`**, has nowhere to
live that is not arbitrary. `hisat2` has the identical shape with `genome.index.hisat2`.

Subtool directories are nevertheless **required**, because nf-core's `star/align` and
`star/genomegenerate` are two separate modules and each needs its own `module/`. So the tree has
two levels and the corrected form is:

```
registry/tools/nf-core/star/
    types/genome.index.star.yml       shared by the subtools below — a TOOL-level thing
    align/
        contract.yml
        module/          module.yml        docs.md
    genomegenerate/
        contract.yml
        module/          module.yml        docs.md
```

**The rule, stated so the lint can hold it:** a thing belongs at the shallowest level that owns
it. A module is per-subtool because upstream ships it that way; a type introduced by one subtool
and consumed by another is per-tool. A tool with no subtools has one level and no `types/` unless
it introduces one.

### 8.2 One `NOTICE` per tool is the wrong mechanism at 1,600 tools

§3.4 proposed a `NOTICE` file in every `module/`. At the target corpus that is ~1,600 near-identical
copies of the MIT licence — noise in every diff, and 1,600 files a reviewer has to not read.

**Corrected:** `LICENSES/MIT.txt` once at the registry root, and `module.yml` carries
`licence: MIT` as an SPDX identifier pointing at it. That is the **REUSE** convention, which
exists for exactly this and which tooling already understands. A module under an unusual licence
gets its own file in `LICENSES/` — still once per licence, never once per module.

The root `LICENSE` keeps its one added sentence: the declarations are CC-BY-4.0, and
`tools/**/module/` is upstream's under the identifier its `module.yml` names.

### 8.3 1,600 directories under one parent

`tools/nf-core/` at full corpus is a flat listing nobody can read, and both precedents this spec
cites sharded for that reason — nixpkgs `by-name/<2 chars>/`, Homebrew `Formula/<letter>/`.

**Not sharded now, and the threshold is written down rather than left to feel:** shard when
`tools/<org>/` passes **~300 entries**. The registry has 8. Sharding early buys nothing and costs
every path in every document; sharding late is a mechanical move the lint can perform. What the
design must not do is make sharding *hard*, and it does not: nothing addresses a tool by path —
`ModuleContract.id` is `nf-core/star/align` and the loader globs.

### 8.4 A reviewer cannot tell what is machine-written

A pull request adding a tool contains a `contract.yml` somebody wrote and a `module/` nobody did.
Reviewing the second is a waste and *not* reviewing the first is a curation failure — and there is
nothing in the diff that says which is which.

- `module/` and `docs.md` are **generated**, by `mendel registry vendor` and `mendel docs`.
- `contract.yml`, `module.yml`'s non-generated fields, `types/` and the rules are **written**.

`mendel registry lint` refuses a `module/` whose content does not match its `upstream:` pin, which
makes "do not hand-edit this" enforceable rather than a comment. `CODEOWNERS` and a
`.gitattributes` `linguist-generated` marker do the rest, and both are cheap.

### 8.5 Two layers vendoring the same tool at different SHAs

Invariant 11's displacement is defined for **contracts**, keyed on the module key. It says nothing
about module *source*, which did not exist inside a layer before this spec.

**The rule, and it must be the same rule:** the layer that wins the contract wins the module. A
`Displacement` record already exists for every kind and reports what replaced what; a displaced
module is one more row rather than a new mechanism. Anything else lets a lab's contract run
against the public layer's source, which is the drift `MD0104` exists to catch, reintroduced
between layers instead of between repositories.

### 8.6 Generated `docs.md` in git is a merge-conflict generator

Already true — `mendel docs --check` runs in comeni-registry's CI today. It gets worse per tool
rather than per registry. **Not changed here**, because a generated page in git is what makes the
registry browsable on GitHub without a build step, which is worth the conflicts. Recorded so the
trade is a decision rather than an accident, and the escape is `.gitattributes merge=ours`.

### 8.7 What survives the attack

The shape holds and one thing in it got stronger. **Self-isolation is the property worth having**
— §8.4 and §8.5 both resolve cleanly *because* a tool is a directory, and both would be
open questions under any layout that scattered a tool's files by kind.

**What changes in this spec as a result:** §4.2's tree gains a tool level above the subtool level
(§8.1); §3.4's per-module `NOTICE` becomes `LICENSES/` plus an SPDX identifier (§8.2); phase A4
gains the shard threshold (§8.3), the generated-file markers (§8.4) and the displacement rule
(§8.5).

---

## 9. Attacking it again — the second pass

*Three findings, and the first two are structural rather than cosmetic. Both were invisible from
the design and needed the code.*

### 9.1 The layer digest would not cover `main.nf`

`comeni_core.declared.layered.declared_entries()` is what the **layer digest** and the symlink
refusal both walk, and it is an **allowlist by file extension**:

```python
_DECLARED_SUFFIXES = (".yml", ".yaml")
```

After the move, a tool directory contains:

| file | in the digest? |
|---|---|
| `contract.yml`, `module.yml`, `types/*.yml` | ✓ |
| `module/meta.yml`, `module/environment.yml` | ✓ |
| **`module/main.nf`** | **✗** |

So a `pipeline.yml` pinning a layer digest would pin the module's *metadata* and not its
**executable code**. Change one line of Groovy in a vendored `main.nf` and the layer digest does
not move — while `meta.yml` beside it moves it every time. **Partial coverage is worse than
none**, because the digest looks like it covers the module and a reader has no way to see that it
does not.

This is issue #46's defect in a new place, and its docstring says why the allowlist is by
extension: *"a layer no longer has kind directories to enumerate"*. That premise changes here —
`module/` is a kind directory, declared by the `module.yml` beside it.

**The fix, and it is not "add `.nf` to the suffixes".** A module's contents are whatever upstream
ships — `.nf`, `.py`, `.sh`, `.R`, a `Dockerfile`, a test fixture. The rule that holds is
**everything under a `module/` directory is layer data**, full stop, because that directory's
whole purpose is to be verbatim upstream content. So `_declared` gains one clause: a path with a
`module/` component is declared regardless of extension. `.git` and `LICENSE` at the layer root
stay excluded, unchanged.

**Phase A2 owns this**, and it is watched failing the same way: change a byte in a vendored
`main.nf`, and the layer digest must move.

### 9.2 `mendel registry vendor` cannot live where §3.6 put it

`mendel` is `mendel_compiler.cli:main` — **`mendel-compiler` is one of the four pure packages.**
A subcommand that fetches from GitHub puts a network client in a package `tests/test_purity.py`
rejects statically and `tests/test_purity_runtime.py` catches at runtime. Invariant 1 is not
negotiable and §3.6 wrote a verb that violates it.

Three ways out, and the third is the one:

- **Put it in `mendel-forge`.** It is already impure and already the offline-authoring half of
  invariant 2 — vendoring a module is exactly that. But the forge is **deferred by the operator's
  decision** and this plan must not require touching it.
- **Make it a `make` target over `nf-core modules install`.** Cheapest, and it gives up
  `module.yml`, `excluded:` and the licence identifier — the whole reason for the verb.
- **A new impure package, `mendel-vendor`, with its own console script.** One job: fetch at a
  pinned SHA, write `module/`, `module.yml` and the SPDX id. It joins `IMPURE_PACKAGES`, and
  `test_no_pure_package_imports_an_impure_one` holds the arrow the same way it does for
  `mendel-ai` and `mendel-forge`. The command is `comeni-vendor …` rather than `mendel …`,
  which is honest: it is not part of the deterministic build path and should not appear to be.

**Phase A1 owns this**, and the phase's own check is that `make check` stays green — which it
only does if the fetch is genuinely outside the four.

### 9.3 One `module/` per directory cannot hold two contract versions

Invariant 11 is explicit that a version bump is not ambiguity: a higher layer pinning
`@1.22.0` over `@1.21.0` displaces on the **module key**, the id minus `@version`. That is
between layers. **Within one layer, two versions of a contract are two ordinary candidates** —
routing ranks them by `(surplus, -priority, id)` and nothing forbids it.

`tools/nf-core/star/align/` has one `module/`. Two contract versions usually need two module
SHAs, and there is nowhere to put the second.

**Not solved here, and bounded rather than ignored:** the public registry ships one version per
tool today and `mendel registry lint` **refuses a second**, naming this section. A layer that
genuinely needs two gets `align@1.11.0/` and `align@1.12.0/` directories — a mechanical change
the lint can perform later, and one that must not be *designed around* now on the strength of a
case nobody has.

---

## 10. Attacking it a third time — the threat model

*One finding, on an axis neither earlier pass touched, and it is the one thing in this plan that
changes what installing a registry MEANS.*

### 10.1 The registry becomes executable code, and no document says so

**Today `--registry X` means *parse this person's YAML*. After this plan it means *execute this
person's Groovy*.**

A layer is currently inert: contracts, types, rules and measurements are data that a loader
parses, and the worst a hostile layer can do is misroute a pipeline — bad, visible in
`pipeline.yml`, and bounded by invariant 7's closed vocabularies. After the move a layer carries
`module/main.nf`, which Nextflow **runs**, plus `environment.yml` naming conda packages and a
`container:` naming an image that gets pulled.

`docs/design/federation.md` §3 designs exactly the case this matters for: *"the registry is a
stack — public curated base, then private overlays via repeated `--registry`"*, and
*"contributing upstream is a proposal into the forge queue"*. **Installing a third-party overlay
becomes installing third-party code**, and nothing in the design or the CLI marks the moment.

**This is not a reason to reverse the decision.** It is precisely nf-core's property — `nf-core
modules install` puts somebody else's Groovy in your pipeline and everyone accepts it, because a
pipeline is code and pretending otherwise helps nobody. Three things change, though:

- **Signed tags stop being a nicety.** Federation §3.4 already specifies *"tag signature plus a
  content digest recorded in the lockfile"*, and today that verifies **data**. It is now the only
  thing standing between an overlay and arbitrary execution, which makes implementing it a
  prerequisite for publishing overlays rather than a later refinement.
- **The layer digest must cover the code**, which is §9.1's finding arriving from a second
  direction. A digest that pins metadata and not `main.nf` is not a supply-chain control at all.
- **It must be *said*.** `docs/design/federation.md` §6 gains a paragraph, and `mendel build`'s
  first use of an unpinned layer is where a person should be told. **What this spec will not do is
  invent a sandbox**: Nextflow runs containers, the trust boundary is the container runtime, and a
  half-measure that looked like isolation would be worse than a sentence that tells the truth.

**Phase A4 owns the sentence** — beside the lint, which is where a reader of the registry's own
rules will be. The signing work is federation's, not this plan's, and this section is what
promotes it from *designed* to *blocking for overlays*.

### 10.2 A note, so nobody unifies two digests that should disagree

`wiener_api.services.artifacts` computes an artifact's identity from `Pipeline.content_digest()`
and says why, explicitly: *"not the tree digest … it covers the whole uploaded directory including
the vendored `modules/` tree — so re-vendoring a module makes the same pipeline look like a
different one."*

That is **the opposite of §9.1's conclusion for the layer digest**, and both are right because
they answer different questions: *is this the same pipeline document* versus *is this the same
layer*. Written down here because the two will look like an inconsistency to whoever reads them
next, and "fixing" either one breaks something real.
