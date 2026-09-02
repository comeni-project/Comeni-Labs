# Walking the builder — 2026-08-23

The second half of 2026-08-23. [The morning](2026-08-23-the-builder-is-a-builder.md) executed
Plan 3E and reported it complete against a green `make verify`. **Then the operator used it**,
and found nine things in about twenty minutes.

This entry is about those nine, because the gap between *the plan is done* and *the thing works*
is the useful part.

## What using it found that testing it did not

| what they said | what it was |
|---|---|
| "you can't detach modules from one another" | `disconnect` had existed since Task 9 and **nothing called it**. No affordance on a wire at all |
| "lines don't line up, if one has multiple inputs" | a real Plan 3C layout bug: **39px onto nothing** |
| "you cannot drag modules into the builder" | 3C removed the fake `draggable`; 3E never added a real one |
| "you cannot tune parameters at all" | the settings card was a record. It is also why the review rail was useless |
| "'problems' shows no problem" | correct behaviour, and the complaint was still right — see below |
| "flickering on every change and drag" | the canvas re-rendered from the server on every edit |
| "text gets highlighted when dragging" | no `select-none` |
| "lines cross each other" | a second layout bug, on the **canonical spine** |
| "pending is not defined" | HMR poisoning, and I misdiagnosed it twice |

**Every one of these was invisible to `make verify`.** 1497 tests, `tsc` green, the emitted
Nextflow byte-identical — and you could not remove a wire.

## The reframe that made it one problem

*"Problems shows no problem"* looked like a bug and was not: the example spine validates clean,
0 findings, and the tab correctly says so. The complaint was still right, and restating it is
what turned nine bugs into one:

> **The screen told you what needed deciding and gave you no way to decide anything.**

Review said *1 to decide* about `star_align.seq_platform` with no way to answer it. Problems could
only ever be empty because nothing could break the graph. Settings showed values you could not
change. Four surfaces, one defect.

## The two layout bugs, because both were in code that shipped

**Wires missed their chevrons by 39px.** `layout.py` anchored a wire using the ports that *have
wires*, in edge order. The canvas draws every port the *contract declares*, in contract order.
Same `portX(width, count, i)` in both; what differed was the `count`. For `featurecounts` — two
declared inputs, one wired — the chevron sat at x=77 and the wire ended at x=116. `_height` had
it too, so a node with three declared inputs and one wire was sized for **one** port row and the
other two chevrons sat on the node's own text.

**They agreed only when a node was fully wired**, which is why it survived a whole plan.

**The canonical spine had crossing wires.** `_order`'s own docstring said it: *"it is not a
crossing-minimisation algorithm. If a graph ever arrives where it is visibly wrong, the honest
fix is a real ordering pass, not more passes of this one."* The shipped spine is that graph.
`star_align` declares `reads`, `index`, `gtf`; both its producers are roots, so the downward pass
had no opinion and they sorted by id — `star_genomegenerate` left feeding `index` (middle),
`trimgalore` right feeding `reads` (left). Crossed on every render of the pipeline this project
is built around.

An upward pass now orders a rank by where its consumers' ports are — the ordinary Sugiyama
alternation. It is **still not a general minimiser**, and the test asserts only the local rule:
for two wires into one node, the one whose source is further left must land on the further-left
port.

## The flicker was architectural, not a setting

Every edit made a new React Query key, `data` went `undefined` until it resolved, and the whole
graph unmounted and remounted. Underneath that, three deeper things:

- **The canvas rendered the server's node list**, so adding or deleting a step did not change the
  picture until a round trip returned.
- **Positions were `placed.x + offset.x`** — a server coordinate plus a drag delta — so a node
  the server had not laid out *had nowhere to be*.
- **Wires rendered the server's points**, so the graph came apart under the hand and snapped back
  after the round trip.

**The split that resolved it: the server seeds, the client owns.** Layout stays in Python for the
canonical arrangement — `CLAUDE.md`'s reason holds, two people reading one artifact must see one
graph — and a node takes the server's coordinates *once*. From the first drag the client's
position wins, and `geometry.ts` computes wire elbows from live positions. What is not Python's
job is where a box sits while you are dragging it.

