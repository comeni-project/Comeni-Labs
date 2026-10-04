# Characteriser 3 — the card — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The person sees the AI read their sample. The upload card accepts any file and says what may go to the AI; while the AI reads, it waits and says so; then it shows what was read, labelled *read by AI*, or why nothing was. A type the engine reads is sent again by itself and measured.

**Architecture:** A design pass first, adding the reading states to the published canvas *Uploading a sample*, approved by the operator before any component code. Then: the session poll waits on a pending reading (`isWaiting`); `SampleUpload` takes the question's `reading` and draws each state of spec §9; it re-sends the files once on `hand_back`; with no files (after a reload) it offers *Measure as …*. The goal card's *read by AI* label already exists and gets a test. Screenshots are compared to the artboards before the plan closes.

**Tech Stack:** React 19, TanStack Query, Tailwind 4, vitest + Testing Library, puppeteer-core for screenshots.

**Spec:** `docs/superpowers/specs/2026-10-04-the-characteriser-design.md` §8, §9. Part 14.7.7.3 of #135. Depends on plan 2 (the `reading` block, the `reading` outcome, and `make client` run).

## Global Constraints

- **Design first:** no component code before the operator approves the artboards.
- The line under the picker is, verbatim: *only the first 4 MB is read, on this server · if nothing here reads its type, about 8 KB of its text goes to the AI to read* (spec §9).
- Every model-read fact is labelled **read by AI**, never *measured* (protocol rule 3).
- `frontend/src/api/` is generated (`make client`), never hand-edited.
- Cite issues in UI comments as *issue 135*, never `#135`.
- Layout bugs are invisible to jsdom: screenshot, and compare in one viewport (`.design/_compare.html`).
- `cd frontend && npx vitest run && npx tsc -b` (never `tsc --noEmit`); `make check` before each commit.

## Review Focus

1. **The reading lands while the tab is hidden** (issue 230: TanStack does not poll a hidden tab). On return the card shows the reading, not *being read by AI…* forever. Pinned in Task 2 by refetching on focus.
2. **The hand-back re-sends once, never in a loop.** A second `hand_back` snapshot for the same attempt sends nothing. Pinned in Task 3.
3. **A reading that answered the question**: the card is replaced by the next question, and the log row says the answer came from the AI. Pinned in Task 3.
4. **A 403 (above level 0) or a 409 (MI0215) on upload** shows the server's sentence and leaves the card usable, as today's refusals do. Pinned in Task 3.
5. **A phone at 390 px**: the reading's lines wrap, never scroll sideways. Pinned in Task 4 by screenshot.

---

## File structure

