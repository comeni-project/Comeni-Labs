# Forge MVP 0 — remove the old forge

**Issue:** #361 (parent #360). **Status:** proposed, awaiting the operator's approval.
**Design:** [the forge MVP design](2026-10-19-forge-mvp-design.md) — *keeping the old forge's
code, data or routes* is a non-goal; it is rewritten from scratch.

## Why

The new forge (catalogue, forging chat, tests as Wiener runs, pull requests, releases) shares
nothing with the old one's adaptation workflow, question queue, drift checks and local `land`.
Leaving the old code beside the new would mean two forges, two sets of tables and two
vocabularies for one job. There are no users before v0.1.0, so nothing is migrated.

## What the old forge is (inventory, 2026-10-19)

- **`packages/mendel-forge/`**, about 10,700 lines: sources (nf-core, pegi3s), the catalogue, the
  adaptation workflow, scaffolding and holes, proposals, drift, `land` (writes into a local
  registry checkout), its AI prompts and the `forge` CLI.
- **In `mendel-api`:** the routes `forge.py`, `contracts.py`, `questions.py`, `sources.py`; the
  services `forge_*.py`, `questions.py`, `answers.py`, `checked.py`, `drift.py`, `queue.py`,
  `sources.py`; the worker's nightly source sync and drift check; the tables `forge_*`,
  `source_check` and `queue_visit`.
- **In the browser:** `frontend/src/forge/` (41 files), `frontend/src/api/registry.ts` and the
  `/forge…` routes behind the *Registry* tab.
- **Elsewhere:** its tests (`packages/mendel-forge/tests`, `packages/mendel-api/tests/forge`,
  parts of infrastructure tests), the guard `tests/guards/test_forge_write_boundary.py`, its
  entries in the purity guard, `tools/forge_ai_eval.py`, the `forge` CLI's reference entry, its
  diagnostics in `diagnostics.yml`, Make targets, and about twenty documentation pages that
  describe it.

## What changes

### 1. Delete

Everything in the inventory, with one database migration that drops the old forge's tables. The
`mendel-forge` package is removed from the workspace (`pyproject.toml`, `uv.lock` regenerated);
its `land` CLI is not kept, because the new forge publishes by pull request through a
`RegistryPublisher`, not by writing into a local checkout.

### 2. Keep, by moving out of the forge

The builder records every model call in `ai_invocation` using three vocabularies that live in
the forge's `workflow.py` today: `Agent`, `InvocationPurpose` and `InvocationState`. They move
to `mendel_api` beside the table that uses them (**my call:** `mendel_api/invocations.py`),
keeping the values the builder writes and the `forge` agent and purpose the new forge will use.
Nothing about how a call is recorded changes.

### 3. Settings

*Registry & sources* keeps the registry folder, its layers and the **GitHub token** (the new
forge publishes with it; its help text changes to say so). **Docker Hub** goes (it was for
pegi3s, which is later) and so does the **nightly source check** (the new catalogue's sync is
part 1's). The *Adapting tools* model purpose stays for the new forge.

### 4. The *Registry* tab between parts 0 and 1

With the old screens gone there is no registry page until part 1's catalogue, and a link to
nothing is refused. **My call:** part 0 removes the tab, and **parts 0 and 1 merge into `main`
together**, so `main` never has a product without a registry section. Part 0 is still its own
reviewed step on the branch.

### 5. Guards

`test_forge_write_boundary.py` guarded *nothing in the old forge writes a registry except
`land`*. With the package gone it guards nothing and is deleted; the guard ledger records why.
The new forge's boundary (*nothing reaches the registry except an approved pull request*) gets
its own guard in part 5 (#366). The purity guard drops `mendel_forge` from its list of adapter
packages.

### 6. Documentation

Pages that describe the old forge as current are corrected: a statement about the old forge is
removed or replaced by a pointer to the forge design, and `docs/how-to/registry/review-proposals.md`
(the old flow) is deleted with its links. `CLAUDE.md`'s source map loses
`packages/mendel-forge/`. The new forge's pages are written by its parts, not here.

## Not in this part

- Anything new: the catalogue, sources and dashboard are part 1 (#362).
- The registry's own repository (`comeni-registry`) is untouched.

## Testing

- **The suite stays green** after the deletion, Python and frontend, with the database tests run
  against the isolated test databases (`make test-db`, `make test`), never the development one.
- **A builder walk still records its model calls:** the existing authoring tests that assert
  `ai_invocation` rows pass with the moved vocabularies.
- **The migration:** upgrading from the current head drops exactly the old forge's tables and
  leaves every other table; downgrading is not supported (no backward compatibility before
  v0.1.0), and the migration says so.
- **Nothing still names the old forge:** a check that `mendel_forge` appears nowhere in code,
  tests, tools or configuration, and `make check` (lint, types, docs, links, doc paths) passes.
- `make guards` passes with the purity list updated.
