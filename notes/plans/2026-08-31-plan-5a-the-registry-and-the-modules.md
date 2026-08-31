# Plan 5, Part A — the registry, and where the modules live

**Spec:** [`../specs/2026-08-31-the-registry-and-the-modules.md`](../specs/2026-08-31-the-registry-and-the-modules.md).
Read it first. Every task below cites the section it implements, and the § numbers in the *why*
column are that spec's unless prefixed.

**Runs before Part B**, which is
[`2026-08-31-plan-5b-what-a-pipeline-takes.md`](2026-08-31-plan-5b-what-a-pipeline-takes.md).
Both edit `registry/`; the other order edits the same files twice.

**Two repositories.** `registry/` is a submodule of `comeni-registry` at `v0.4.0-2-ga677753`.
A2 and A4 are a pull request there plus a submodule bump here, **and the registry PR merges
first** — until it does, `make check` refuses in one sentence naming `git submodule update --init`.

**The forge is deferred** by the operator's decision of 2026-08-31. Spec §5 lists what a registry
change does to it. The rule for this plan: leave every forge code path alone and point
`source_root` at the layer, so the forge is *no more broken than it is today* rather than newly
broken.

**`make check` is not verification for any of this.** Every phase touches `emit.py`,
`pipeline.py` or the loader — the six files `CLAUDE.md` names. Run **`make verify`**.

---

## Phase A1 — `module` becomes a declared kind, and a tool that can fetch one

*Nothing depends on it yet. `vendor/` is still present and still read, so this phase cannot break
a build.*

### A1.1 The kind

- [x] `DeclaredKind` gains `MODULE`. **The count lives in `len(DeclaredKind)`** and nowhere in
      prose — invariant 11, and A33's lesson about a number repeated in a sentence.
- [x] `Module` in `comeni_core.declared`: `id`, `upstream: {repo, sha, path} | None`, `excluded:
      list[str]`, `licence: SpdxId`. It parses, keys and merges through `stack()` like every other
      kind — **not a hand-written loader**, which is what audit root B was.
- [x] `upstream: None` is legal and means **a tool nobody vendored** — a laboratory's own process.
      The absence is the honest statement that there is nothing to check it against (§3.3).
- [x] `excluded:` records what was **not** copied. Without it a drift check reports every module as
      differing from upstream forever, because nf-core ships a `tests/` directory we do not take.

### A1.2 The layer digest has to cover the code — spec §9.1

- [x] `comeni_core.declared.layered._declared()` gains one clause: **a path with a `module/`
      component is layer data regardless of extension.**
- [x] **Not** by adding `.nf` to `_DECLARED_SUFFIXES`. A module carries whatever upstream ships —
      `.nf`, `.py`, `.sh`, `.R`, a Dockerfile — and an extension allowlist would cover today's
      corpus and silently miss the next one.
- [x] `.git`, `LICENSE` and `README.md` at the layer root stay excluded, unchanged. Issue #46's
      machine-dependent-digest defect must not come back through this door.
- [x] **Watched failing**: change one byte of a vendored `main.nf` and assert the layer digest
      moves. Reverted, it must not — a digest that pins `meta.yml` and not `main.nf` is the
      partial coverage §9.1 calls worse than none.

### A1.3 The vendor tool, and why it is not `mendel` — spec §9.2

- [x] **New impure package `comeni-vendor`**, console script `comeni-vendor`. `mendel` is
      `mendel_compiler.cli:main` and **`mendel-compiler` is pure**; a subcommand that fetches from
      GitHub is a network client in a package `tests/test_purity.py` rejects.
- [x] It joins `IMPURE_PACKAGES`, and `test_no_pure_package_imports_an_impure_one` holds the arrow
      the way it already does for `mendel-ai` and `mendel-forge`.
- [x] The name is `comeni-vendor` rather than `mendel vendor` **on purpose**: it is not part of the
      deterministic build path and must not appear to be.
