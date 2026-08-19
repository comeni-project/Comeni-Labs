# Plan 3D — the forge, redesigned

> **For the executor:** drive this with `superpowers:executing-plans`, task by task, yourself.
> `CLAUDE.md` forbids farming implementation out to subagents here. **Tick each `- [ ]` as it
> completes**, and where a step was carried out differently, tick it anyway and record the
> deviation in that phase's execution-record table.

**Goal:** make the forge answerable — rank the candidates so a question has a visible right
answer, then merge three screens into one board that says whether anything is wrong.

**Architecture:** Phase 1 is arithmetic over declared data in `mendel-forge` and writes the
producer for `OpenQuestion.suggested`, whose consumer is already built. Phases 3–4 collapse
`Sources` and `Contracts` into one `GET /api/tools` behind a status board. Phase 5 is help.
Phase 6 revisits the landing page **last**, because it points at these screens.

**Tech Stack:** Python 3.12 / Pydantic / FastAPI, React 19 / TS / Vite / Tailwind 4,
generated TS client (`make client`).

**Spec:** [`notes/specs/2026-08-19-the-forge-redesigned.md`](../specs/2026-08-19-the-forge-redesigned.md)
— read it first; this plan argues from it.

## Global constraints

- **`make verify`, not `make check`**, for any change under `mendel_compiler/`, `resolve.py`,
  `router.py`, `rules/`, `emit.py`, `artifact/pipeline.py`. Phase 1 touches none of those, but
  run `make verify` at each phase boundary anyway — it is two minutes.
- **Never write a diagnostic code as a string.** Declare it in `comeni_core/diagnostics.yml`,
  emit through `coded()`, run `make docs`.
- **`frontend/src/api/` is generated.** Never hand-edit. Run `make client` after any API change.
- **The frontend gate is `npm run build` (`tsc -b`), not `npx tsc --noEmit`.** The looser command
  let six type errors accumulate across the whole of 3A.
- **No new design token, colour, radius or font.** `tokens.css` must stay byte-identical except
  where a phase says otherwise. `--text-hero` / `--text-lede` are front-door-only.
- **An absence is not a zero.** Anything unmeasured renders `—`, never `0`.
- **Guards must be watched failing.** Every new guard gets deliberately broken once, and the
  message recorded in the phase's execution record.

---

## Phase 1: rank the candidates, and set `suggested`

**Why first:** spec §7. The consumer of `suggested` is fully built and has no producer (§1.5).
This is the smallest change with the largest effect, and the only phase whose success is a
measurement rather than a judgement.

**The baseline is measured, not assumed.** Over the 30 ports in the 12 landed contracts, with 22
candidate types per hole:

| ranking | correct type ranked #1 |
|---|---|
| alphabetical — **what ships today** | **3%** (1 of 30) |
| port == last segment of the type | 63% |
| + port is any segment | 73% |
| + tool name shares a segment, + shares a namespace with an input | **83%** |

**Acceptance: ≥80% top-1 on that corpus.** The last row already clears it, so this phase is
implementing a validated heuristic rather than searching for one.

**Files:**
- Create: `packages/mendel-forge/tests/test_candidate_ranking.py`
- Modify: `packages/mendel-forge/src/mendel_forge/candidates.py`
- Modify: `packages/mendel-forge/src/mendel_forge/assemble.py:71-97` (`_hole`)
- Modify: `packages/mendel-api/src/mendel_api/questions.py:138-157` (`_ask`)
- Test: `packages/mendel-api/tests/test_suggested.py`

**Interfaces:**
- Produces: `candidates.for_field(field, stack, *, type_id=None, channels=(), excluding=None,
  port=None, tool=None, input_types=())` — same function, four new keyword-only arguments, all
  defaulted so every existing call site keeps working.
- Produces: `Hole.candidates` is now **ranked**, best first, for `type_id` holes.
- Produces: `OpenQuestion.suggested` is `candidates[0].value` when the hole has candidates.

### Task 1.1: the measurement harness

The harness comes before the heuristic, because that is how the `name` branch got good — its
comments record `reordering was tried first and did not help` and `splitting type_id into
segments was measured and was a net loss`. Without a number those sentences cannot be written.

- [x] **Step 1: Write the harness as a test that asserts today's floor**

Create `packages/mendel-forge/tests/test_candidate_ranking.py`:

