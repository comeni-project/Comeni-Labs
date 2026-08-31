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

`vendor/` being in the code repository is wrong: nobody here maintains it, it is not code, and
the only thing that ever writes to it is `uvx nf-core modules install`. But it does **not** follow
that it belongs *inside* the registry, and §3 is why.

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

### 1.2 `vendor/conf/` is read by nothing at all

Eight nf-core container-config files, and **no code path opens any of them.** The label→resource
mappings that Mendel emits are *transcribed* into `emit.py` as a quoted convention — its own
docstring says so: *"nf-core's `conf/base.config`, quoted rather than a judgement invented"*. So
`vendor/conf/` is 8 files of dead weight, and this spec deletes it rather than moving it. If a
later change wants to read those mappings rather than quote them, it fetches them the same way
§3 fetches everything else.

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
emitted pipeline is the artifact.** So the pattern that fits is *the registry declares, the
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

## 3. Where the modules go: the pin moves in, the bytes move out

**`registry/` declares which module a contract binds, by immutable revision. Nothing keeps a
checked-in copy. `mendel vendor sync` materialises them into a cache.**

```yaml
# registry/tools/nf-core/star/align/module.yml
declares: module
id: nf-core/star/align
repo: https://github.com/nf-core/modules.git
sha: 6d46786420b4d7bc88eba026eb389c0c5535d120     # immutable, never a branch
path: modules/nf-core/star/align
```

### 3.1 Why the pin belongs in the registry and not beside the code

**A contract and its module are checked against each other.** `MD0104` refuses a build where they
disagree, which means they are *version-locked* whether or not anything says so. Today the
contract's version lives in a registry tag and the module's SHA lives in `vendor/modules.json` in
a different repository, so those two can drift and nothing notices until a build fails.

Putting the pin in the same commit as the contract makes **"this registry layer is internally
consistent"** a property of one revision. That is the same reason `modules.json` sits next to the
pipeline that uses it, and it is a correctness argument rather than a tidiness one.

### 3.2 Why the bytes do not

Three reasons, in order of weight:

- **Licences.** `docs/design/federation.md` §6 already warns that *"one repository with two
  licences invites exactly the confusion the licence files exist to prevent"*, which is why the
  registry left this repository in the first place (issue #46). Registry data is CC-BY-4.0;
  nf-core modules are MIT. Putting MIT source inside a CC-BY-4.0 repository recreates the problem
  that split was for.
- **Size.** 13 modules is 788 KB. The registry's target corpus is nf-core plus pegi3s, on the
  order of 1,600 tools — call it 100 MB of somebody else's source in a repository whose stated
  virtue is that *"pulling the registry should not mean cloning a Python workspace"*.
- **Authority.** A mirror has to be kept in step with upstream forever, and a stale mirror is
  indistinguishable from a deliberate pin. A SHA is not.

### 3.3 The fetch, and invariant 1

**`mendel vendor sync` is a CLI verb in an impure package.** `comeni-core`, `mendel-resolver`,
`mendel-compiler` and `wiener-core` do not reach the network — the fetch cannot live in any of
them, and this is the same shape as `uvx nf-core modules install`: an explicit command a person
or a CI job runs, never something a build does behind your back.

```
mendel vendor sync --registry registry/       # fetch every pinned module
mendel vendor sync --check                    # is the cache complete? exit 1 if not
```

Cache location: `${XDG_CACHE_HOME:-~/.cache}/comeni/modules/<sha>/<path>`, keyed by **SHA**, so
two registry layers pinning the same module share one copy and a re-pin is additive rather than
destructive. Overridable by `MENDEL_MODULE_CACHE` for an air-gapped site.

### 3.4 What breaks, and what does not

- **Building a pipeline** needs the cache, so it needs one `sync` on a new machine.
- **Running an emitted pipeline** needs nothing: the artifact already carries its modules
  (`services/bundle.py`, `MD0210`). A laboratory that receives a `pipeline.yml` and runs it never
  syncs anything, which is the case that matters most and the one this must not regress.
- **CI has no network in the `make check` lane.** `mendel vendor sync` is a *setup* step, cached
  on the registry digest — the same shape as `uv sync`. `make check` itself stays offline.
- **`MD0104`'s message changes.** *"vendor the module"* becomes *"run `mendel vendor sync`"*, and
  a **missing cache must be distinguishable from a mismatched module** — one is a setup problem
  and the other is a real conformance failure. A new code rather than an overloaded one.

### 3.5 Air-gapped sites, said explicitly

`mendel vendor sync --from <tarball>` and a matching `--to`, because a site that cannot reach
GitHub is a normal customer here, not an edge case. **Self-hosted is not a degraded tier**
(invariant 13), and a design whose only path runs through github.com would make it one.

---

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
  tools/<org>/<tool>[/<subtool>]/
      contract.yml                      the contract
      module.yml                        the pin (§3)
      types/<id>.yml                    types this tool introduces — genome.index.star
      docs.md                           generated by `mendel docs`, never hand-written
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
holding more than one role, a tool directory with a contract and no module pin, a type under
`tools/` whose id is not namespaced by that tool. It runs in `comeni-registry`'s CI beside
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
| **A1** | **`module.yml` and the sync.** The pin as a declared kind, `mendel vendor sync` / `--check` / `--from`, the cache, conformance reading the cache, the new diagnostic for *cache missing* versus *module disagrees*. `vendor/` still present and unread. | `make verify` green with `vendor/` renamed away |
| **A2** | **`vendor/` deleted.** Including `vendor/conf/`, which nothing reads. CI gains a sync step; `docker-compose.yml` and `settings.source_root` point at the cache; `MD0104`'s `fix:` changes. | `vendor/` gone, nightly stub gate green |
| **A3** | **The layout.** `roles.yml` → `roles/`, rules one per file, contracts renamed to `contract.yml`, `registry.yml` rewritten as the lint's input, `mendel registry lint`, and comeni-registry's CI running it. A comeni-registry PR plus a submodule bump here. | the lint refuses a misfiled file, watched failing |

Then Part B — [`2026-08-31-what-a-pipeline-takes.md`](2026-08-31-what-a-pipeline-takes.md) — lands
`entry_channel` templates and `scope:` **into the new layout**, which is why this half runs first.

---

## 7. What to be suspicious of

- **`make check` will pass while the world is broken.** It has no Nextflow and no Docker; the
  conformance check reading an empty cache is exactly the kind of thing that goes green in CI and
  red on a developer's machine, which is the inverse of the trap `CLAUDE.md` documents. **Run
  `make verify`**, and treat A2's nightly stub gate as the real checkpoint.
- **`.gitignore` has swallowed a module before.** `build/` matched
  `vendor/modules/nf-core/hisat2/build/`, so the module every short-read decision depends on was
  never committed and no test noticed. A gitignored cache is the same hazard wearing a different
  hat: `--check` must fail loudly on an incomplete cache rather than a build failing obscurely
  three steps later.
- **A rename is not a migration.** A1 renaming `vendor/` rather than deleting it is deliberate:
  if something still reads it, that is the phase where it shows up, and it shows up as a missing
  path rather than as silently stale content.
- **The submodule bump is two repositories and one review.** A3's registry change and this
  repository's pin must land together or `make check` refuses in one sentence naming
  `git submodule update --init`, which is the honest failure but a confusing one mid-review.