- [x] `comeni-vendor add nf-core:star/align --sha <sha> --registry ../comeni-registry` fetches at
      the pin, writes `module/`, `module.yml` and the SPDX id, and applies `excluded:`.
- [x] `comeni-vendor check --registry X` — does every `module/` match its `upstream:` pin? Exit 1
      if not. This is what makes *do not hand-edit this* enforceable rather than a comment (§8.4).
- [x] **Nothing else fetches.** A build reads a layer on disk, which is what keeps `make check`
      offline and an air-gapped site a first-class customer (invariant 13).

### A1.4 Licences — spec §8.2

- [x] `LICENSES/<spdx>.txt` at the registry root, **one file per licence, never one per module**.
      A `NOTICE` per tool was the first proposal and at 1,600 tools it is that many near-identical
      copies of the MIT text, in every diff, that nobody reads.
- [x] `module.yml` carries `licence: MIT` as an SPDX identifier pointing at it — the **REUSE**
      convention, which tooling already understands.

### A1.5 Checkpoint

- [x] `make verify` green. `make check` **still green**, which it only is if the fetch genuinely
      lives outside the four pure packages — that is A1.3's real test.
- [x] A module can be vendored into a scratch layer and nothing in the build path reads it yet.

---

## Phase A2 — the move

*The 13 modules land beside their contracts. This is the phase that can break a build, and the
check is a count.*

### A2.1 The registry side — a `comeni-registry` pull request

- [x] The tool/subtool layout, **spec §8.1**, which the spec got wrong and this corrects:

      ```
      tools/nf-core/star/
          types/genome.index.star.yml       shared by the subtools — TOOL level
          align/
              contract.yml  module/  module.yml  docs.md
          genomegenerate/
              contract.yml  module/  module.yml  docs.md
      ```

      Subtool directories are **required** because nf-core ships `star/align` and
      `star/genomegenerate` as separate modules, each needing its own `module/`. `genome.index.star`
      is produced by one and consumed by the other, so it sits at the tool level. `hisat2` has the
      identical shape.
- [x] **The rule, stated so A4's lint can hold it:** a thing belongs at the **shallowest level that
      owns it**.
- [x] All 13 modules vendored with `comeni-vendor add`, at the SHAs `vendor/modules.json` holds
      today — so the move is a relocation and not a version bump. **One thing at a time.**
- [x] `LICENSES/MIT.txt` and the root `LICENSE` gaining its one sentence: the declarations are
      CC-BY-4.0, and `tools/**/module/` is upstream's under the identifier its `module.yml` names.

### A2.2 The code side

- [x] Conformance reads the **layer**, not a separate root.
- [x] `services/bundle.py` copies module source from the layer. **One path changes** and `MD0210`
      is unaffected — a laboratory receiving a `pipeline.yml` still needs nothing but the artifact.
- [x] `settings.source_root` retired; `docker-compose.yml` loses a bind mount from two services.
- [x] `--vendor` retired from the CLI. **One root**: `mendel build --registry X`.
- [x] The forge's `source_root` points at the layer and **no forge code path is otherwise
      touched** (spec §5).

### A2.3 The checks that matter here — spec §7

- [x] **The count of verified contracts before and after the move is the same.** A conformance
      check that finds no module source reports `MD0100 unverified` — a *diagnostic*, not a crash
      — so a move that silently loses every module is a **green suite with every contract quietly
      downgraded**. This is the single most important assertion in Part A.
- [x] **`git status --ignored` in `comeni-registry` after the move.** `build/` in `.gitignore`
      swallowed `vendor/modules/nf-core/hisat2/build/` once already: the module every short-read
      decision depends on was never committed, no test noticed, and only a worktree surfaced it.
      **`hisat2/build/` moves in this phase.** Anchor every pattern (`/build/`, not `build/`).
- [x] The registry PR merges **before** the submodule bump.
- [x] `make verify` green, and the nightly stub gate green.

