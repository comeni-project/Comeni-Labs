# Samples 7 — where it runs, how to add a piece, and scenario 1 by uploading — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reader can see in one table what measures data, where each one runs and what crosses; a contributor can add a format or a measure from the inspectors README; and scenario 1, walked with a real model and a real FASTQ pair, ends with `paired` and `read_length` measured and nothing invented.

**Architecture:** Documentation in the places the repository already keeps it (the protocol page, `ARCHITECTURE.md` §6, `registry/inspectors/README.md`, `packages/comeni-inspect/README.md`), then the walk the round protocol describes (`docs/internals/walking.md`): every finding an issue first, mechanical ones fixed test-first, protocol ones brought to the operator. The step closes with a journal entry and a compaction.

**Tech Stack:** Markdown; the running stack (`make dev`), a local model (`make ai-up OLLAMA_GPU=rocm`), headless Chrome.

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §2 (*where it runs is declared*), §12 (14.7.6.7), §14 (*Acceptance*). Part 14.7.6.7 of #134. Depends on parts 1–6.

## Global Constraints

- **Writing documentation, four rules** (`CLAUDE.md`): lead with what the reader gets; name sections after what somebody does; no internal names a reader must learn (Mendel, Wiener, the forge, `comeni-core`); no provenance (issue numbers, audit ids) in a task page.
- **Do not claim anything about where sequencing data goes on managed cloud.** The table says *this server* and *the lab's machine*; it does not say *Comeni's cloud*.
- **Say "does not receive patient data" only where it holds**: at level 0 a sample's head reaches the server, and the table says so plainly.
- **Nothing in a doc is a count.** No "three measures", "nine tools".
- **Every walk finding gets an issue before any code** (`docs/internals/walking.md`).
- `make doc-sizes`: `CLAUDE.md` ≤ 300 lines, `now.md` ≤ 150.

## Review Focus

1. **The table says where a sample's head goes at level 0**: our server, read by an inspector, and (from 14.7.7) a model. A reader must not come away thinking nothing leaves their machine. Pinned in Task 1 by a doc test.
2. **The five-step guide works for a newcomer**: following it to add a toy measure (`gc_content`) in a scratch copy of the registry passes the guards. Pinned in Task 2.
3. **The walk uses a real pair**, not the synthetic fixtures. Pinned in Task 3.
4. **A finding is not fixed inside the walk**: it is written down, then becomes an issue. Pinned in Task 3's procedure.
5. **The journal entry names commits**, not summaries. Pinned in Task 4.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `docs/design/authoring-protocol.md` | *Where each measurer runs* table; rule 4 points at the vocabulary's who-measures-what |
| Modify `ARCHITECTURE.md` §6 | inspectors beside profilers; the table, by reference |
| Modify `registry/inspectors/README.md` | what an inspector is; add a format or a measure in five steps |
| Modify `packages/comeni-inspect/README.md` | link to the guide and the protocol |
| Create `tests/repo/test_where_it_runs.py` | the table names every `runs:` value a piece declares |
| Create `docs/notes/journal/2026-10-XX-samples.md` | the session record |
| Modify `docs/notes/now.md` | compacted |

---

### Task 1: Where each measurer runs

**Files:**
- Modify: `docs/design/authoring-protocol.md`, `ARCHITECTURE.md` (§6)
- Test: `tests/repo/test_where_it_runs.py`

- [x] **Step 1: Write the failing test**

```python
# tests/repo/test_where_it_runs.py
"""The where-it-runs table covers every place a declared measurer can run (spec §2)."""

from support.paths import ROOT


def test_the_table_names_every_place_a_piece_runs():
    from mendel_resolver import layers

    loaded = layers.load(ROOT / "registry")
    places = {f.runs for f in loaded.inspection.formats.values()} | {"lab"}
    assert places, "no measurer declares where it runs"
    page = (ROOT / "docs/design/authoring-protocol.md").read_text()
    table = page.split("## Where each measurer runs", 1)[1].split("\n## ", 1)[0]
    for place in sorted(places):
        word = {"server": "this server", "lab": "the lab's machine", "browser": "the browser"}[place]
        assert word in table, f"the table does not say what runs on {word}"
    assert "level 0" in table and "head" in table
```

- [x] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/repo/test_where_it_runs.py -q`
Expected: FAIL — no such section.

- [x] **Step 3: Write the section**

In `docs/design/authoring-protocol.md`, after *How a fact's source reaches the tiers*:

```markdown
## Where each measurer runs

Every measurer declares where it runs (`runs:`), so moving one is a change to that field and a
runner, never a redesign. A protection level can refuse anything that runs on this server.

