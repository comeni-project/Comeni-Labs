# Code and documentation organisation

**Date:** 2026-08-16
**Status:** Approved. Not yet implemented.
**Closes:** [issue #41](https://github.com/comeni-project/Comeni-Labs/issues/41)
**Related:** `ARCHITECTURE.md`, `CLAUDE.md`, `docs/README.md`

> This spec lives in `notes/specs/` and Task 6 moves that directory to `notes/specs/`.
> The loop is deliberate: a spec that described the move from outside the thing being moved
> would be the one file exempt from its own argument.

## What the issue says

Three complaints, and they are not the same complaint:

1. **The code has no organisation.** `comeni-core` holds 24 modules at one level, 5,541 lines.
   `pipeline.py` is 1,116 of them, `rules.py` is 1,170, `cli.py` is 851.
2. **The documentation is bloated and hard to follow**, with the error codes named as the
   worked example of something a reader cannot find.
3. **The documentation does not match what the repository has become.** The AI is the primary
   operator — it produces a goal, drives the CLI, and treats `pipeline.yml` as the save file it
   sets down and picks up. A human can hand-author one and that is not the main path.

The third is the one that decides the other two, because it says who the reader is.

## What this is not

**No new capability.** `pipeline.yml` and the `mendel` CLI already *are* the save-file
interface; nothing here adds a typed Python entry point, a fifth egress door, a CLI verb or a
schema field. Decided 2026-08-16 — an importable `comeni.build(goal)` was considered and
deferred, because it would need its own egress review and Plan 2 owns the question of what an
agent calls.

No package renames, no dependency changes, nothing to `registry/` or `vendor/`.

## The oracle

**A pure reorganisation has a byte-exact test, and it is not "the tests pass".**

`pipeline.yml` carries no paths and no timestamps by design, and `main.nf` and `nextflow.config`
are golden-file tested. So the same goal against the same registry must produce the same three
files, byte for byte, before and after every task here. Verified on `main` at `7315347` —
two independent builds produced identical output directories:

| file | sha256 (first 16) |
|---|---|
| `pipeline.yml` | `f1f2d7e5e9cca6a3` |
| `main.nf` | `76355bbf9f10d6e6` |
| `nextflow.config` | `72ddb081638edf76` |

`tools/refactor_oracle.py` builds `examples/rnaseq-goal.yml` and prints these. **Every task
checks them, and Tasks 1–5 must not move one at all**: those tasks relocate code and split
files, so a moved digest is a behaviour change hiding in a large diff, which is the only real
risk in this work.

**Plan-local, and deleted in Task 10.** There is no single determinism test to extend — the
property is asserted across `test_resolve`, `test_emit`'s golden files and `test_counts` — and
a permanent digest test would need re-blessing on every legitimate behaviour change, which is
the kind of gate people learn to re-bless without reading.

## Part one — the code

### `comeni-core`: five packages, two cross-cutting modules

```
comeni_core/
  __init__.py       unchanged
  yaml_strict.py    every group reads YAML through it
  diagnostics.py    every group can emit a code
  declared/         what a registry layer holds
    contract  measurement  vocabulary  roles  registry  layered  layer
  goal/             what was asked for
    goal  profile  premise
  plan/             what was decided
    ir  decision  tiers
  artifact/         what is shipped
    pipeline  materialise  load  lockfile  digest  egress  gates
  spell/            how a value is written down
    marks  routes  directives
```

Grouped **by lifecycle stage** so the directory a reader opens and the document they started
from agree: `ARCHITECTURE.md` describes five stages, and someone asking *where does routing
happen* should not have to know our type names first.

`yaml_strict.py` and `diagnostics.py` stay at the top because they are cross-cutting. Filing
them under `spell/` would be a claim about what they are that is not true — one is a loader,
the other is the error registry, and every group uses both.

`gates.py` joins `artifact/`: a gate verdict is a thing the pipeline records.

### `__init__.py` does not change

It already re-exports a curated public surface, and 36 files also reach past it to
`comeni_core.pipeline`. After this there is **one spelling at each level** — the package name
for a consumer, the full path internally.

**No back-compat module shims.** `comeni_core.pipeline` does not survive as an alias for
`comeni_core.artifact.pipeline`. Two ways to spell one thing is how the two come to disagree,
which is the argument this repository makes about `DeclaredKind`, about invariant 14's literal
list, and about `AnyKey`. There are no external consumers yet: the registry is data and Wiener
does not exist.

### The three splits

| From | Into | Why there |
|---|---|---|
| `pipeline.py` 1,116 | `artifact/pipeline.py`, `artifact/materialise.py`, `artifact/load.py` | three jobs — what the artifact *is*, how it is built from an IR (`Pipeline.of`), and what a file must satisfy to be read back (`MD0200`–`MD0224`) |
| `rules.py` 1,170 | `rules/format.py`, `rules/table.py`, `rules/validate.py` | the validator alone is ~450 lines and is where a rule author's error comes from; the models and the stacking are different readers |
| `cli.py` 851 | `cli/__init__.py` + `build` `emit` `upgrade` `publish` `profile` `explain` | six verbs in one module, so a contributor adding a seventh reads all six |

`mendel-resolver` (eleven modules) and `mendel-compiler` (seven) get **no subpackages** beyond
those two splits. Inventing groups for them would be organisation for its own sake, which is
the thing being complained about.

### The guards that reference paths as strings

Four tests and two tools name module paths literally, and a rename can silently disable a guard
by pointing it at a file that no longer exists — which is exactly A67's shape, where a mistyped
package key made the scan pass **faster**:

- `tests/test_construction.py` — three permitted-spelling paths
- `tests/test_purity.py` — `ATTRIBUTE_EXEMPT_PATH`
- `tests/test_purity_runtime.py` — two frame paths
- `tools/generate_types.py`, `tools/generate_diagnostics_doc.py` — output paths

Each gets a revert recorded in the guard ledger: point it at the old path, confirm the guard
fails rather than passing on nothing.

## Part two — the documentation

### The tree

```
docs/                   25 files — what a reader or an agent consumes
  README.md             the front door: routes by who you are
  guides/  reference/  concepts/  design/
notes/                  69 files — the working record
  README.md             what this is, and why it is not in docs/
  journal/  plans/  audits/  specs/
```

`notes/` is 69 of the 94 markdown files under `docs/` and is most of the bloat a
reader meets. It moves out rather than being archived or signposted: the record stays
versioned and linkable, and stops being the first thing `ls docs/` shows.

**A `README.md` in each of the nine directories.** Each earns its place by answering *what is
in here and which file do I open first* — not by listing what `ls` already prints.

### The link cost, and the checker

73 relative links inside `internal/`, 43 pointing into it from outside. Most of the 73 are
sibling links that move together; the ones crossing out (`../../design/conformance.md`) need a
level added.

**A link checker joins `make check`.** Nothing checks them today, which is why the move is
worth doing with one rather than without: a mechanical repair verified by hand is a repair
nobody can re-verify next time.

### Three answers to what the issue names

**`docs/reference/diagnostics.md`** — every code, generated from `diagnostics.yml`, grouped by
band, with what it says, whether it refuses, and `mendel explain <code>` beside each. `cli.md`
keeps the verbs and loses the table. The table is currently two-thirds of the way down a page
about something else, which is why it could not be found.

**`docs/guides/driving-mendel.md`** — the page that does not exist. The operating loop: produce
a goal, `build`, read `pipeline.yml`, change a setting, `emit`, `publish`. What `needs_review()`
obliges, and how to answer a tier-4 question *in the file* rather than by re-running. That loop
is today described in fragments across `CLAUDE.md`, `pipeline-schema.md` and `mendel.md`, and
nowhere as a sequence.

**`docs/README.md` routes by reader**, in three doors: *driving Mendel*, *running a pipeline it
produced*, *changing Mendel*. The current front door is organised by document type, which helps
only a reader who already knows which type they need.

### How far the re-voicing goes

**The front door and the getting-started path, not the nine design documents.** Those argue
*why*, and are addressed to whoever is deciding whether to trust this — an audience that has
not changed. What changed is who does the driving, and that is a guides-and-README question.

**Two pages are added while the complaint was bloat.** Both are net removals of confusion
rather than additions of content: one replaces a table nobody can find, the other replaces a
loop that exists only as fragments.

## Part three — the root

| File | |
|---|---|
| `CODE_OF_CONDUCT.md` | **deleted.** 119 lines of boilerplate nobody here wrote or wants |
| `CONTRIBUTING.md` | → `docs/guides/contributing.md`, with a three-line root stub. GitHub reads the root path when it offers contributing guidelines on a pull request, so dropping the stub removes an affordance rather than ceremony |
| `SECURITY.md` | **stays.** It is where a vulnerability report goes, GitHub surfaces it in its own tab, and for a repository with clinical positioning its absence reads badly |
| `README.md` `ARCHITECTURE.md` `CHANGELOG.md` `CLAUDE.md` | stay at the root |

`ARCHITECTURE.md` stays because it is the contributor's entry point, `CLAUDE.md` leans on it in
four places, and the root is where a stranger looks for it.

### `CLAUDE.md`

723 lines, the largest file in the repository and the AI operator's entry point — so the same
complaint applies to it, and it is also the file most likely to be read *in full* by an agent.

Restructured with `claude-md-management:revise-claude-md`, and **last**, because it describes
the layout everything else here is changing. Doing it first would mean writing it twice.

## The tasks

| | | Verified by |
|---|---|---|
| 0 | the oracle; `main`'s three digests recorded | two builds agree |
| 1 | `comeni-core` layout; every import moved | `make verify` + digests unmoved |
| 2 | split `pipeline.py` | `make verify` + digests unmoved |
| 3 | split `rules.py` | `make verify` + digests unmoved |
| 4 | split `cli.py` | `make verify` + digests unmoved |
| 5 | the four guards and two tools that name paths | each reverted and watched |
| 6 | `notes/` → `notes/`; links repaired; checker into `make check` | the checker, run |
| 7 | `docs/reference/diagnostics.md`; `cli.md` loses the table | `make docs` |
| 8 | `docs/README.md`; a `README.md` per directory | the link checker |
| 9 | `docs/guides/driving-mendel.md`; the root files | `make check` |
| 10 | `CLAUDE.md` via the skill; delete the oracle; journal entry | `make verify` |

Tasks 1–5 are pure relocation and **must not move a digest**. Tasks 7 and 10 touch generated
documentation, so `make docs` is the check there.

## What could go wrong

**A behaviour change hidden in a 5,000-line diff.** The oracle is the answer, and it is checked
per task rather than at the end so the task that moved it is the task that is still open.

**A guard silently disabled by a rename.** Task 5 exists for this, and every one of the six
gets a recorded revert rather than a reading.

**Links rotting during the move.** The checker lands in the same task as the move, not after
it.

**`CLAUDE.md` describing the old layout.** It is last for that reason, and the journal entry in
the same task is what a fresh reader picks up.