---

## Phase A3 — `vendor/` deleted

*Separate from A2 on purpose: if something still reads it, that shows up here as a missing path
rather than as silently stale content read from a directory nobody updates any more.*

- [ ] `vendor/` deleted, **including `vendor/conf/`** — eight nf-core container-config files and
      **no code path opens any of them** (§1.2). The label→resource mappings Mendel emits are
      transcribed into `emit.py` as a quoted convention.
- [ ] `vendor/modules.json` goes with it. Its pins now live in `module.yml`, where our own code
      reads them — they were written by `nf-core modules install` and read by nothing we own.
- [ ] `MD0100`'s `fix:` changes from *"vendor the module"* to naming the layer and
      `comeni-vendor add`.
- [ ] `Makefile`, `docker-compose.yml`, `.github/workflows/` and `CLAUDE.md`'s vendoring line all
      stop mentioning `vendor/`.
- [ ] **Nightly stub gate is the real checkpoint.** `make check` has no Nextflow and no Docker.

---

## Phase A4 — the layout, the lint, and the sentence about trust

### A4.1 The remaining layout fixes

- [ ] `roles.yml` → `roles/<id>.yml`, one per file. It held **every** role in one file at the
      layer root — one of the four different granularities §4.1 counts.
- [ ] `rules/` one rule per file, named for its id.
- [ ] Contracts renamed to `contract.yml` inside the subtool directory.
- [ ] `registry.yml` rewritten as **the lint's input** (§4.4). Its `kinds:` list is *"read by
      nobody"* by its own comment today — a self-description that can only rot. A manifest that is
      the lint's argument cannot drift.

### A4.2 `mendel registry lint`

*The loader stays free — invariant 11 is unchanged and an overlay keeps its freedom. The curated
registry holds itself to a layout **its own CI** enforces, which is nixpkgs's `pkgs/by-name` move.*

- [ ] Refuses: a file in the wrong directory for its kind; a filename that is not its id; a
      `roles.yml` holding more than one role; a type under `tools/` whose id is not namespaced by
      that tool; a `module/` with no `module.yml`.
- [ ] Refuses **a relative path crossing out of a tool's own directory** — this is what makes
      §3.1's *self-isolated* a checked property rather than a hope.
- [ ] Refuses **a second contract version in one layer** (§9.3), naming that section. One
      `module/` per directory cannot hold two SHAs, and the case is bounded rather than designed
      around on the strength of a need nobody has.
- [ ] Runs in `comeni-registry`'s CI beside `mendel docs --check`, which already runs there.
- [ ] **Watched failing** — misfile a document and see the message.

### A4.3 What a reviewer may skip — spec §8.4

- [ ] `.gitattributes` marks `module/**` and `docs.md` `linguist-generated`.
- [ ] `CODEOWNERS` so a contract gets review and a vendored `main.nf` does not.
- [ ] `comeni-vendor check` in CI, so *"do not hand-edit this"* is enforced rather than asked.

### A4.4 Module displacement — spec §8.5

- [ ] **The layer that wins the contract wins the module.** Invariant 11's displacement is defined
      for contracts on the module key; module source did not exist inside a layer before this plan.
- [ ] A displaced module is one more `Displacement` row, **not a new mechanism**. Anything else
      lets a laboratory's contract run against the public layer's source — the drift `MD0104`
      exists to catch, reintroduced between layers instead of between repositories.

### A4.5 The threat model, said out loud — spec §10.1

- [ ] `docs/design/federation.md` §6 gains a paragraph: **`--registry X` used to mean *parse this
      person's YAML* and now means *execute this person's Groovy*.** A layer carries `main.nf`,
      which Nextflow runs.
- [ ] It is **not a reason to reverse the decision** — it is exactly nf-core's property, and a
      pipeline is code. What changes is that **signed tags stop being a nicety**: federation §3.4
      already specifies tag signature plus a content digest, and that verification is now the only
      thing between a third-party overlay and arbitrary execution. It becomes a **prerequisite for
      publishing overlays** rather than a later refinement.