| File | Responsibility |
|---|---|
| The published canvas *Uploading a sample* ([DEhSpA4k](https://claude.ai/artifact/DEhSpA4kEZPvq9soyapJTM)) | a page *Read by AI*, its artboards |
| Modify `.design/README.md` | the canvas row says it holds the reading states |
| Modify `frontend/src/build/living/authoringReducer.ts` (`isWaiting`) | a pending reading keeps the poll |
| Modify `frontend/src/build/living/useAuthoringSession.ts` | refetch on window focus |
| Modify `frontend/src/build/living/blocks/SampleUpload.tsx` | the reading's states; the re-send; *Measure as …*; any file; the new line |
| Modify `frontend/src/build/living/blocks/GapCard.tsx` | pass `reading`; the other answers wait while it is pending |
| Modify `packages/mendel-api/src/mendel_api/services/authoring.py` (`_answer_of`) | the log row for an answer the AI read |
| Tests: `frontend/src/build/living/SampleUpload.test.tsx`, `authoringReducer.test.ts`, `GapCard.test.tsx`, `Collection.test.tsx` (goal card), `packages/mendel-api/tests/test_characterise_reading.py` | |

---

### Task 1: The artboards — STOP for approval

**Files:** the published canvas; `.design/README.md`.

- [x] **Step 1: Open the canvas and read what is there**

Read the canvas with `Artifact` `action: "read"` on `https://claude.ai/artifact/DEhSpA4kEZPvq9soyapJTM`, and read `frontend/src/build/living/blocks/SampleUpload.tsx` as it stands after plan 2. The new artboards continue that canvas's look; they do not start a new one.

- [x] **Step 2: Draw the reading's artboards**

Add a page *Read by AI*, with the gap *This analysis needs a reference genome (genome.fasta)* as the example. One artboard per row of spec §9's table, on a desk:

1. picked `ref.fa.gz`, with the new line under the picker;
2. ● *being read by AI…*;
3. read and answered: the log row above the next question, *genome.fasta · read by AI*;
4. read, question stays: `alignment.bam` · read by AI, `coordinate_sorted` · read by AI;
5. handed back: *read by AI: FASTQ reads → measuring…*, then the measured result with *type read by AI*;
6. handed back, files gone: *looks like FASTQ reads*, **Measure as FASTQ**;
7. the AI couldn't tell;
8. refused at admission;
9. the AI didn't answer, **Measure again**;

and states 2 and 4 again on a phone (390 px). The goal card with one *read by AI* input and one *read by AI* fact.

- [x] **Step 3: STOP — the operator approves the artboards**

Publish, give the operator the link, and wait. Record what they change in the execution record.

- [x] **Step 4: The README row, then commit**

In `.design/README.md`, change the *uploading a sample* row's text to add: *and, since 2026-10, the AI's reading (14.7.7): nine artboards on a desk, two on a phone*. Run `make links doc-paths`.

```bash
git add .design/README.md && git commit -m "docs(design): the AI's reading on the upload canvas (#135)"
```

---

### Task 2: The poll waits on a reading, and sees it on return

**Files:**
- Modify: `frontend/src/build/living/authoringReducer.ts:230-240`
- Modify: `frontend/src/build/living/useAuthoringSession.ts:53-57`
- Test: `frontend/src/build/living/authoringReducer.test.ts`, `frontend/src/build/living/useAuthoringSession.test.tsx`

**Interfaces:**
- Consumes: `AuthoringSession["pending_proposal"]["block"]["reading"]`, generated by `make client` in plan 2. Its `state` is `"pending" | "read" | "could_not_tell" | "refused" | "no_answer" | "hand_back" | "handed"`.

- [x] **Step 1: Write the failing tests**

In `authoringReducer.test.ts`, next to the existing `isWaiting` cases (copy how they build a session):

```ts
it("waits while the AI reads a sample (issue 135)", () => {
  const s = sessionWithBlock({ kind: "question", reading: { state: "pending", attempt: 1 } });
  expect(isWaiting(s)).toBe(true);
});

it("stops waiting once the reading arrived", () => {
  const s = sessionWithBlock({ kind: "question", reading: { state: "read", attempt: 1 } });
  expect(isWaiting(s)).toBe(false);
});
```

(`sessionWithBlock` is the helper those tests already use, or a three-line one written beside them: `{ ...emptySession, pending_proposal: { id: "p", kind: "gap", block } }`.)

In `useAuthoringSession.test.tsx`, follow the file's own render helper:

```ts
it("asks again when the window regains focus, so a reading that landed while hidden shows (issue 230)", async () => {
  const fetches = mockSessionFetches(); // the file's existing fetch mock; count calls
  renderSession();
  await waitFor(() => expect(fetches()).toBe(1));
  window.dispatchEvent(new Event("focus"));
  await waitFor(() => expect(fetches()).toBe(2));
});
```

- [x] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/build/living/authoringReducer.test.ts src/build/living/useAuthoringSession.test.tsx`
Expected: FAIL. `isWaiting` ignores `reading`; with no `refetchOnWindowFocus`, the query may already refetch on focus by TanStack's default. If that test passes before the change, the default is on: keep the test, which now pins the default, and skip the change in Step 3.

- [x] **Step 3: Implement**

`isWaiting`: widen the block's cast to include `reading?: { state?: string }` and add:

```ts
  // The AI reading a sample (issue 135): its answer arrives on this poll, like a phrasing.
  if (block?.reading?.state === "pending") return true;
```

`useAuthoringSession`, in the session query's options: `refetchOnWindowFocus: "always",`.

- [x] **Step 4: Run them to verify they pass**

Run the Step 2 command. Expected: PASS.

- [x] **Step 5: Check, then commit**

```bash
git add frontend/src/build/living && git commit -m "feat(living): the page waits on the AI's reading, and asks again on return (#135)"
```

---

### Task 3: The card reads, waits, re-sends and says what the AI read

**Files:**
- Modify: `frontend/src/build/living/blocks/SampleUpload.tsx`
- Modify: `frontend/src/build/living/blocks/GapCard.tsx:88-99`
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`_answer_of`)
- Test: `frontend/src/build/living/SampleUpload.test.tsx`, `frontend/src/build/living/GapCard.test.tsx`, `packages/mendel-api/tests/test_characterise_reading.py`

**Interfaces:**
- Consumes: `SampleInspected.outcome === "reading"`; the question block's `reading`.
- Produces: `SampleUpload` gains the prop `reading?: Reading | null`, where `type Reading = NonNullable<QuestionBlock["reading"]>`.

- [x] **Step 1: Write the failing tests**

Append to `SampleUpload.test.tsx`:

```tsx
const reading = (state: string, extra = {}) => ({ state, attempt: 1, type_id: null, states: [],
  recorded: [], kept: [], disagreed: [], code: null, ...extra }) as never;

function setupReading(props: Record<string, unknown> = {}, onUpload = vi.fn()) {
  const view = render(
    <SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={onUpload}
      onAnswered={vi.fn()} {...props} />,
  );
  return { onUpload, ...view };
}

describe("the AI reading a sample (issue 135)", () => {
  it("accepts any file and says what may go to the AI", () => {
    setupReading();
    const input = screen.getByLabelText(LABEL) as HTMLInputElement;
    expect(input.accept).toBe("");
    expect(screen.getByText(/if nothing here reads its type, about 8 KB of its text goes to the AI to read/)).toBeTruthy();
  });

  it("waits while the AI reads", async () => {
    const onUpload = vi.fn().mockResolvedValue(result({ outcome: "reading", facts: [], recorded: [] }));
    const { rerender } = setupReading({}, onUpload);
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("x.bam")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    rerender(<SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={onUpload}
      onAnswered={vi.fn()} reading={reading("pending")} />);
    expect(await screen.findByText(/being read by AI/)).toBeTruthy();
  });

  it("shows what the AI read, each line read by AI", () => {
    setupReading({ reading: reading("read", { type_id: "alignment.bam",
      states: ["coordinate_sorted"], recorded: ["alignment.bam"] }) });
    expect(screen.getByText("alignment.bam")).toBeTruthy();
    expect(screen.getByText("coordinate_sorted")).toBeTruthy();
    expect(screen.getAllByText(/read by AI/).length).toBeGreaterThanOrEqual(2);
  });

  it("says when the AI couldn't tell, when it was refused, and when it didn't answer", () => {
    const { rerender } = setupReading({ reading: reading("could_not_tell") });
    expect(screen.getByText(/the AI couldn't tell what this file is/)).toBeTruthy();
    rerender(<SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={vi.fn()}
      onAnswered={vi.fn()} reading={reading("refused", { code: "MI0204" })} />);
    expect(screen.getByText(/named something this registry doesn't declare · nothing was recorded/)).toBeTruthy();
    rerender(<SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={vi.fn()}
      onAnswered={vi.fn()} reading={reading("no_answer", { code: "MA0007" })} />);
    expect(screen.getByText(/the AI didn't answer/)).toBeTruthy();
  });

  it("re-sends the same files once when the AI names a type the engine reads", async () => {
    const onUpload = vi.fn()
      .mockResolvedValueOnce(result({ outcome: "reading", facts: [], recorded: [] }))
      .mockResolvedValueOnce(result());
    const { rerender } = setupReading({}, onUpload);
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("reads.txt")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    const handBack = reading("hand_back", { type_id: "fastq.reads" });
    rerender(<SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={onUpload}
      onAnswered={vi.fn()} reading={handBack} />);
    await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(2));
    expect(onUpload.mock.calls[1][0][0].name).toBe("reads.txt");
    rerender(<SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={onUpload}
      onAnswered={vi.fn()} reading={{ ...handBack }} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(onUpload).toHaveBeenCalledTimes(2);
    expect(await screen.findByText(/type read by AI/)).toBeTruthy();
  });

  it("offers Measure as … when the files are gone", () => {
    setupReading({ reading: reading("hand_back", { type_id: "fastq.reads" }) });
    expect(screen.getByText(/looks like fastq\.reads/)).toBeTruthy();
    expect(screen.getByLabelText(/Measure as fastq\.reads/)).toBeTruthy();
  });

  it("keeps a refusal's sentence and stays usable", async () => {
    const onUpload = vi.fn().mockRejectedValue(new Refused("MI0215: a sample is already being read for this question"));
    setupReading({}, onUpload);
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("x.bam")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/MI0215/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Measure again" })).toBeTruthy();
  });
});
```

Check `Refused`'s constructor in `frontend/src/api/client.ts` and build it the way its other tests do.

In `GapCard.test.tsx`, add: with `block.reading.state === "pending"`, the question's other answers are disabled (`toBeDisabled()`). Follow the file's own proposal builder.

Append to `packages/mendel-api/tests/test_characterise_reading.py`:

```python
def test_the_log_says_an_answer_came_from_the_ai(clean, readable):
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    row = next(h for h in authoring.read(sid)["history"] if h["id"] == pid)
    assert row["answer"] == "I have it · read by AI"
```

- [x] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/build/living/SampleUpload.test.tsx src/build/living/GapCard.test.tsx`, and
`MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_characterise_reading.py -q -k log`
Expected: FAIL.

- [x] **Step 3: Implement, to the artboards**

`SampleUpload.tsx`:

- `accept` is removed from the input. The two lines under the picker become the spec's line: *only the first 4 MB is read, on this server · if nothing here reads its type, about 8 KB of its text goes to the AI to read*. For a picked file, use *only the first 4 MB of each is read, on this server · the rest never leaves your computer · if nothing here reads its type, about 8 KB of its text goes to the AI*.
- `Stage` gains `{ at: "reading"; files: File[] }`. In `measure`, a result with `outcome === "reading"` sets that stage, and calls neither `onAnswered` nor the `done` stage.
- New prop `reading?: Reading | null`. Its effect on the drawing, in this order:
  - `pending` → the *measuring* line's twin: ● *being read by AI…*;
  - `read` → `ReadByAi`: one line for the type, then one per state, each `· read by AI` in `--measured`'s sibling colour from the artboard. Any `disagreed` subject gets the same box `SampleResult` draws for a disagreement;
  - `could_not_tell` / `refused` / `no_answer` → the `Outcome`-style box with the spec's sentence. `no_answer` and `refused` also show **Measure again** when files are held;
  - `hand_back` with files held (stage `reading`, or `done`) → *read by AI: {type_id} → measuring…*, and a `useEffect` that calls `measure(files)` once per `attempt`, remembered in a `useRef<number | null>`;
  - `hand_back` with no files held → *looks like {type_id}*, and the picker drawn with the label `Measure as {type_id}`;
  - `handed` → the measured result as today, plus one line, *type read by AI*.
- Keep the three-file refusal and the `failed` stage as they are.

`GapCard.tsx`: pass `reading={block.reading}` to `SampleUpload`, and treat `block.reading?.state === "pending"` like `measuring` for the other answers' `disabled`.

`authoring.py`, `_answer_of`: for `chosen_option == UPLOAD` on an input gap, return `"I have it · read by AI"` when the session's fact for that subject has `source == "model_read"`, else `_INPUT_OPTIONS["have_it"]` as today. `facts` is already passed in.

Run `make client` if a backend type moved (it should not have).

- [x] **Step 4: Run them to verify they pass**

Run the Step 2 commands, then `cd frontend && npx vitest run && npx tsc -b`.
Expected: PASS.

- [x] **Step 5: Check, then commit**

```bash
git add frontend packages/mendel-api && git commit -m "feat(living): the card shows the AI reading a sample — waiting, read, refused, handed back and re-sent (#135)"
```

---

### Task 4: The goal card's label, and the look against the artboards

**Files:**
- Test: `frontend/src/build/living/Collection.test.tsx` (or wherever `GoalCard` is tested: `grep -ln "GoalCard" frontend/src --include=*.test.tsx`)
- Screenshots: the scratchpad.

- [x] **Step 1: Pin the goal card's label**

```tsx
it("labels an input and a fact the AI read as read by AI (issue 135)", () => {
  renderGoal({ facts: [
    { kind: "input", subject: "genome.fasta", source: "model_read", states: [] },
    { kind: "measurement", subject: "paired", value: true, source: "model_read" },
  ] }); // the file's own render helper
  expect(screen.getAllByText(/read by AI/)).toHaveLength(2);
});
```

Run it. It should pass already (`SOURCE.model_read` exists). If it does not, the input line does not use `sourceLabel`; make it, and watch the test pass.

- [x] **Step 2: Screenshot each state**

With `make dev` up, an AI model configured, and level 0: drive the gap card with puppeteer, as the 14.7.6 walk did (`scratchpad/pp/shoot.mjs` is the pattern), through a BAM, a FASTQ renamed `.txt`, and a binary file. Capture each artboard's state on a desk (1280) and on a phone (390). Where a live model is slow, wait on `being read by AI` disappearing, never on a fixed sleep.

- [x] **Step 3: Compare each to its artboard in one viewport** (`.design/_compare.html`), never by reading markup. List every difference, fix the ones that are mistakes, and record the deliberate ones in the execution record for the operator.

- [x] **Step 4: Check, then commit**

```bash
git add frontend && git commit -m "fix(living): the AI's reading matches its artboards (#135)"
```

---

## Execution record

Executed 2026-10-04, in one hand. The artboards were approved by the operator ("thats good go ahead").

- **Task 1** (0d51f2aa): the canvas page *Read by AI*.
- **Task 2** (1f4d3843). *Ruling:* the return-to-page test passed before any change (TanStack refetches on focus by default), so it pins the default.
- **Task 3** (427a0e45): the card's states, the automatic re-send, and the log row's answer.
- **Task 4**, walked live with gemma3:12b.
  - The walk found #243 and #244. The operator decided #244 (evidence, spec §14), built by plan 5; that work found #245.
  - Compared with the artboards:
    - *A4* lacked the file's name and why the question stays; fixed in 44b3428c.
    - *A3*'s log row said *measured from your sample* for an AI reading; fixed in 44b3428c, then reduced to one *read by AI*.
  - Matches: A1, A2, A3, A4, A5 (the hand-back, shown as the log row once the question closes, a deliberate difference from A5's in-card line), A8, and on a phone A10 and A11.
  - Not reached live and pinned by vitest only: A6 (files gone after a reload), A7 (couldn't tell), A9 (no answer).
  - Mid-walk the machine restarted. The stack was brought back up, and the throwaway test database recreated (`postgres:17-alpine` on :5442) and migrated.