| Measurer | Reads | Runs on | What crosses | Allowed at |
|---|---|---|---|---|
| **Inspector** (a format and its measures) | the first 4 MB of one uploaded sample, a file or a pair | **this server**, in its own process, with time, memory and size limits | the sample's head reaches this server; nothing leaves it. The facts go into the goal | level 0 only |
| **Profiler** (a tool used to measure) | all the data | **the lab's machine**, inside the pipeline the lab runs | nothing reaches this server; the lab reads the profile back in | every level |
| **Characteriser** (a model, 14.7.7) | the sample's head | a model, through a declared door | the head reaches the model's provider | level 0 only |
| *Later:* an inspector in **the browser** | the head | the person's browser | only the facts | designed for `guarded` |

**At level 0 a sample's head reaches this server.** That is the loosening recorded below; the
other levels are written so that tightening is filling in a row.
```

Rule 4's sentence *"Which types have an inspector is declared"* gains: *"; the vocabulary lists, for every measurement, what measures it and where that runs."* In `ARCHITECTURE.md` §6, add a paragraph: *Inspectors measure a sample's head on this server before the build; profilers measure all the data on the lab's machine when the pipeline runs. Both produce the same measurement ids, and a fact records which one measured it (`Measured.by` for a profiler, `Measured.pieces` for an inspector). Where each runs is the protocol page's table.* (link it).

- [x] **Step 4: Run it, and the doc checks**

Run: `uv run pytest tests/repo/test_where_it_runs.py -q && make docs links doc-paths doc-sizes`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add docs/design/authoring-protocol.md ARCHITECTURE.md tests/repo/test_where_it_runs.py
git commit -m "docs: where each measurer runs, and what crosses (#134)"
```

---

### Task 2: Add a format or a measure, in five steps

**Files:**
- Modify (registry): `inspectors/README.md`
- Modify: `packages/comeni-inspect/README.md`

- [x] **Step 1: Write the guide**

`registry/inspectors/README.md`, leading with what a contributor gets:

```markdown
# Inspectors

Measure an uploaded sample's head on the server, so a person who is not sure of a fact can
answer with a file. An inspection is built from small pieces, each written once:

- **codecs** unwrap bytes (`gzip`);
- **formats** turn bytes into records and confirm the file is what its name says (`fastq`);
- **measures** read records of one shape and produce one measurement (`read_length`).

A format and every measure that reads its record shape make an inspection. Add a format, and every
measure of its shape works on it; add a measure, and it works on every format of its shape.

## Add a measure

1. Make sure the measurement exists in `vocabulary/measurements/`.
2. Create `measures/<id>/measure.yml` (`declares: measure`, `id`, `version`, `measures`,
   `record`, `decided`, `entry: piece/<id>.py`).
3. Write `piece/<id>.py` with an `Accumulator`: `add(row)` for each row of records, `result()`
   returning a value with its evidence, or *undetermined* with a reason below `decided`.
4. Write `piece/test_<id>.py` against the format's fixtures, including a case that is undetermined.
5. Run `uv run pytest registry/inspectors tests/guards/test_inspector_pieces.py tests/registry/test_inspection_conformance.py`
   and regenerate the golden reports it names.

## Add a format

The same five steps with `formats/<id>/format.yml` (`reads`, `extensions`, `record`, `runs`) and a
module with `confirms(first)` and `records(stream)`; its fixtures go in `piece/fixtures/<case>/`.

## The rules every piece keeps

Imports only from the allowlist in `tests/guards/test_inspector_pieces.py`; never raises; never
guesses (below its threshold, a measure says *undetermined* and why); never decides on a file's
name. A faster implementation in another language is welcome if it reproduces every golden report
byte for byte (`comeni-inspect`'s `PROTOCOL.md`).
```

Link it from `packages/comeni-inspect/README.md`.

- [x] **Step 2: Follow it, as a newcomer would**

In a scratch copy of the registry (`cp -r registry /tmp/claude-1000/reg-try`), follow *Add a measure* for a toy `gc_content` (declare the measurement first, `kind: number`, `per_sample: true`, a cite), writing only what the guide says. Run the step-5 command against the copy (`--rootdir`, or point `support.paths` at it through the env var the tests read, if any). Every place the guide was missing a step is a fix to the guide, made now. Delete the copy.

- [x] **Step 3: Commit, in the registry and here**

```bash
cd registry && git add inspectors/README.md && git commit -m "Inspectors: how to add a format or a measure (comeni-labs #134)" && cd ..
git add registry packages/comeni-inspect/README.md && git commit -m "docs(inspect): add a format or a measure, in five steps (#134)"
```

---

### Task 3: Walk scenario 1 by uploading

**Files:** none planned; each finding is an issue, and a mechanical fix gets its own test-first commit.

- [x] **Step 1: A real pair**