```python
"""How often the right type is the first candidate offered.

**This file is a measurement, not an example.** The forge asks seven `type_id` questions per
module and the answer to each is one of twenty-two declared types; whether a person can answer
them is entirely a question of where the right one sits in the list. Alphabetical order put it
first once in thirty holes.

The corpus is the registry itself: every port of every landed contract is a hole whose answer is
already known, which makes this the one part of the forge with free ground truth.
"""

from pathlib import Path

import pytest
from mendel_resolver.layers import Layers, load

from mendel_forge import candidates

ROOT = Path(__file__).resolve().parents[3]

TARGET = 0.80
"""Spec §4. Below this the question is not answerable by a person reading a list."""


@pytest.fixture(scope="module")
def stack() -> Layers:
    return load([ROOT / "registry"])


def _holes(stack: Layers) -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every port in the registry as `(tool, port_name, true_type, this contract's inputs)`."""
    out = []
    for contract in stack.registry.contracts.values():
        tool = contract.id.split("@")[0]
        inputs = tuple(p.type_id for p in contract.consumes)
        for port in contract.consumes:
            out.append((tool, port.name, port.type_id, ()))
        for port in contract.produces:
            out.append((tool, port.name, port.type_id, inputs))
    return out


def _top1(stack: Layers) -> float:
    holes = _holes(stack)
    hit = 0
    for tool, port, truth, inputs in holes:
        offered = candidates.for_field(
            "produces[0].type_id",
            stack,
            excluding=tool,
            port=port,
            tool=tool,
            input_types=inputs,
        )
        if offered and offered[0].value == truth:
            hit += 1
    return hit / len(holes)


def test_the_right_type_is_the_first_candidate(stack: Layers) -> None:
    # **`excluding=tool` is what makes this honest.** Without it the contract being scored is
    # in the evidence its own ranking reads, which is the mistake `_played_by`'s docstring
    # records: every accuracy figure measured that way is meaningless.
    got = _top1(stack)
    assert got >= TARGET, f"top-1 is {got:.0%}, target {TARGET:.0%}"
```

- [x] **Step 2: Run it and watch it fail on the signature, then on the number**

Run: `uv run pytest packages/mendel-forge/tests/test_candidate_ranking.py -v`

Expected: `TypeError: for_field() got an unexpected keyword argument 'port'`. That is the
signature not existing yet, which is the correct first failure.

- [x] **Step 3: Commit the harness alone**

```bash
git add packages/mendel-forge/tests/test_candidate_ranking.py
git commit -m "test: how often the right type is the first candidate offered"
```

### Task 1.2: rank the type_id candidates

- [x] **Step 1: Add the four arguments and the scorer**

In `packages/mendel-forge/src/mendel_forge/candidates.py`, change the signature of `for_field`
to add four keyword-only arguments after `excluding`:

```python
def for_field(
    field: str,
    stack: Layers,
    *,
    type_id: str | None = None,
    channels: tuple[str, ...] = (),
    excluding: str | None = None,
    port: str | None = None,
    tool: str | None = None,
    input_types: tuple[str, ...] = (),
) -> list[Candidate]:
```

Then add, above `for_field`:

```python
def _fit(type_name: str, port: str | None, tool: str | None,
         input_types: tuple[str, ...]) -> int:
    """How well a declared type fits the port being asked about. Higher is better.

    **Arithmetic over declared data, never a model.** Invariant 2 is untouched: this proposes an
    order and a human still answers. It is also what keeps the forge deterministic — the same
    draft ranks the same way on any machine, forever.

    Every weight below was measured against the registry as ground truth
    (`test_candidate_ranking.py`), and the numbers are in the plan and the journal rather than
    only here. Alphabetical order — what shipped until now — put the right type first in **1 of
    30** holes. This scorer puts it first in **25 of 30**.

    The four signals, strongest first:

    1. **The port is the type's last segment.** `fa`/`fasta` -> `genome.fasta`, `bam` ->
       `alignment.bam`. Alone this is 63%.
    2. **The port is any segment.** `index` -> `genome.index.star`. Adds 10 points.
    3. **The tool's own name shares a segment with the type.** This is the signal that breaks the
       ambiguity nothing else can: a port called `index` is `alignment.bai` on `samtools/index`
       and `genome.index.star` on `star/genomegenerate`, and the *only* thing separating them is
       which tool is being drafted.
    4. **The type shares a namespace with something the module consumes.** A tool that takes an
       `alignment.bam` tends to emit another `alignment.*`. Inputs only, and only for outputs —
       an input cannot be justified by itself.

    **What was tried and is deliberately absent: popularity.** Ranking by how many contracts
    already carry a type is the obvious fifth signal and it is a trap here — it would rank the
    common types up in every hole regardless of the question, which is the *alphabetical*
    failure with a different sort key. If it is ever added it must use `excluding`, for the
    reason `_played_by` gives.
    """
    if port is None:
        return 0
    segments = type_name.split(".")
    score = 0
    if port == segments[-1]:
        score += 30
    if port in segments:
        score += 20
    if tool and any(segment in tool.split("/") for segment in segments):
        score += 20
    if any(segments[0] == other.split(".")[0] for other in input_types):
        score += 10
    return score
```

- [x] **Step 2: Sort the `type_id` branch by it**

Replace the `type_id` branch body (currently `candidates.py:37-42`) with:

```python
    if base.endswith("type_id"):
        carried = _carried_by(stack, excluding)
        # **Ranked, not alphabetical.** `sorted(stack.vocabulary.types)` is what shipped until
        # now, and it put the right answer first in one hole out of thirty — for a port called
        # `fa` on SAMTOOLS_FAIDX it offered `genome.fasta` and `measurement.rrna_fraction` with
        # equal prominence. `name` had this treatment already; `type_id` never got it.
        #
        # Name is the tiebreak, so the order is total and the forge stays deterministic.
        ranked = sorted(
            stack.vocabulary.types,
            key=lambda name: (-_fit(name, port, tool, input_types), name),
        )
        return [
            Candidate(value=name, note=_note("declared type", carried.get(name, ())))
            for name in ranked
        ]
```

- [x] **Step 3: Run the harness and read the number**

Run: `uv run pytest packages/mendel-forge/tests/test_candidate_ranking.py -v`

Expected: PASS. If it fails, the assertion prints the actual percentage — do not lower `TARGET`
to make it pass. Adjust the weights, re-run, and record what you tried in the execution record,
the way the `name` branch's comments do.

- [x] **Step 4: Confirm nothing else regressed**

Run: `uv run pytest packages/mendel-forge packages/mendel-api -q`

Expected: PASS. The four new arguments are all defaulted, so every existing call site is
unchanged — if something fails here, a call site was passing positionally.

- [x] **Step 5: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/candidates.py
git commit -m "feat(forge): rank type candidates by the port that is asking"
```

### Task 1.3: forward the port from the call site

The port name is already at the call site — `assemble.py:197` passes `port=offered[0]` and
`assemble.py:214` passes `port=emit` — and `_hole` uses it **only** for `_evidence_for`. The
ranking signal is present and discarded.

- [x] **Step 1: Write the failing test**

Create `packages/mendel-forge/tests/test_hole_ranking.py`:

```python
"""The port a hole is about must reach the candidates it offers.

`_hole` has taken a `port` since Phase 2 and spent it only on evidence. Scoring needs it too,
and a hole whose candidates are unranked is the whole of what made the forge unanswerable.
"""

from pathlib import Path

from mendel_resolver.layers import load

from mendel_forge import assemble, sources
from mendel_forge.sources import ToolRef

ROOT = Path(__file__).resolve().parents[3]


def _scaffold(ident: str, version: str):
    """The same chain `ops.draft` runs, minus the workspace write.

    Verified against `ops.py:253-255` rather than guessed: the source method is `ingest` and it
    takes a `ToolRef` plus a root, and `scaffold_for` names its keyword `ident`, not `name`.
    """
    ref = ToolRef(source="nf-core", ident=ident)
    observation = sources.get(ref.source).ingest(ref, ROOT / "vendor")
    stack = load([ROOT / "registry"])
    return assemble.scaffold_for(
        observation, stack, ident=f"{ref.source}/{ref.ident}", version=version
    )


def test_a_produces_hole_offers_its_own_type_first() -> None:
    scaffold = _scaffold("samtools/faidx", "1.21.0")

    # `SAMTOOLS_FAIDX` emits a port called `fa`. The answer is `genome.fasta` and nothing else
    # in the vocabulary is close — but alphabetical order buried it sixth among twenty-two.
    hole = next(h for h in scaffold.holes if h.subject == "produces[0].type_id")
    assert hole.candidates[0].value == "genome.fasta"
```

- [x] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_hole_ranking.py -v`

Expected: FAIL, asserting some other type is first — most likely `alignment.bai`, the
alphabetically first entry.

**The call chain in `_scaffold` was verified against `ops.py:253-255`** while writing this plan,
and three names in the first draft were wrong: the source method is `ingest` (not `read`), it
takes a `ToolRef` and a root (not a string), and `scaffold_for` names its keyword `ident` (not
`name`). If it still disagrees, read `ops.draft` and correct the test rather than the source.

- [x] **Step 3: Forward `port` and the two new facts through `_hole`**

In `packages/mendel-forge/src/mendel_forge/assemble.py`, in `_hole` (line ~71), change the
`candidates.for_field` call to pass the port through:

```python
        candidates=candidates.for_field(
            field, stack, type_id=type_id, excluding=excluding,
            port=port, tool=excluding, input_types=input_types,
        ),
```

and add `input_types: tuple[str, ...] = ()` to `_hole`'s keyword arguments.

**`tool=excluding` is not a mistake and needs the comment**, because it reads like one:

```python
    # `excluding` is the module key of the tool being drafted — the same string the ranking
    # needs to know which tool is asking. They are one fact used twice, not two parameters that
    # happen to agree, and giving the scorer its own would let them drift apart silently.
```

- [x] **Step 4: Pass the consumed types to the `produces` holes**

In the `emits` loop (`assemble.py:203-216`), the input types are not yet known — the `consumes`
type_id holes are still open at draft time. **So `input_types` is empty on a fresh draft and
fills in on re-scaffold**, which is exactly how `after=` already works for the name holes.

Add to the `produces` `_hole` call:

```python
                input_types=tuple(
                    filled[f"consumes[{i}].type_id"].value
                    for i in range(len(obs.fact("consumes") or []))
                    if f"consumes[{i}].type_id" in filled
                ),
```

- [x] **Step 5: Run both tests**

Run: `uv run pytest packages/mendel-forge/tests/test_hole_ranking.py packages/mendel-forge/tests/test_candidate_ranking.py -v`

Expected: both PASS.

- [x] **Step 6: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/assemble.py packages/mendel-forge/tests/test_hole_ranking.py
git commit -m "feat(forge): the port a hole is about reaches its candidates"
```

### Task 1.4: write the producer for `suggested`

- [x] **Step 1: Write the failing test**

Create `packages/mendel-api/tests/test_suggested.py`:

```python
"""`suggested` had every consumer and no producer.

It crosses the API, is keyed on by `aggregate()`, sorted on by the queue's ordering, highlighted
by `Question.tsx`, and switches `QueueRow`'s label from *Ask* to *Confirm* — and every
`suggested=` in the repository was in a test. This is the producer.
"""

from comeni_core.review import Candidate
from mendel_forge.scaffold import Hole

from mendel_api.questions import _ask


def test_the_top_candidate_is_what_is_suggested() -> None:
    hole = Hole(
        subject="produces[0].type_id",
        what="the semantic type of the output the module emits as fa",
        why_open="the semantic type exists only in the English description",
        candidates=[Candidate(value="genome.fasta"), Candidate(value="alignment.bam")],
    )
    assert _ask(hole, draft="faidx").suggested == "genome.fasta"


def test_a_hole_with_no_candidates_suggests_nothing() -> None:
    # Free text — `priority_because` is the live case. A suggestion there would be an invention,
    # which is the one thing the forge must never do (invariant 2).
    hole = Hole(subject="priority_because", what="why this ranks where it does", why_open="a judgement")
    assert _ask(hole, draft="faidx").suggested is None
```

- [x] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-api/tests/test_suggested.py -v`

Expected: FAIL — `assert None == 'genome.fasta'`. That failure **is** finding §1.5: the field
exists, everything reads it, nothing writes it.

- [x] **Step 3: Set it in `_ask`**

In `packages/mendel-api/src/mendel_api/questions.py`, inside `_ask`'s `OpenQuestion(...)` call
(line ~146), add:

```python
        # **The producer this field never had.** `suggested` is read by `aggregate()`, by the
        # queue's ordering, by `Question.tsx`'s highlight and by `QueueRow`'s Ask/Confirm label —
        # and until now every `suggested=` in the repository was in a test, so the Confirm branch
        # was unreachable and the "Ask before Confirm" sort was a no-op.
        #
        # `candidates[0]` is the suggestion because `for_field` returns them ranked. A free-text
        # hole has none and suggests nothing rather than inventing one.
        suggested=hole.candidates[0].value if hole.candidates else None,
```

- [x] **Step 4: Run the test, then the whole API suite**

Run: `uv run pytest packages/mendel-api -q`

Expected: PASS. **Watch `test_aggregate.py` and `test_band_order.py` especially** — they are the
only files that ever set `suggested`, and they now describe live behaviour rather than a
hypothetical.

- [x] **Step 5: Watch the Confirm branch become reachable**

Run: `make client && cd frontend && npx vitest run && npm run build`

Expected: all pass. Then check by hand that a queue row for a ranked hole now reads **Confirm**
rather than **Ask** — that label has been unreachable since it was written.

- [x] **Step 6: Commit**

```bash
git add packages/mendel-api frontend/src/api
git commit -m "feat(api): write the producer suggested never had"
```

### Task 1.4 execution record

| step | as written? | what happened |
|---|---|---|
| 1–2 | **no — wrong function name** | The projection is `question_from_hole`, not `_ask`. Corrected the test against the code. It then failed with `assert None == 'genome.fasta'`, which **is** finding §1.5. |
| 3 | **no — the plan's version shipped a defect** | See below. |
| 4–6 | yes | 369 tests, 73 frontend, build green. |

**Step 5 did what step 5 is for, and it caught a defect the plan itself contained.** Rendering a
real draft showed the Confirm branch reachable — and reachable on the *wrong* holes.
`suggested=hole.candidates[0].value` is what the plan told me to write, and for `samtools/faidx`
it labelled `sizes`, `fai`, `gzi` and `versions_samtools` **Confirm** and offered
`alignment.bai` for all four. Those ports' names say nothing about a type, every candidate scores
0, and the list falls back to alphabetical — so the change turned a screen that honestly said
*Ask* into one inviting a person to accept the alphabet.

**That is the tier-4 mistake in a different costume.** Invariant 6 flags an ambiguous decision
even at high model confidence, for exactly this reason: a suggestion with no evidence behind it
must not be dressed as one with. `candidates.suggestion()` now returns the top value only when
`_fit` scored it above zero, `Hole.suggested` carries it, and `question_from_hole` projects
rather than recomputes. Two holes now say Confirm on that draft and both are right; the other
nine say Ask.

**`test_a_hole_keeps_what_is_genuinely_its_own` made me justify where the field lives**, which is
what that guard is for. `suggested` is on `Hole`, not on the shared `Question` base: the resolver
ranks candidates too (invariant 8 orders ties by `(surplus, -priority, id)`), so the field would
compile there and read as natural — and invariant 6 is exactly what it would erode. On the forge
side it is safe for a reason that does not transfer, invariant 2: a hole is approved by a human
offline, before anything resolves.

**Known and not fixed:** `consumes[N].name` holes still say Ask. They are built inline rather
than through `_hole`, and before their type is answered they offer only channel names — which
Phase 2's own comments record as the case where the single candidate was wrong. Ask is therefore
*true* there. Not a regression (`suggested` was `None` everywhere before) and not this phase's
job.

### Task 1.5: close the phase

- [x] **Step 1: `make verify`** — unpiped, so the exit code is `make`'s and not `tail`'s.
- [x] **Step 2: Record the measured number** in the execution record: top-1 before, after, and
      anything tried and rejected.
- [ ] **Step 3: Commit**

### Task 1.3 execution record

| step | as written? | what happened |
|---|---|---|
| 1–3 | yes | The verified `ingest`/`ToolRef`/`ident=` chain worked first time. Test failed with `alignment.bai` — alphabetically first — exactly as predicted. |
| 4 | **no — the step was deleted** | `input_types` was measured at **0 gain** (25/30 with and without) and is structurally unusable where it was wanted: at draft time every `consumes[N].type_id` is still an open hole, so there is nothing to read. The fact is also `input_names`, not `consumes`. Signal 4 was removed from `_fit` rather than plumbed. |
| 5 | **no — two runs** | Forwarding `port` did not fix the test. `samtools/faidx` **is not in the registry**, and its port is `fa` — an *abbreviation* of `fasta`, not a segment — so every candidate tied at 0. Added signal 2b, prefix matching. |
| 6 | yes | |

**A golden file caught it, which is what they are for.** `nf-core-fastqc.scaffold.json` moved and
was regenerated with `FORGE_GOLDEN=update` and then *read*, as its own docstring demands. What
reading it showed: `consumes[0]` (port `reads`) now offers `fastq.reads` first, and
`produces[0..2]` — ports `html`, `zip`, `versions_fastqc` — are unchanged from alphabetical,
because those names say nothing about a type. **That is the honest shape of this change: it helps
where the port name carries meaning, does nothing where it does not, and never makes a hole
worse**, since a tie falls back to exactly today's order. The five misses in 25/30 are all of
this kind.

**The 2b decision is the interesting one and is deliberately inconsistent with the 1.3.4 one.**
Both measure 0 on the corpus; one was deleted and one kept. The difference is *why* they measure
zero: signal 4 has no input to read at draft time and never will, while 2b's case — an undrafted
tool — is simply absent from a corpus made of landed contracts. **The corpus cannot measure the
tools the forge exists to draft**, and that is a limit of the measurement rather than a licence
to add whatever. It is written into the docstring so the next person weighs it rather than
inherits it.

---

## Phase 2: give `priority_because` a question

**Files:** Modify `packages/mendel-forge/src/mendel_forge/assemble.py:232`

- [x] **Step 1: Write the failing test**

Append to `packages/mendel-forge/tests/test_hole_ranking.py`:

```python
def test_every_hole_asks_something() -> None:
    """`assemble.py:86`'s own comment complains about this string; one hole still uses it."""
    scaffold = _scaffold("samtools/faidx", "1.21.0")
    for hole in scaffold.holes:
        assert not hole.what.startswith("a value for"), hole.subject
```

- [x] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_hole_ranking.py::test_every_hole_asks_something -v`

Expected: FAIL on `priority_because`.

- [x] **Step 3: Give it a `what`**

In `assemble.py`, change line 232 to:

```python
    holes.append(
        _hole(
            "priority_because",
            stack,
            obs,
            why=_WHY_OPEN["priority_because"],
            what=(
                "why this contract should be preferred over another that produces the same "
                "type — routing ranks candidates by priority, and this is the sentence a "
                "reviewer reads when it does"
            ),
        )
    )
```

- [x] **Step 4: Run it, then `make check`. Commit.**

```bash
git add packages/mendel-forge
git commit -m "fix(forge): priority_because asks a question instead of naming itself"
```

### Phase 2 execution record

Carried out as written. The golden file moved by exactly one line and it is the question.

**`make verify` exited 2 the first time, and it was lint, not tests** — `ruff` I001 on the new
test's imports plus an E501 my own docstring edit had mangled into a duplicated fragment. Worth
recording because the plan's step says *run it unpiped so the exit code is `make`'s*: piping to
`tail` would have shown a wall of passing tests and hidden a non-zero exit entirely, which is
the mistake 3B's Task 3 made.

---

## Phase 3: one Tools page

**Why after 1–2:** a denser board over unranked candidates renders an unanswerable question
faster. Spec §7.

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/tools.py`
- Create: `packages/mendel-api/src/mendel_api/routes/tools.py`
- Create: `packages/mendel-api/tests/test_tools.py`
- Create: `frontend/src/forge/Tools.tsx`, `frontend/src/forge/Tools.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/src/app/Shell.tsx`
- Delete: `frontend/src/forge/Sources.tsx`, `Contracts.tsx` and their tests, **and** the API
  services and routes behind them **only if nothing else consumes them** — check
  `attention.py`, which calls both.

**Interfaces:**
- Produces: `GET /api/tools?state=&against=&q=` → `Board`:

```python
class ToolRow(BaseModel):
    ref: str                      # `nf-core:samtools/faidx`
    tool: str                     # `samtools/faidx` — what a person reads
    state: State                  # undrafted | drafted | landed
    status: Status | None = None  # matching | unverifiable | drifted; None unless landed
    consumes: list[str] = []      # type ids — what a decision actually needs
    produces: list[str] = []
    open_questions: int = 0
    contract_id: str | None = None
    draft: str | None = None

class Board(BaseModel):
    rows: list[ToolRow]
    counts: dict[str, int]        # state -> n, over everything, never the filtered view
    status_counts: dict[str, int]
    known: int | None = None      # None until #77; renders `—`, never 0
    sources: list[str]
    checked_at: datetime | None = None
```

### Task 3.1: the service

- [x] **Step 1: Write the failing test**

Create `packages/mendel-api/tests/test_tools.py`:

```python
"""Sources and Contracts were one query at two stages of one object's life.

Both screens carried a `Facets` component with the same docstring, written twice. A tool moves
undrafted -> drafted -> landed, and `status` is a property of the last stage only.
"""

from mendel_api.services import tools


def test_a_landed_tool_carries_its_status_and_its_ports() -> None:
    board = tools.board()
    landed = [r for r in board.rows if r.state == "landed"]
    assert landed, "the registry has twelve contracts"
    row = landed[0]
    assert row.status is not None, "a landed tool has been checked or is unverifiable"
    # **The field the old row omitted.** `status | id | roles` spent 180px on `roles`, which
    # helps nobody choose a tool; what it consumes and produces is what a decision needs.
    assert row.consumes or row.produces


def test_an_undrafted_tool_has_no_status() -> None:
    board = tools.board()
    for row in board.rows:
        if row.state == "undrafted":
            assert row.status is None, "nothing has been checked, so nothing may claim a status"


def test_the_known_total_is_absent_rather_than_wrong() -> None:
    # Issue #77 — discovery reads `vendor/modules/`, so the size of the known world is unknown.
    # `13` presented as that size is a lie; `None` renders `—`. Same discipline as
    # `pipeline_pins: None`.
    assert tools.board().known is None


def test_counts_are_over_everything_not_the_filtered_view() -> None:
    everything = tools.board()
    filtered = tools.board(state="landed")
    assert filtered.counts == everything.counts
    assert len(filtered.rows) < len(everything.rows)
```

- [x] **Step 2: Run and watch it fail** — `ModuleNotFoundError: mendel_api.services.tools`.

- [x] **Step 3: Write `services/tools.py`**

Compose it from the two existing services rather than re-deriving: `sources.catalogue()` already
computes state and `contracts.listing()` already computes status, and **both are cached on the
registry digest** (phase 7's `@lru_cache`), so calling both costs one load rather than two.

Join on the **module key** — `sources._module_key` already exists and is the contract id minus
`@version`, which is what invariant 11 keys displacement on.

Read the ports off `stack.registry.contracts[...]` for landed rows; leave them empty otherwise.

Set `known=None` with the reason in a docstring citing #77.

- [x] **Step 4: Run the tests. Then add the route** in `routes/tools.py`, registered **before**
      any catch-all path — the greedy `/{id:path}` defect cost a phase once.

- [x] **Step 5: `make client`, then commit.**

### Task 3.1 execution record

| step | as written? | what happened |
|---|---|---|
| 1–2 | yes | |
| 3 | **no — `Board.checked_at` was dropped** | `CheckResult` has no `checked_at`; the health strip reads `SourceCheck.ran_at` from the database, written by the nightly worker. That is a *different fact* from `checked.result()`, which is a check computed now. Carrying it on the board would have forced a choice between two truths and let the board and the health strip disagree about one sentence. The page reads both endpoints — each is O(1) and cached on the registry digest. |
| 4 | yes, plus a guard | `test_every_operation_is_named_by_hand` holds a literal list of every operation and refused the new one until it was added by hand. That is the guard working: `listTools` is in the list with a note that `listSources`/`listContracts` become dead routes when Task 3.2 deletes their screens. |
| 5 | yes | |

**One design point the plan did not anticipate: the join is a union, not a lookup.**
`sources.catalogue()` walks what a source can *discover*, so composing the board by iterating it
would silently drop any contract whose module is not in `vendor/` — hand-written, or removed
upstream. Those are exactly the rows a person most needs, because they are the ones nothing can
re-read. `test_a_landed_contract_appears_even_if_no_source_can_discover_it` holds it.

### Task 3.2: the page

- [ ] **Step 1: Write the failing test** (`frontend/src/forge/Tools.test.tsx`) asserting a landed
      row renders `consumes → produces` and its status, an undrafted row renders neither, and the
      list is one component for both — `queryAllByTestId("tool-row")` covers every state.
- [ ] **Step 2: Run it, watch it fail.**
- [ ] **Step 3: Build `Tools.tsx`** — a single row component, ~32px, `consumes → produces` in
      `font-data`, status as a coloured dot not a 110px word. Filter chips for state and status,
      a text filter above ~50 rows.
- [ ] **Step 4: Virtualise above 200 rows** — and put the number in a test, not a comment, so
      #77 landing cannot silently break it.
- [ ] **Step 5: Repoint the router**, redirect `/forge/sources` and `/forge/contracts` to
      `/forge/tools` with the matching filter, so every existing link survives.
- [ ] **Step 6: Delete `Sources.tsx`, `Contracts.tsx` and their tests.** Check `attention.py`
      first — it consumes both services and must be repointed, not orphaned.
- [ ] **Step 7: `npx vitest run && npm run build`, `make verify`, commit.**

---

## Phase 4: the status board

> **Correct this phase against phase 3's real `Board` before executing it.** It is written
> against the shape declared above, and phase 3 will change it — `notes/README.md` records that
> writing later phases against types that do not exist is what killed Plan 2.

**Files:** Create `frontend/src/forge/Board.tsx`; modify `Tools.tsx` to mount it.

- [ ] **Step 1: Write the failing test** — the board renders `—` for `known` when it is `null`,
      and never `0`; each figure is a link to the filter that produces it; the cell strip has one
      cell per landed contract.
- [ ] **Step 2: Run it, watch it fail.**
- [ ] **Step 3: Build it.** One question — *is everything okay?* Registry agreement as a bar plus
      one cell per contract; catalogue coverage; when it was last checked. Nothing is a list.
      Reuse the certainty strokes from `home/Standing.tsx` rather than inventing a second
      language — extract the `STROKE` map into `ui/` if both need it.
- [ ] **Step 4: Watch the `—` guard fail** by returning `known=0`.
- [ ] **Step 5: `npm run build`, `make verify`, commit.**

---

## Phase 5: help, and the glossary

**Independent of 1–4** and can be executed at any point after phase 3 names the screens.

**Files:** Create `frontend/src/ui/Glossary.tsx`, `frontend/src/ui/Term.tsx`,
`docs/reference/glossary.md`; modify `ui/States.tsx`.

- [ ] **Step 1: Write `docs/reference/glossary.md`** — eight terms, one sentence each:
      **contract, role, type, measurement, drift, hole, band, proposal**. Each links to the
      reference page that defines it fully.
- [ ] **Step 2: Write the failing test** — every term the UI renders through `<Term>` exists in
      the glossary, and the glossary has no term nothing uses. **Both directions**, the same
      shape as the diagnostics guard: declared-but-never-emitted is as much a defect as the
      reverse.
- [ ] **Step 3: Run it, watch it fail.**
- [ ] **Step 4: Build `<Term>`** — the word, underlined on hover, opening the glossary at that
      entry. `?` opens it anywhere.
- [ ] **Step 5: Rewrite every `Empty`** so it explains the *screen*, not the filter. Today's
      contracts empty state says *"Clear the facet to see every contract"*, which assumes you
      know what a contract is.
- [ ] **Step 6: Show `why_open` once per kind of question**, collapsed after. Seven identical
      rationales read as boilerplate by the second.
- [ ] **Step 7: `make links`, `npm run build`, `make verify`, commit.**

---

## Phase 6: the landing page, revisited

> **Do not start this until 1–5 are merged.** It points at these screens; designing it first is
> the mistake 3B made and the operator named.

**Files:** Modify `frontend/src/home/Home.tsx`, `home/Standing.tsx`, `services/attention.py`.

- [ ] **Step 1: Re-read the page against the screens that now exist.** Its *Where to go* block
      names Queue, Contracts and Sources — two of which no longer exist as destinations.
- [ ] **Step 2: Repoint `attention.py`** at `services/tools.py` so the front door and the board
      cannot disagree about what is open.
- [ ] **Step 3: Decide whether `Standing` survives** now that the board says the same thing
      better. If it does not, delete it and its tests — do not leave it rendering a second
      answer to one question.
- [ ] **Step 4: Look at it in a browser** — both `:5173` and `:80`. **This step is the
      operator's**, and 3B shipped without it.
- [ ] **Step 5: `make verify`, journal, indexes, commit.**

---

## Self-review

**Spec coverage:**

| spec section | phase |
|---|---|
| §1.1 candidates unranked | 1 |
| §1.2 alphabetical discards the one signal | 1.2 |
| §1.3 three screens, one axis | 3 |
| §1.4 no help anywhere | 5 |
| §1.5 `suggested` has no producer | 1.4 |
| §1.6 `priority_because` placeholder | 2 |
| §3 the shape | 3, 4 |
| §3.3 `known` renders `—` | 3.1, 4 |
| §4 narrow the candidates | 1 |
| §5 help as a surface | 5 |
| §7 the order | the phase order itself |
| §8 open questions | **not covered — decisions, not tasks.** Answer them during phase 3. |

**Known gaps, stated rather than hidden:**

- **Phases 4 and 6 are less detailed than 1–3**, because they are written against a `Board` that
  phase 3 creates. Correct them before executing; do not execute them as written.
- **`ops.draft`'s exact ingest chain was verified** and three names in the first draft of Task
  1.3 were wrong. `sources.get(...).ingest(ToolRef, root)` and `scaffold_for(..., ident=,
  version=)` are the real ones and the plan now uses them.
- **`_hole` does not currently take `input_types`.** Task 1.3 Step 4 adds it; if the `emits` loop
  has moved, find the `produces[N].type_id` construction rather than trusting the line number.
- **Spec §8's three open questions** — whether `Forge` survives as a nav item, where the registry
  lookup lives, whether `roles` earns a column — are decisions for phase 3 and have no task.
