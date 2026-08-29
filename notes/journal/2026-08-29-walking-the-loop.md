# 2026-08-29 — walking the loop, by hand, from raw

**Read this first if you are picking the project up. This is the newest entry.**

[The 2026-08-25 entry](2026-08-25-the-screens-against-their-artboards.md) ended with an
instruction rather than a plan: *set a pipeline up by hand and actually run it, end to end — the
point is not to demonstrate that it works, it is to find where the loop rubs.* This is that walk.

**It closed.** A pipeline drawn by hand in the builder — two steps, one wire, nothing preloaded —
was kept, linted, couriered to Wiener, given a read pair, run, and read. `run 417bcc1c ·
succeeded · 2 of 2 steps · 42s`, on the nf-core `SRR6357070` pair, TRIMGALORE into FASTQC.

**Nothing about the pipeline was the problem.** Every defect below is in the machinery around it:
five in bringing the stack up, and nine in the builder's own surface. That split is the finding.

## The loop, as it actually went

| step | what happened |
|---|---|
| draw | deleted the five preloaded spine steps, added `trimgalore` and `fastqc`, wired `reads → reads` |
| keep | **500, silently** — `PermissionError: /app/drafts/<id>`. Fixed, then kept at 12:27:05 |
| gate | `lint: passed` — 3 warnings, 3 files no errors |
| run | *Send to Wiener* → `ae00463f, 544 kB`; one hole discovered, `input`; *Start run* |
| read | overview, console, graph all correct. 42s |

The draft row was exactly what was drawn — `trimgalore_1 → fastqc_1` on port `reads` — so the
canvas and the artifact never disagreed. **That half is sound and was never in doubt.**

## Five frictions before a single click, all fixed

Every one of these is in `make dev`, and four of the five were **already solved elsewhere in the
same file** for a different service.

- **Wiener's database was never migrated in dev.** `alembic upgrade head` lived in
  `docker-compose.prod.yml` and nowhere else, so `make prod` came up migrated and `make dev` came
  up with no `run` table: nine healthy containers and a traceback on the first request to
  `/api/runs`. Moved to the base; the overlay's copy is deleted rather than duplicated.
  **Two guards** in `tests/test_compose.py`, both watched failing against the restored defect —
  one asserts every database is migrated by *exactly one* service in the base, the other that the
  overlay never introduces a migration the base lacks, which is the direction it actually drifted.
- **The HMR server could not reach Wiener at all.** `vite.config.ts` proxied `/api/runs` to
  `localhost:8001`, and `wiener-api` publishes **no host port** by design. `make dev` prints the
  HMR address on its first line, so the advertised way in was the one where half the app 502s.
  It now proxies at nginx — which keeps the decision *and* makes dev take the path prod serves.
- **`.run/drafts` and `workspace` came up root-owned**, because Docker creates a missing
  bind-mount source as root and the containers run as the host user. This is the trap
  `CLAUDE.md` records, and `make dev` already fixes it — for `.run/wiener/*` only, in a comment
  whose own text names `./workspace` as the precedent. **It is what made *Keep* fail**, which is
  the one control the whole loop hangs on.
- **A second checkout collides on container names** and compose fails part-way through `up`,
  naming one container. `.env.example` anticipates this and ships the overrides commented out, so
  the default experience is the collision. A `names-free` preflight now lists every clash at once
  and names both ways out.
- **`make dev` never installs frontend dependencies.** Pull a commit that adds one and Vite serves
  a broken app while `http://localhost/` stays green, because the `web` image runs its own
  `npm ci`. Measured after a 152-commit pull: `@tanstack/react-virtual` declared, absent, and only
  `tsc -b` said so. `node_modules` is now a make prerequisite of `package-lock.json`.

**The pattern across all five: the fix existed and covered one service.** Wiener's migration was
in prod only, Wiener's directories were mkdir'd and Mendel's were not, Wiener's port was closed
and Vite was not told. Each is one line, and each was invisible because the *other* half worked.

## What using the builder found, and none of it is fixed

**The three that actually cost time:**

- **A failed *Keep* says nothing.** The API answered 500 and the rail sat there, unchanged, still
  offering *Keep*. Nothing on screen, nothing in the console. The only way to learn that the
  central action of the page had failed was `docker logs`. This is the defect that matters most:
  every other item below is friction, this one is a lie by omission.
- **There are two *Send to Wiener* buttons, stacked.** The rail renders the step's label as a
  button and the panel renders the real control directly beneath it. Both are `disabled: false`.
  Clicking the upper one does nothing at all, and on an 819px viewport the real one is below the
  fold — so the visible button is the inert one.
- **Every step is placed at the same coordinates.** Double-click `trimgalore`, double-click
  `fastqc`, and you have one node on screen and two in the graph. Nothing indicates the second
  landed on top of the first; it looked like the add had failed until dragging revealed it.

**The rest:**

- **The module palette is unreachable except by mouse.** Each row is a bare
  `div draggable="true"` — no `role`, no `tabindex`, absent from the accessibility tree entirely.
  The only two ways to add a step are drag and double-click.
- **The verdict panel lags the graph and does not say so.** Mid-edit it read
  `UNMET MD0506 star_align.index` while `star_align` was already deleted. It converges in ~2–3s;
  until then it describes a graph that no longer exists, with nothing marking it stale.
- **The layout does not reflow.** Below roughly 1100px the three columns clip rather than
  rearrange: at 735px the canvas is a 197px strip and the rail's sentences are cut mid-word.
  There is no breakpoint, and no way to collapse either side panel.
- **The rail scrolls itself back to the top**, taking the parameter form you were filling with it.
- **The pipeline is still called `RNA-SEQ SPINE`** after every one of its steps was deleted and
  replaced. The draft row's `name` column is empty; the header is showing the example's name, and
  nothing on the page renames it.
- **An empty canvas has no right-click menu.** Nodes have one (*Settings…*, *Delete step*); the
  place you would reach for *add a step here* has nothing.

## Two numbers that disagree, both small

- The console footer says **8 events** above **6 rows**. The database holds 8; two are run-level
  and have no process, so they are counted and not rendered. Same class as the rail that
  `ab218cb` taught to count what it names.
- The run page says **42s**, the board says **45s**, and `ended_at - submitted_at` is **44.7s**.
  Two screens, one run, no explanation of which span either is measuring.

## What a fresh reader gets wrong

- **"The builder is bad."** That was the expectation going in, and the walk does not support it.
  The graph model, the wire, validation, emission, the gate and the courier all did exactly what
  they claim. What is bad is the **feedback**: a silent 500, a duplicated button, an invisible
  stacked node, a stale verdict. Every one is a report-back defect, not a modelling defect.
- **"`0.4 / 12 GB` has lost its unit."** It has not — `units.ts` shares the unit deliberately and
  documents why, including the `0.0` case W2 fixed. Checked before reporting; it is correct.
- **"Deleting a producer should be a problem."** Not if the type declares an entry channel.
  Removing TRIMGALORE left `star_align.reads` unwired and the verdict stayed clean, correctly —
  `fastq.reads` is an entry channel and `genome.index.star` is not, which is why deleting
  `star_genomegenerate` *did* raise `MD0506`.

## What is next

**The three costly builder defects are one afternoon**, and they are the difference between
*the loop works* and *the loop is usable*: surface a failed mutation, delete the duplicate
button, offset a new node from the last one.

**Nothing here touches the forge**, which is still carried as needing testing and rework.
