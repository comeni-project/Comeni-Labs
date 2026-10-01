# Samples 6 — uploading a sample, on the gap card — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person who is not sure of a fact picks one file or a pair on the gap card, watches it be inspected, and sees what it measured — or why it could not — and the goal card says *measured · fastq 1.0.0 · from 1 sample* beside each fact a file settled.

**Architecture:** A Claude Design pass first, approved by the operator, so the build has artboards to match. Then a `postForm` client helper and an `upload` mutation in `useAuthoringSession`; a `SampleUpload` block inside `GapCard` that owns the picking → inspecting → result states; and the goal card's source label reading `pieces` and `evidence` from the fact. Screenshots are compared to the artboards before the plan closes.

**Tech Stack:** React 19, TypeScript, Tailwind 4 (this project's custom nine-step spacing scale: write spacing as explicit `[Npx]`), TanStack Query, Vitest + Testing Library, headless Chrome for screenshots.

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §1, §10. Part 14.7.6.6 of #134. Depends on part 4 (the route, the `upload` option, `Fact.pieces`).

## Global Constraints

- **Design first:** no component code before the operator approves the artboards (spec §10).
- **`frontend/src/api/` is generated** (`make client`), never hand-edited.
- **The file's name is shown back only on this card, in this browser**; it is never sent anywhere but the upload route, and never written into a fact.
- **Spacing is explicit pixels** (`px-[12px]`, never `px-3`): this project replaces Tailwind's spacing scale with nine custom steps. An unmapped Tailwind colour generates no CSS.
- **Touch targets ≥ 44 px on a phone.** Layout bugs are invisible to jsdom: screenshot.
- Cite issues as *issue 134* in UI text and comments, never `#134` (reads as a hex colour).
- `cd frontend && npx vitest run && npx tsc -b` (never `tsc --noEmit`), and oxlint clean.

## Review Focus

1. **Three files dropped** on the picker: refused on the card before any request, saying *one file or a pair*. Pinned in Task 3.
2. **An upload that fails on the network** (the API is down): the card says so and returns to the gap's answers, never stuck on *inspecting*. Pinned in Task 3.
3. **A result that records facts for other gaps but leaves this one undetermined**: the card shows the reason and keeps this gap's answers; the recorded facts still show on the goal card later. Pinned in Task 3.
4. **A phone**: the picker is a 44 px button, not a drop zone you cannot drop onto. Pinned in Task 5 (screenshot).
5. **A fact from before samples** (no `pieces`): the goal card still says *measured* with no version, never `undefined`. Pinned in Task 4.

---

## File structure

| File | Responsibility |
|---|---|
| Create (scratchpad, published) the design canvas: `GapUpload.dc.html` (desk), `GapUploadPhone.dc.html`, `GoalMeasured.dc.html` | artboards |
| Modify `.design/README.md` | the canvas's row |
| Modify `frontend/src/api/client.ts` | `postForm` |
| Modify `frontend/src/build/living/useAuthoringSession.ts` | `upload` mutation |
| Create `frontend/src/build/living/blocks/SampleUpload.tsx` | the picker, the inspecting state, the result |
| Modify `frontend/src/build/living/blocks/GapCard.tsx` | `upload` option opens `SampleUpload` |
| Modify `frontend/src/build/living/DecisionLog.tsx` | wire `onUpload` |
| Modify `frontend/src/build/living/blocks/GoalCard.tsx` | the measured label |
| Tests: `frontend/src/build/living/SampleUpload.test.tsx`, `GapCard.test.tsx`, `Conversation.test.tsx` (or the GoalCard test) | |

---

### Task 1: The design pass

**Files:** the design canvas (published); `.design/README.md`.

- [ ] **Step 1: Start from the Design type**

Call `Artifact` with `action: "quickstart"`, `intent: "design"`, and follow its result: create the Artifact from the Design type with title *Uploading a sample*, read the instructions it returns, and use the project's design system it lists (the same one the settings overlay used). Read `.design/living-pipeline/LivingCollect.dc.html` and the current `GapCard.tsx` first so the artboards continue the living pipeline's look, not a new one.

- [ ] **Step 2: Draw the artboards**

On one canvas, with the gap *Read length* as the example:

1. **Offered** (desk, 760 px conversation column): the question, *Not sure: upload a sample and I'll measure it* as the upload control, *I can't share it* as a quiet answer, and a one-line note *one file, or a pair (R1 and R2) · only the first 4 MB is read, on this server*.
2. **Picked**: the two file names, sizes, *Measure* (primary) and *Change*.
3. **Inspecting**: the steps as a short list appearing in order (*reading the first 4 MB… unpacking… confirming FASTQ… measuring*).
4. **Measured**: each fact on one line — `read_length 151 · measured · fastq 1.0.0 · 8,412 reads, 97% at 151` — and which gaps it closed.
5. **Undetermined**: `read length: undetermined — lengths vary: 139–151, trimmed?`, then the gap's other answers again.
6. **Unreadable**: `named .fastq, but does not start like one`, then the other answers.
7. **Nothing reads it**: `nothing reads .bam files yet`, then the other answers.
8. **Phone (390 px)**: Offered and Measured, full width, 44 px targets.
9. **Goal card**: the facts list with *measured · fastq 1.0.0 · from 1 sample* beside two facts and *you said* beside one.

Render each with `_prev.py` or headless Chrome and read the PNGs before calling it done.

- [ ] **Step 3: STOP — the operator approves the artboards**

Give the operator the link and wait. Apply their changes and republish to the same URL until they say it is right.

- [ ] **Step 4: Record it**

Add a row to `.design/README.md`'s table: `| (published only) | uploading a sample, 2026-10 — gap card states on a desk and a phone, and the goal card's measured label. **Current** | [<id>](<url>) |`. Run `make links doc-paths`.

```bash
git add .design/README.md && git commit -m "docs(design): the canvas for uploading a sample (#134)"
```

---

### Task 2: The upload mutation

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/build/living/useAuthoringSession.ts`
- Test: `frontend/src/build/living/useAuthoringSession.test.tsx`

**Interfaces:**
- Consumes: the generated `SampleInspected` schema (`make client` after part 4).
- Produces: `postForm<T>(path: string, form: FormData): Promise<T>` (same error handling as `post`: a refusal is a `Refused` with the coded detail); `useAuthoringSession(...).upload(proposal: AuthoringProposal, files: File[]) => Promise<SampleInspected>`; `uploading: boolean`.

- [ ] **Step 1: Write the failing test**

```tsx
it("uploads the files with the proposal and re-reads the session", async () => {
  const fetch = stubFetch({
    "/api/pipeline/authoring/s1/samples": { outcome: "measured", type_id: "fastq.reads", facts: [], reason: null,
      steps: ["read the first 4 MB of 1 file(s)"], recorded: ["read_length"], kept: [], disagreed: [], session: SESSION },
  });
  const { result } = renderHook(() => useAuthoringSession("s1"), { wrapper });
  await waitFor(() => expect(result.current.session).not.toBeNull());
  const file = new File(["@r\nA\n+\nI\n"], "s_R1.fq");
  const got = await act(() => result.current.upload(GAP, [file]));
  expect(got.outcome).toBe("measured");
  const [url, init] = fetch.mock.calls.find(([u]) => String(u).endsWith("/samples"))!;
  expect(url).toBe("/api/pipeline/authoring/s1/samples");
  const body = init.body as FormData;
  expect(body.get("proposal_id")).toBe(GAP.id);
  expect((body.getAll("files")[0] as File).name).toBe("s_R1.fq");
});
```

(Use the test module's existing fetch stub, wrapper, `SESSION` and gap fixtures; the names above stand for them.)

- [ ] **Step 2: Run it to see it fail**

Run: `cd frontend && npx vitest run src/build/living/useAuthoringSession.test.tsx`
Expected: FAIL — `upload` is not a function.

- [ ] **Step 3: Implement**

`client.ts`: `postForm` beside `post`, sending `FormData` with no `Content-Type` header (the browser sets the boundary), sharing `post`'s response handling (extract it into one function both call if it is inline).

`useAuthoringSession.ts`:

```ts
  const upload = useMutation({
    mutationFn: (input: { proposal: AuthoringProposal; files: File[] }) => {
      const form = new FormData();
      form.append("proposal_id", input.proposal.id);
      for (const file of input.files) form.append("files", file);
      return postForm<SampleInspected>(`/pipeline/authoring/${sessionId}/samples`, form);
    },
    onSettled: () => void refresh(),
  });
```

and return `upload: (proposal, files) => upload.mutateAsync({ proposal, files })`, `uploading: upload.isPending`.

- [ ] **Step 4: Run it to see it pass**

Run: `cd frontend && npx vitest run src/build/living/useAuthoringSession.test.tsx && npx tsc -b`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/build/living/useAuthoringSession.ts frontend/src/build/living/useAuthoringSession.test.tsx
git commit -m "feat(living): upload a sample from the conversation (#134)"
```

---

### Task 3: The gap card's upload states

**Files:**
- Create: `frontend/src/build/living/blocks/SampleUpload.tsx`
- Modify: `frontend/src/build/living/blocks/GapCard.tsx`, `frontend/src/build/living/DecisionLog.tsx`
- Test: `frontend/src/build/living/SampleUpload.test.tsx`, `frontend/src/build/living/GapCard.test.tsx`

**Interfaces:**
- Consumes: Task 2's `upload`.
- Produces: `<SampleUpload label: string; busy: boolean; onUpload: (files: File[]) => Promise<SampleInspected>; onDone: () => void />`; `GapCard` gains `onUpload?: (files: File[]) => Promise<SampleInspected>`.

States, matching the approved artboards: `offered` (the option's label as the control) → `picked` (names and sizes, *Measure*, *Change*) → `inspecting` (the steps, then the result) → `measured` | `undetermined` | `unreadable` | `no_inspector` | `failed` (network). Every state but `measured`-with-this-gap-closed shows the gap's other answers below it again.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/build/living/SampleUpload.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SampleUpload } from "./blocks/SampleUpload";

const fq = (name: string) => new File(["@r\nACGT\n+\nIIII\n"], name);
const result = (extra = {}) => ({
  outcome: "measured", type_id: "fastq.reads", reason: null, recorded: ["read_length"], kept: [], disagreed: [],
  steps: ["read the first 4 MB of 2 file(s)", "unpacked gzip", "confirmed FASTQ", "measured 3 fact(s)"],
  facts: [{ measurement: "read_length", value: 151, undetermined: null, pieces: ["fastq@1.0.0", "read_length@1.0.0"], evidence: { records: 8412, share: 0.97 } }],
  ...extra,
});

describe("uploading a sample", () => {
  it("measures a pair and says what it found and how", async () => {
    const onUpload = vi.fn().mockResolvedValue(result());
    render(<SampleUpload label="Not sure: upload a sample and I'll measure it" busy={false} onUpload={onUpload} onDone={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload a sample/i), [fq("s_R1.fq.gz"), fq("s_R2.fq.gz")]);
    expect(screen.getByText("s_R1.fq.gz")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(onUpload).toHaveBeenCalledWith([expect.any(File), expect.any(File)]);
    expect(await screen.findByText(/read_length 151/)).toBeTruthy();
    expect(screen.getByText(/fastq 1\.0\.0 · 8,412 reads, 97% at 151/)).toBeTruthy();
  });

  it("refuses three files on the card, before any request", async () => {
    const onUpload = vi.fn();
    render(<SampleUpload label="Upload" busy={false} onUpload={onUpload} onDone={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), [fq("a.fq"), fq("b.fq"), fq("c.fq")]);
    expect(screen.getByText(/one file, or a pair/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Measure" })).toBeNull();
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("says why a file could not be read", async () => {
    const onUpload = vi.fn().mockResolvedValue(result({ outcome: "unreadable", facts: [], recorded: [], reason: "x.fastq is named like fastq, but does not start like one" }));
    render(<SampleUpload label="Upload" busy={false} onUpload={onUpload} onDone={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), [fq("x.fastq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/does not start like one/)).toBeTruthy();
  });

  it("shows an undetermined fact with its reason", async () => {
    const onUpload = vi.fn().mockResolvedValue(result({ recorded: [], facts: [{ measurement: "read_length", value: null, undetermined: "lengths vary: 139–151, trimmed?", pieces: ["fastq@1.0.0", "read_length@1.0.0"], evidence: {} }] }));
    render(<SampleUpload label="Upload" busy={false} onUpload={onUpload} onDone={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), [fq("t.fq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/lengths vary: 139–151, trimmed\?/)).toBeTruthy();
  });

  it("is never stuck inspecting when the request fails", async () => {
    const onUpload = vi.fn().mockRejectedValue(new Error("Failed to fetch"));
    render(<SampleUpload label="Upload" busy={false} onUpload={onUpload} onDone={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), [fq("a.fq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    await waitFor(() => expect(screen.getByText(/could not be sent/i)).toBeTruthy());
    expect(screen.queryByText(/inspecting/i)).toBeNull();
  });
});
```

In `GapCard.test.tsx`:

```tsx
it("opens the picker from the upload answer instead of sending it", async () => {
  const onAnswer = vi.fn();
  render(<GapCard proposal={LENGTH_WITH_UPLOAD} busy={false} onAnswer={onAnswer} onUpload={vi.fn()} />);
  expect(screen.getByLabelText(/upload a sample/i)).toBeTruthy();
  expect(onAnswer).not.toHaveBeenCalled();
});
```

with `LENGTH_WITH_UPLOAD` = the file's `LENGTH` fixture whose options are `value`, `upload` (*Not sure: upload a sample and I'll measure it*) and `cant_share`.

- [ ] **Step 2: Run them to see them fail**

Run: `cd frontend && npx vitest run src/build/living/SampleUpload.test.tsx src/build/living/GapCard.test.tsx`
Expected: FAIL — no `SampleUpload`.

- [ ] **Step 3: Implement, to the artboards**

`SampleUpload.tsx`: a visually hidden `<input type="file" multiple accept=".fastq,.fq,.gz">` labelled with `label`, behind a styled `<label>` acting as the button (`min-h-[44px]` on a phone); a drop zone only at `md:` and up; the picked list with sizes (`format.ts` has a size formatter if one exists — else add `bytes(n)`); *Measure* calls `onUpload`; while pending, the steps list (`inspecting…` until the answer, then the returned `steps`); then the result by `outcome`. A fact line: `${measurement} ${value} · measured · ${piece(pieces[0])} · ${evidence.records.toLocaleString("en")} reads, ${Math.round(share*100)}% at ${value}` (drop each part whose data is absent). When the result recorded this gap's subject, call `onDone()` (the session re-reads and the next gap arrives); otherwise keep the result visible above the gap's other answers.

`GapCard.tsx`: an option with id `upload` renders `<SampleUpload label={option.label} … />` in place of a button, when `onUpload` is given; the other buttons stay. `DecisionLog.tsx`: pass `onUpload={(files) => upload(pending, files)}` from the session hook (thread `upload` through the props the way `onAccept` is threaded).

- [ ] **Step 4: Run them to see them pass, and the whole frontend**

Run: `cd frontend && npx vitest run && npx tsc -b && npx oxlint`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/build/living
git commit -m "feat(living): the gap card takes a sample — picked, inspected, measured or why not (#134)"
```

---

### Task 4: The goal card says what measured it

**Files:**
- Modify: `frontend/src/build/living/blocks/GoalCard.tsx:10-14, 244-270`
- Test: the GoalCard tests (`grep -ln "GoalCard" frontend/src/build/living/*.test.tsx`)

- [ ] **Step 1: Write the failing tests**

```tsx
it("says which pieces measured a fact, and from one sample", () => {
  renderGoal({ facts: [
    { kind: "measurement", subject: "read_length", value: 151, source: "measured", pieces: ["fastq@1.0.0", "read_length@1.0.0"], evidence: { records: 8412 } },
    { kind: "measurement", subject: "strandedness", value: "reverse", source: "person_said", pieces: [], evidence: null },
  ] });
  expect(screen.getByText(/read_length: 151/).textContent).toContain("measured · fastq 1.0.0 · from 1 sample");
  expect(screen.getByText(/strandedness: reverse/).textContent).toContain("you said");
});

it("says measured, plainly, for a fact with no pieces", () => {
  renderGoal({ facts: [{ kind: "measurement", subject: "read_length", value: 150, source: "measured", pieces: [], evidence: null }] });
  expect(screen.getByText(/read_length: 150/).textContent).toMatch(/· measured$/);
});
```

(`renderGoal` stands for the test module's render helper.)

- [ ] **Step 2: Run them to see them fail**

Run: `cd frontend && npx vitest run src/build/living/<GoalCard test file>`
Expected: FAIL — the label is `measured` only.

- [ ] **Step 3: Implement**

```tsx
/** `fastq@1.0.0` → `fastq 1.0.0`: the format that read the file, which is what a person recognises. */
const piece = (ref: string) => ref.replace("@", " ");

const sourceLabel = (f: Fact) =>
  f.source === "measured" && f.pieces?.length
    ? `measured · ${piece(f.pieces[0])} · from 1 sample`
    : SOURCE[f.source];
```

Use `sourceLabel(f)` in `Facts` and for the input chips (`sourceOf`). *From 1 sample* is a constant on purpose: one sample is all 14.7.6 accepts (issue 218 is where that changes).

- [ ] **Step 4: Run them to see them pass**

Run: `cd frontend && npx vitest run && npx tsc -b`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/build/living
git commit -m "feat(living): the goal card says what measured a fact (#134)"
```

---

### Task 5: Look at it against the artboards

- [ ] **Step 1: Bring the stack up**

`docker compose up -d` and Vite (`cd frontend && setsid npm run dev >/tmp/claude-1000/vite.log 2>&1 &`), the throwaway-free dev database the stack uses. Start a session (*paired-end RNA-seq to gene counts*) and answer gaps until *read length* is asked.

- [ ] **Step 2: Screenshot each state at 1280 and 390**

Headless Chrome with `--force-prefers-reduced-motion` and a throwaway `--user-data-dir`, upload `registry/inspectors/formats/fastq/piece/fixtures/pair_150/*` (measured), `trimmed/t.fq` (undetermined), `fasta_named_fastq/x.fastq` (unreadable), and any `.bam`-named file (nothing reads it). Save to the scratchpad `shots/`.

- [ ] **Step 3: Compare each to its artboard in one viewport** (`.design/_compare.html`), never by reading markup. List every difference; fix the ones that are mistakes; record the deliberate ones in the execution record for the operator.

- [ ] **Step 4: Commit any fixes, then run the frontend checks separately**

```bash
git add frontend && git commit -m "fix(living): the upload states match their artboards (#134)"
cd frontend && npx vitest run && npx tsc -b && npx oxlint
```

---

## Execution record

*(Filled in while executing: rulings, measurements, deviations.)*