`tidy()` throws the client's positions away and takes the server's again: the deterministic
arrangement **on demand** rather than on every gesture. **It has no button yet.**

## Two guards earned themselves, and one had never worked

**`MD0220` refused the first editable-settings implementation.** A param decision must be keyed
`<node>.<param>` with no prefix, because that is what `Pipeline` looks up to confirm a value
claiming `source: human` is backed by a person actually answering it. A prefixed key is a
decision the artifact cannot find, which makes the value a review cleared by assertion —
precisely what that code exists to refuse. It refused it the first time it ran.

**`test_every_configured_root_is_absolute_in_the_compose_file`** caught `MENDEL_DRAFT_ROOT`. Its
docstring predicted it by name: *"a new `MENDEL_*_ROOT` default that nothing overrides will fail
here."*

**And the frontend typecheck had never checked anything.** `frontend/tsconfig.json` has
`"files": []` and only references the two project configs, so `npx tsc --noEmit` — what CI ran,
and what I reported "tsc clean" from repeatedly during Plan 3E — type-checks **nothing** and
exits 0 unconditionally. Watched failing with a file assigning a string to a `number`; recorded
in [`../audits/guard-ledger.md`](../audits/guard-ledger.md). CI runs `tsc -b` now.

Three real type errors had reached a Docker build behind it. The generalisable part is in the
ledger: **a guard invoking a tool with the wrong arguments reports success rather than an error,
so it is invisible to the very failure it exists to catch.**

## What I got wrong

**I misdiagnosed the last bug twice.** *"pending is not defined"* — I checked timestamps, found
the erroring module was compiled 19ms before my final edit, and concluded *stale, just reload*.
It then reproduced after a restart, so I nearly called it real. Both readings were wrong: my
`rm` of the Vite log kept failing (exit 144) and I was reading the **old file** each time.

The actual message, once I read a genuinely fresh log, was *"React has detected a change in the
order of Hooks called by `Editing`"* — I added a `useState` and a `useEffect` to a component
while HMR was live, Fast Refresh cannot preserve a component whose hook list changed, and the
error boundary caught it without recovering. The source was never broken: `npm run build`
succeeds and 182 tests mount that component.

**Twice I told the operator something confident and wrong before checking properly.** The fix is
not more caution in the prose; it is checking that the file I am reading is the one being
written.

## Traps

- **Editing a component's hooks while HMR is live poisons the page.** Build green, types green,
  tests green, app broken — because the breakage is in the browser's fiber, not the code.
  Restart Vite and hard-reload after adding a hook; do not leave the operator to find it.
- **`npx tsc --noEmit` in `frontend/` checks nothing.** It is `tsc -b`.
- **`addNode` minting ids from `graph` collides under batching.** Two adds in one handler both
  read the same state and both minted `star_align_1`. A ref updated synchronously is the fix, and
  the tests caught it the moment `addNode` started returning its id.
- **A layout test can pass for the wrong reason.** The crossing test passed at first because
  `of(spine)` without declared ports uses the wired-port fallback, where the two orders coincide.
- **A 1.5px stroke is a 1.5px hit target.** Wires needed a 14px invisible path before a hand
  could hit one.
- **Generated schema names are not stable.** FastAPI splits a model into `-Input`/`-Output` when
  optionality differs and merges them back when it does not, so `DraftGraph` was
  `DraftGraph-Input` for one commit and `DraftGraph` the next. `frontend/src/api/types.ts` is the
  one import site now.

## What is next

1. **`tidy()` has no button.** The hook can take the canonical layout back; nothing calls it.
2. **Keeping-yours records nothing.** `Compare`'s *keep mine* holds its reason in component
   state; writing it to `ProducerDecision.human_override` needs an override endpoint.
3. **The forge**, which the operator is redesigning. Untouched by any of this.
4. **Nothing here was walked a second time.** These nine came from twenty minutes of use; the
   honest expectation is that another twenty finds more.
