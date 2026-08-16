# Registry CI, and documentation generated from the registry

> **Precedence:** this spec takes precedence over the code where they disagree, until the work
> lands. After that, the code is right and this is the argument for it.

**Issue:** [comeni-registry#2](https://github.com/comeni-project/comeni-registry/issues/2) —
*"this repo needs github actions setup, and a system that auto docs each 'tool' from the registry
files themselves."*

Two deliverables in two repositories. The engine gains a verb that documents a layer; the
registry gains the workflows that call it and the pages it produces.

## 1. The problem, stated as it actually is

`comeni-registry` has **no `.github/` at all**. Nothing validates a contract before it merges,
and the only thing that has ever loaded the layer is `Comeni-Labs`' test suite — against a
submodule pointer, which is to say *after* the registry commit already exists.

That is the sharper half of the complaint. A registry PR today can merge a contract that does not
load, and the failure surfaces in a different repository, in somebody else's pull request, as a
submodule bump that will not go green.

The documentation half is the softer one but has the same root: a contract is a dense YAML
document, and the only way to read what a tool offers is to open the file.

**The constraint that shapes everything below:** all validation logic lives in `Comeni-Labs`
(`comeni_core`, `mendel_resolver`), and the registry has no Python. Any answer either depends on
the engine or duplicates it.

## 2. What was verified before designing, because it decided the design

**A registry CI job needs no `Comeni-Labs` checkout.** Installing `mendel-resolver` from git into
a clean virtualenv with a *cold* cache resolves `comeni-core` from the same repository — uv reads
the workspace root out of the git checkout and honours `[tool.uv.sources]`. A bare clone of
`comeni-registry` then loads: 12 contracts, 22 types, 12 measurements.

This was worth checking rather than assuming. `comeni-core` is not on PyPI and never will be
(decided 2026-08-16), and `mendel-resolver` declares a bare `comeni-core>=0.1.0` with no source —
so the obvious prediction is that the install fails outside the workspace. It does not. Had it
failed, this spec would be proposing a vendored validator or a reverse-direction workflow, and
both are worse.

**There are no tags and no releases.** Every package is `0.1.0` and the release machinery has
never been fired. So "pin a released engine" has nothing to pin. §6 is what follows from that.

## 3. `mendel docs` — a verb that documents a layer

```
mendel docs <layer> [--out DIR] [--check]
```

Writes one Markdown page per tool. `--check` writes nothing and exits non-zero if what is on disk
disagrees with what the data says, which is the shape `make docs` already uses for
`diagnostics.md`.

**Why a verb and not a script in `tools/`.** `tools/generate_diagnostics_doc.py` is the obvious
precedent and it is the wrong one here, for one reason: a script in `Comeni-Labs/tools/` can only
be run by something that has checked out `Comeni-Labs`. Shipping it inside `mendel-compiler`
means the registry installs the engine — which §2 proved it can — and runs one command.

The benefit is larger than the convenience. **A laboratory can document its own private overlay
with the same command**, which turns a registry chore into a product feature. Nothing about the
verb is specific to the public registry; it takes a layer, and a layer is a layer.

**Where it lives in `cli/`.** Issue #41 split the CLI by *what a verb does to a pipeline* —
`resolve_verbs` produces one, `artifact_verbs` acts on one that exists, `report` prints, `parse`
reads arguments. `docs` does nothing to a pipeline: it acts on a **layer**, and there is no
pipeline anywhere in its execution. That is a new category and it gets its own module rather than
being wedged into `report` because both happen to write text. Wedging it in is how `cli.py`
became the thing #41 had to split.

### 3.1 What counts as a tool

**The first two segments of the module key** — the contract `id` with `@version` removed.

The obvious alternative is the directory, and it is wrong. comeni-registry#1 removed the
directory's meaning on purpose: a file declares what it is and the loader never reads its path.
Grouping documentation by folder would put path-as-meaning straight back in, one layer up, in the
first thing built after that issue closed.

It also disagrees with the data today. `tools/comeni/` holds two contracts whose ids both say
`comeni/profile`, so the folder says one thing and the id says another, and the id is what
shadowing already keys on.

The rule was checked against the whole registry rather than reasoned about, because the ids are
**not uniformly shaped** — `nf-core/star/align` has three segments and `nf-core/fastqc` has two,
and a rule of "drop the last segment" turns the second into `nf-core`. Taking the first two
segments handles both, and produces eight pages:

| Page | Contracts |
|---|---|
| `comeni/profile` | collect, fastqc |
| `nf-core/fastqc` | fastqc |
| `nf-core/hisat2` | align, build |
| `nf-core/multiqc` | multiqc |
| `nf-core/samtools` | index, sort |
| `nf-core/star` | align, genomegenerate |
| `nf-core/subread` | featurecounts |
| `nf-core/trimgalore` | trimgalore |

**A module key with fewer than two segments becomes its own page**, named for itself. No
contract has one today, and the first draft of this spec made it a refusal with a new diagnostic
code — which is inventing a rule for a case that does not exist and may be legitimate, since a
laboratory's in-house `sortmerna@4.3.6` is not obviously wrong. Taking the whole key when there is
no second segment costs one line and forbids nothing.

### 3.2 What a page holds

Only what the data says, because a generated page that contains prose nobody can trace is worse
than no page. Per contract: id and version, roles, `nf_process` and `nf_include`, `consumes` and
`produces` with their required and produced states, `params` with tier hints and their `via:`
routes, `container`, and `provenance` with its citation.

Two cross-references the layer can answer and a single file cannot:

- **types the tool declares** — `genome.index.star` is declared beside `star/align` and appears
  nowhere else, which is precisely the fact the old layout hid.
- **rules that name it** — a contract pinned by a tier-3 `implementation` effect is a contract
  whose selection is not free, and a reader deciding whether to use a tool should be told.

**No hand-written sections, and no markers.** Issue #41 found that a generator splicing into a
partly hand-edited page compares the hand-written half against itself and can never see an edit.
The whole page is generated; `--check` refuses any local change.

## 4. What CI gates, and what it deliberately does not

**Gated:**

1. **The layer loads** — `layers.load()` over the repository root. That is every `MD0001`–`MD0012`
   refusal, vocabulary closure (invariant 7), rule validation against the parameters contracts
   actually declare, and role coverage.
2. **The pages match the data** — `mendel docs . --check`.

**Not gated, and the workflow says so in a comment rather than leaving it to be discovered:**
**conformance against module source.** `MD0104`, `MD0105` and container drift compare a contract
against the vendored `main.nf` and `meta.yml`, and the registry has no `vendor/` — nor should it,
since vendoring nf-core modules into a data repository would be the copy that comeni-registry#1
and issue #46 both exist to remove. Conformance stays where the modules are, in `Comeni-Labs`, and
runs when the submodule pointer is bumped.

This is a real gap and naming it is the honest move. A contract can merge into the registry
declaring an `nf_process` no module defines, and only the engine PR will catch it.

## 5. Two workflows, and why not one

**`ci.yml`** — on pull request and push. Installs the engine at a pinned commit and runs the two
gates in §4.

**`compat.yml`** — scheduled, weekly. The same gates against engine `main`. On failure it opens or
updates a single tracking issue; it does **not** block anything.

The split exists so that **a data contributor is never blocked by somebody else's engine commit.**
A registry PR adding a citation should not go red because `mendel-resolver` changed that morning,
and a contributor who is here to fix a DOI cannot act on that failure.

**This is not the drift subsystem returning.** `make drift` compared two *copies* of the same
data and was deleted because there is one copy now, so drift is impossible rather than detected.
Engine/registry *compatibility* is a different question about two independently versioned things,
and nothing has ever checked it. Recorded here because the shapes rhyme and somebody will
reasonably ask.

**`compat.yml` must not skip when it cannot run.** `make drift`'s default resolved to a directory
that did not exist and printed *"skipped"*, so Plan 1.15 Task 0 edited twelve contracts under a
green gate. A job whose input is missing fails.

## 6. Pinning the engine

**By commit SHA, with the version in a trailing comment** — the convention this repository already
applies to every GitHub Action, adopted for the same reason: a mutable ref can be repointed by
whoever controls the other end.

```yaml
# Comeni-Labs @ mendel-compiler 0.1.0
ENGINE_REF: 33cb6535c6ce24960ba95d5151d06da9ff0518de
```

**Why not cut a release first.** `docs/guides/releasing.md` says the version bump is judged rather
than derived — it is a claim about what changed in the code. Cutting `0.2.0` to unblock a
workflow decides that number for a reason that has nothing to do with the code, and the number
then means nothing. When a release is cut for its own reasons the pin becomes a tag, and that is a
one-line change.

**The pin bump is the registry's decision**, made in a registry PR, where the pages regenerate in
the same commit and any change to them is reviewable. That is the mechanism that makes a generated
page worth committing at all.

## 7. Order, and the cost this makes real

The engine PR must merge before the registry workflow can call the verb — the two-repository cost
`docs/guides/contributing.md` already states to a contributor's face:

> a change touching both the engine and the registry is **two pull requests**, and the engine one
> cannot merge until the registry one does and the pointer is bumped.

This is the first change to pay it in the *other* direction — the registry waiting on the engine
rather than the engine on the registry — and it is worth noting that the documented sentence only
describes one of the two directions.

## 8. What this does not do

- **No GitHub Pages.** Committed Markdown is the deliverable. Rendering it is additive and needs
  no part of this design changed.
- **No index page beyond a list.** A tool catalogue with search is `mendel-api`'s job (Plan 3),
  and building a static half of it now is the surface area issue #11 argues against.
- **No docs for rules, measurements or types as such.** They appear as cross-references on the
  page of the tool they concern. A separate page per type is worth doing when a type has more
  than one producer, which none does yet.
- **No Dependabot for the engine pin.** Dependabot does not understand a bare `ENGINE_REF`, and
  `compat.yml` already answers the question Dependabot would be asked.

## 9. Risks

**The verb's output is a golden file, and golden files rot quietly.** The mitigation is that
`--check` runs in the registry's CI on every PR, so the pages are compared against the data far
more often than they are read.

**A registry contributor now needs the engine installed to regenerate.** That is a real cost
against `contributing.md`'s promise that registry data *"needs no Python"*. The promise survives
for *authoring* — you still write YAML and cite a paper — but not for regenerating pages. CI
regenerating them on the contributor's behalf was considered and rejected: a bot commit into a PR
means the diff a reviewer approved is not the diff that merges, and the reviewability of the
generated page is the whole argument for committing it.

**Eight pages is small enough that the generator's value is not yet proven.** Stated rather than
hidden: at this size a reader could open the folder. The argument is that the folder is the thing
comeni-registry#1 just made not-authoritative, and that the cross-references in §3.2 are facts no
single file holds.