- [ ] **No sandbox is invented.** Nextflow runs containers; the trust boundary is the container
      runtime, and a half-measure that looked like isolation would be worse than a sentence that
      tells the truth.
- [ ] `comeni-registry`'s `CONTRIBUTING.md` says the same thing where a contributor will see it.

### A4.6 Two things recorded rather than fixed

- [ ] **The shard threshold** (§8.3): shard `tools/<org>/` at ~300 entries. It has 8. Nothing
      addresses a tool by path — `ModuleContract.id` is `nf-core/star/align` and the loader globs —
      so sharding stays a mechanical move the lint can perform later.
- [ ] **Two digests that should disagree** (§10.2): `wiener_api.services.artifacts` identifies an
      artifact by `Pipeline.content_digest()` and says explicitly that it is *not* the tree digest,
      because re-vendoring a module would make the same pipeline look like a different one. That is
      the **opposite** of A1.2's conclusion for the layer digest, and both are right — *is this the
      same pipeline document* versus *is this the same layer*. Written into both files so nobody
      "fixes" either into the other.

---

## Execution record

| Phase | Carried out as written? | Deviation |
|---|---|---|
| A1 | Yes, with three additions | **The kind is loaded, not merely declared.** `layers.load` stacks `Module.kind()` into `Layers.modules`, read by nothing — otherwise a `module.yml` in a layer is bucketed and then dropped, and A4.4's displacement would need a second mechanism later. Nothing in the build path consumes it. **`_in_module` is checked *before* the dot rule**, which running `comeni-vendor add` found: nf-core ships `.conda-lock/` inside a module and it pins which build of the tool runs, so the dot rule written for `.git` at a layer root would have left the digest blind to it. **`check` is offline by default** — it compares each `module/` against the digest `module.yml` records, which is the hand-edit question and needs no network, so it can run in CI; `--upstream` re-fetches and is the other question. A1.4's `LICENSES/` files land with the modules in A2; what A1 adds is the refusal — `add` will not vendor under a licence the layer carries no text for, checked *before* the fetch |
| A2 | Yes, plus three things the plan did not name | **A contract's module source is not derivable from a root**, and the plan reads as five bullets because it did not notice. `conformance.module_path` computed `module_root / f"{nf_include}.nf"`; with the source *in* the layer there is no root to compute against, so it became a lookup by module key — `key_of`, one derivation from `nf_include`, rather than a second field a lint would have to check agreed with the first. That changed `check`, `_meta_keys`, `orchestrate.build`, `diagnostics_for`, the API and three forge sites, and **154 tests** with them. Reported to the operator with the number and three options before sweeping; they chose the sweep. **`mendel_compiler.staging` is new**: both `mendel build` and the API's `keep` wrote `out/modules/` with their own `copytree` — the shape `MD0210` already found a bug in — and it now copies what the pipeline *includes*, five modules for the spine where the sweep shipped all thirteen. **`mendel conformance` is new**, and it is A2's payoff: the registry's CI could not ask whether its own contracts agree with their own modules, and its `CONTRIBUTING.md` said so. Contracts moved to `contract.yml` in A2 rather than A4 — A2.1's own diagram shows it, and leaving `align.contract.yml` beside `align/module/` for a phase is a state nobody should review |
| — | **The stated order was impossible** | A2.1 says the registry PR merges first. It cannot: the layer will not load under an engine that has never heard of the `module` kind, and the engine's suite will not pass against a layer with no modules in it. `ENGINE_REF` in the registry's CI is what breaks the cycle — it pins a Comeni-Labs *commit*, which only has to exist on a pushed branch. Sequence that works: push the engine branch, bump `ENGINE_REF`, merge the registry PR, bump the submodule |
| A3 | | |
| A4 | | |