Fetch one real paired-end RNA-seq pair's heads: the nf-core test dataset the RNA-seq pipeline uses (`https://raw.githubusercontent.com/nf-core/test-datasets/rnaseq/testdata/GSE110004/SRR6357070_1.fastq.gz` and `_2`). Keep them in the scratchpad, never in the repository. If the URL has moved, find the current path in `nf-core/test-datasets`' `rnaseq` branch README.

- [x] **Step 2: The stack and a local model**

`make dev`; `make ai-up OLLAMA_GPU=rocm`; the want on `gemma3:12b` (decided for #187). Check the settings menu shows *Protection level: Level 0* as built.

- [x] **Step 3: Walk it**

In the browser at `http://localhost:5173`: *Paired-end RNA-seq to gene counts*. At each gap:
- **reads**: *I have it, and I'll upload a sample* → the pair;
- **read length** and **paired**: closed by that upload, marked measured;
- **genome**, **annotation**: *I have it* (asked, answered);
- **strandedness**: answered by the person (no inspector measures it).

At the goal card: `paired` and `read_length` say *measured · fastq 1.0.0 · from 1 sample*; nothing is marked measured that the file did not measure; nothing invented. Continue into the build and check the aligner's decision cites the measured read length (yellow border, *measured by fastq@1.0.0 + read_length@1.0.0*).

Also walk the failure states once each: a FASTA named `.fastq`, a `.bam`, three files, and (temporarily, in the settings) a level other than 0 — which must be refused as *designed* rather than chosen.

Write every finding down as it happens; **do not stop to fix**.

- [x] **Step 4: An issue for every finding**

For each, open an issue with the *Walk: mechanical* or *Walk: protocol* template (lead with what happened and what was expected; then the evidence), as a sub-issue of #134. Mechanical: fix test-first, close citing the commit. Protocol: STOP and bring it to the operator as a choice with its costs.

- [x] **Step 5: Re-walk** once every issue is closed or decided. The round ends when scenario 1 passes by uploading.

---

### Task 4: Close the step

- [x] **Step 1: The journal entry**

`docs/notes/journal/<date>-samples.md` in the README's order: where things stand (with the commands that verify them: the guards, the conformance goldens, the speed budget's number, the per-request registry time before and after), what changed (commit hashes for every part, and the registry branch's commits), decisions and why (one registry for tools, profilers and inspectors; composed pieces; one pass; undetermined; a separate process; bytes not stored; `MEASURED` not `INSPECTED`; steps returned not streamed), what is next (14.7.7 the characteriser, which fills the *no inspector* branch), open questions (the registry branch merged to `main`?).

- [x] **Step 2: Compact**

By `docs/notes/compaction.md`: fold the step into `now.md` (14.7.6 done; 14.7.7 next), move the entry to `archive/`, keep `now.md` ≤ 150 lines (`make doc-sizes`).

- [x] **Step 3: Update the spec and the task tree**

Mark the spec's §9 and §10 with the two rulings (MEASURED; bytes not stored), comment on #134 with the commits and close it; close #216 if the registry branch has merged.

- [x] **Step 4: Commit, and run `make check` separately**

```bash
git add docs && git commit -m "docs(notes): samples built — 14.7.6 closes (#134)"
make check > /tmp/claude-1000/check.log 2>&1; tail -20 /tmp/claude-1000/check.log
```

---

## Execution record

- **Task 1** (60b29d9..d327068): the table also says *only the head leaves the browser; nothing is
  stored*, and marks the characteriser designed.
- **Task 2** (d327068..6fe04ed): followed for a toy `gc_content` measure in the real registry
  checkout, removed after (the guards read `ROOT/registry`); five failures in Comeni Labs taught
  the guide's note on what a new measurement moves.
- **Task 3:** walked with the real pair SRR6357070 (Chrome, `gemma3:12b`). Findings #229–#233:
  #232 fixed (e152db8); #233 decided A by the operator, built (d9e3d6e); #229 A, built (f7f489c).
  The first walk began its session through the API because of #229; the re-walk began on home
  and passed by uploading.
- **Task 4:** the journal entry was compacted in the same commit (29fd0a5); `now.md` stayed at 150
  lines by dropping traps `CLAUDE.md` already holds. Spec §10 carries the two built rulings (§9
  already had `MEASURED`). **Deviation:** #134 closes after the step's open sub-issues are done
  (operator, 2026-10-03), not in this task; #216 closes when the registry branch merges.
- **Final review** (opus, fresh context): no Critical. Fixed: `test_where_it_runs` passed with the
  Inspector row deleted (now reads each row's cell), and *Add a format* ran a new format's tests on
  FASTQ's fixtures (`request_for(..., format=)`, registry 8ddbbd5) — 3915a75. Five minors → #234.
