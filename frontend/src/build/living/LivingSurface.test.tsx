import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingSurface } from "./LivingSurface";

/** The living builder's shell, against the static session that carries every block state.
 *
 * **What these cannot see is how it looks** — the side-by-side renders are the record of that,
 * and they are in the plan's execution record. These hold the structure: which regions exist,
 * what each state says, where focus goes, and what the layout does not depend on.
 */

function surface(session: AuthoringSession = FAKE_SESSION, overrides = {}) {
  const props = {
    session,
    graph: session.graph,
    steps: FAKE_STEPS,
    state: { ...initialAuthoring, snapshot: session },
    preview: { revision: session.revision, state: "ready" as const, text: "version: 6\n", findings: [] },
    busy: () => false,
    onAccept: vi.fn(),
    onReject: vi.fn(),
    onPreviewOption: vi.fn(),
    onSelect: vi.fn(),
    onCompose: vi.fn(),
    onSay: vi.fn(),
    onRetry: vi.fn(),
    onAddStep: vi.fn(),
    onDismiss: vi.fn(),
    onSetParam: vi.fn(),
    onApplyChange: vi.fn(),
    onEdit: vi.fn(),
    ...overrides,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingSurface {...props} />
    </QueryClientProvider>,
  );
  return props;
}

const with_ = (changes: Partial<AuthoringSession>) =>
  ({ ...FAKE_SESSION, ...changes }) as AuthoringSession;

describe("the two surfaces", () => {
  it("has a canvas, a conversation, one header strip and a composer — and no tabs", () => {
    surface();
    expect(screen.getByRole("region", { name: "pipeline canvas" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "conversation" })).toBeInTheDocument();
    expect(screen.getByTestId("living-header")).toHaveTextContent("rnaseq-counts");
    expect(screen.getByTestId("mode")).toHaveTextContent("build");
    expect(screen.getByRole("form", { name: "say something" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("keeps the canvas first in the document, whatever the stacked order draws", () => {
    // Stacked under 1000px the conversation is drawn first by CSS `order`; the canvas is still
    // what the page is about, so a screen reader meets it first.
    surface();
    const [first, second] = screen.getAllByRole("region");
    expect(first).toHaveAccessibleName("pipeline canvas");
    expect(second).toHaveAccessibleName("conversation");
  });

  it("draws the accepted steps solid and the step on offer as a ghost", () => {
    surface();
    expect(screen.getByTestId("living-node-star_align")).not.toHaveAttribute("data-ghost");
    expect(screen.getByTestId("living-node-samtools_sort")).toHaveAttribute("data-ghost", "true");
    expect(screen.getByRole("button", { name: "SAMTOOLS_SORT, proposed" })).toBeInTheDocument();
  });

  it("says how far through the blueprint the draft is", () => {
    surface();
    expect(screen.getByTestId("living-status")).toHaveTextContent("3 of 5 steps");
  });
});

describe("every block state in the static session", () => {
  it("renders each kind the server can send", () => {
    surface();
    const log = screen.getByRole("list", { name: "decisions and conversation" });
    expect(within(log).getByText("Goal confirmed")).toBeInTheDocument();
    expect(within(log).getByRole("region", { name: "Are the reads stranded?" })).toBeInTheDocument();
    expect(within(log).getByText(/STAR is here because/)).toBeInTheDocument();
    expect(within(log).getByText(/you moved STAR_ALIGN/)).toBeInTheDocument();
    expect(within(log).getByRole("region", { name: "a value for seq_platform" })).toBeInTheDocument();
    expect(within(log).getByRole("region", { name: "the change this would make" })).toBeInTheDocument();
    for (const title of ["It would not answer", "This answer is out of date", "Something to check", "Done"]) {
      expect(within(log).getByText(title)).toBeInTheDocument();
    }
    expect(within(log).getByRole("region", { name: "step 4: SAMTOOLS_SORT" })).toBeInTheDocument();
  });

  it("collapses every answered step to one line naming who decided it", () => {
    surface();
    const row = screen.getByRole("button", { name: /STAR_ALIGN step 3 · measured/ });
    expect(row).toHaveTextContent("you chose");
  });
});

describe("the states a session can be in", () => {
  it("shows a pending turn as working, and the composer waits with it", () => {
    surface();
    expect(screen.getByText("Working on it")).toBeInTheDocument();
    expect(screen.getByTestId("composer")).toBeDisabled();
  });

  it("restores a session with nothing pending as an open composer and the whole history", () => {
    const restored = with_({
      turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending"),
    });
    surface(restored);
    expect(screen.queryByText("Working on it")).toBeNull();
    expect(screen.getByTestId("composer")).not.toBeDisabled();
    expect(screen.getAllByRole("button", { name: /step \d/ })).toHaveLength(3);
  });

  it("says plainly when no model is configured", () => {
    surface(with_({ model_configured: false }));
    expect(screen.getByTestId("no-model")).toHaveTextContent("No model is configured here");
  });

  it("offers retry on an unreachable model only while the session has failed", () => {
    const failed = with_({
      phase: "failed",
      turns: [
        ...FAKE_SESSION.turns.filter((t) => t.state !== "pending"),
        { seq: 9, role: "assistant", state: "answered", text: "", base_revision: 4,
          at: "2026-09-13T10:20:00+00:00",
          blocks: [{ kind: "notice", id: "n9", notice: "refusal", code: "MA0007",
            text: "the model could not be reached" }] },
      ] as AuthoringSession["turns"],
    });
    const props = surface(failed);
    fireEvent.click(screen.getByTestId("retry"));
    expect(props.onRetry).toHaveBeenCalledOnce();
  });

  it("shows a server refusal from the reducer as an alert that can be dismissed", () => {
    const props = surface(FAKE_SESSION, {
      state: { ...initialAuthoring, snapshot: FAKE_SESSION,
        notice: { code: "MI0201", text: "this draft moved while you were looking at it" } },
    });
    expect(screen.getByTestId("living-notice")).toHaveTextContent("MI0201");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(props.onDismiss).toHaveBeenCalledOnce();
  });
});

describe("the proposal card", () => {
  it("accepts the option that is selected, and the recommended one is said in words", () => {
    const props = surface();
    const card = screen.getByRole("region", { name: "step 4: SAMTOOLS_SORT" });
    expect(within(card).getByText("recommended")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("radio", { name: /SAMTOOLS_SORMADUP/ }));
    fireEvent.click(within(card).getByTestId("accept-step"));
    expect(props.onAccept).toHaveBeenCalledWith(FAKE_SESSION.pending_proposal, "alt_1");
  });

  it("previews an option on keyboard focus, not only on hover", () => {
    const props = surface();
    fireEvent.focus(screen.getByRole("radio", { name: /SAMTOOLS_SORMADUP/ }));
    expect(props.onPreviewOption).toHaveBeenCalledWith("alt_1");
  });

  it("asks why as a real turn", () => {
    const props = surface(with_({ turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending") }));
    fireEvent.click(screen.getByTestId("explain-step"));
    expect(props.onSay).toHaveBeenCalledWith("Why is samtools_sort here?");
  });
});

describe("drawers", () => {
  it("moves focus into the artifact drawer and back to the control that opened it", () => {
    surface();
    const opener = screen.getByTestId("living-view-artifact");
    opener.focus();
    fireEvent.click(opener);

    const drawer = screen.getByRole("dialog", { name: /pipeline\.yml/ });
    expect(drawer).toHaveFocus();
    expect(screen.getByTestId("artifact-text")).toHaveTextContent("version: 6");

    fireEvent.keyDown(drawer, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(opener).toHaveFocus();
  });
});

// ── waiting on the person ─────────────────────────────────────────────────────────────────

describe("when the session is waiting on the person to say something (issues 110 and 112)", () => {
  // **Found by the first walk with a real model (2026-09-28).** A refused goal left the header on
  // *reading your goal* with nothing being read, and a goal answered *Not quite* left a read-only
  // card and a composer asking about steps that did not exist. Saying it again worked; nothing on
  // the page said so.
  const person = { seq: 0, role: "person", state: "answered", base_revision: 0,
    at: "2026-09-28T10:00:00Z", blocks: [], text: "paired-end RNA-seq to gene counts" };
  const summary = { kind: "goal_summary", id: "goal-1", goal: { have: [], want: ["counts.matrix"] },
    have: "reads", do: "count them", get: "a matrix" };
  const understanding = (turns: unknown[], history: unknown[] = []) =>
    with_({ phase: "understanding", steps_total: null, pending_proposal: null,
      graph: { nodes: [], edges: [] }, placement: {}, turns, history } as Partial<AuthoringSession>);

  it("after a refusal: the header waits on you, and the log says to say it again", () => {
    surface(understanding([person, { seq: 1, role: "assistant", state: "answered", base_revision: 0,
      at: "2026-09-28T10:01:00Z", text: "",
      blocks: [{ kind: "notice", id: "notice-1", notice: "refusal", code: "MA0004",
        text: "MA0004: the answer did not match GoalUnderstanding: have" }] }]));
    expect(screen.getByTestId("living-status")).toHaveTextContent("waiting for you");
    expect(screen.getByTestId("living-status")).not.toHaveTextContent("reading your goal");
    expect(screen.getByTestId("your-turn")).toHaveTextContent("Say it again, or put it differently");
    expect(screen.getByPlaceholderText(/what you have and what you want/)).toBeInTheDocument();
  });

  it("after Not quite: the log asks what is wrong with the goal", () => {
    surface(understanding(
      [person, { seq: 1, role: "assistant", state: "answered", base_revision: 0,
        at: "2026-09-28T10:01:00Z", text: "", blocks: [summary] }],
      [{ id: "h-goal", kind: "goal", state: "rejected", by: "person", chosen_option: null,
        chosen_contract: null, at: "2026-09-28T10:02:00Z", block: summary }],
    ));
    expect(screen.getByTestId("your-turn")).toHaveTextContent("Say what is wrong with it");
  });

  it("says nothing of the kind while a turn is still being answered", () => {
    surface(understanding([person, { seq: 1, role: "assistant", state: "pending", base_revision: 0,
      at: "2026-09-28T10:01:00Z", text: "", blocks: [] }]));
    expect(screen.getByTestId("living-status")).toHaveTextContent("reading your goal");
    expect(screen.queryByTestId("your-turn")).toBeNull();
  });
});

describe("an answered gap on the log (issue 169)", () => {
  it("shows the answer whole — a typed value as the value", () => {
    const question = (id: string, asks: string) => ({ kind: "question", id, asks,
      why_open: "a step reads it to decide", options: [], exhaustive: true });
    surface(with_({ phase: "gathering", pending_proposal: null, history: [
      { id: "h1", kind: "gap", state: "accepted", by: "person", chosen_option: "value",
        chosen_contract: null, answer: "150", at: "2026-09-28T10:02:00Z",
        block: question("gap-5", "Sequenced read length?") },
      { id: "h2", kind: "gap", state: "accepted", by: "person", chosen_option: "cant_share",
        chosen_contract: null, answer: "I have it, but can't share it", at: "2026-09-28T10:03:00Z",
        block: question("gap-6", "This analysis needs a reference genome. Do you have one?") },
    ] } as Partial<AuthoringSession>));
    expect(screen.getByTestId("gap-answer-h1")).toHaveTextContent(/^150$/);
    const whole = screen.getByTestId("gap-answer-h2");
    expect(whole).toHaveTextContent("I have it, but can't share it");
    expect(whole.className).not.toContain("truncate");
  });

  it("says a question a sample answered was measured, with the value it measured (issue 134)", () => {
    const question = { kind: "question", id: "gap-5", asks: "Sequenced read length?",
      why_open: "a step reads it to decide", options: [], exhaustive: true };
    surface(with_({ phase: "gathering", pending_proposal: null, history: [
      { id: "h1", kind: "gap", state: "accepted", by: "person", chosen_option: "upload",
        chosen_contract: null, answer: "150", at: "2026-09-28T10:02:00Z", block: question },
    ] } as Partial<AuthoringSession>));
    const line = screen.getByTestId("gap-answer-h1").closest("div")!;
    expect(screen.getByTestId("gap-answer-h1")).toHaveTextContent(/^150$/);
    expect(line).toHaveTextContent("measured from your sample");
    expect(line).not.toHaveTextContent("you said");
  });
});

describe("a goal composed by gathering, once confirmed (issue 173)", () => {
  it("stays on the log as the first decision, inputs to outputs", () => {
    const card = { kind: "goal_summary", id: "goal-9",
      goal: { have: [{ type_id: "fastq.reads" }, { type_id: "genome.fasta" }], want: ["counts.matrix"] },
      have: "You have: fastq.reads, genome.fasta.", do: "counts", get: "You get: counts.matrix." };
    surface(with_({ phase: "building", turns: [], history: [
      { id: "g1", kind: "goal", state: "accepted", by: "person", chosen_option: null,
        chosen_contract: null, answer: null, at: "2026-09-28T10:05:00Z", block: card },
    ] } as Partial<AuthoringSession>));
    expect(screen.getByText("Goal confirmed")).toBeInTheDocument();
    expect(screen.getByText("fastq.reads, genome.fasta → counts.matrix")).toBeInTheDocument();
  });
});

describe("the new phases say what is happening (14.7.3)", () => {
  it("reads gathering as gathering what it needs", () => {
    surface(with_({ phase: "gathering", pending_proposal: null }));
    expect(screen.getByTestId("living-status")).toHaveTextContent("gathering what it needs");
  });

  it("after an honest stop, says it ended and offers a new analysis (issue 175)", () => {
    surface(with_({ phase: "stopped", pending_proposal: null, graph: { nodes: [], edges: [] },
      turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending") } as Partial<AuthoringSession>));
    expect(screen.getByTestId("canvas-empty")).not.toHaveTextContent("Confirm the goal");
    expect(screen.getByTestId("canvas-empty")).toHaveTextContent("This analysis stopped");
    expect(screen.getByRole("link", { name: "Start a new analysis" })).toHaveAttribute("href", "/build");
    expect(screen.queryByPlaceholderText(/Ask about a step/)).toBeNull();
  });

  it("reads stopped as stopped: something is missing", () => {
    surface(with_({ phase: "stopped", pending_proposal: null }));
    expect(screen.getByTestId("living-status")).toHaveTextContent("stopped: something is missing");
  });
});

describe("the composer's invitation follows the phase", () => {
  it("asks for a correction while a goal is being checked", () => {
    surface(with_({ phase: "goal_review",
      turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending") } as Partial<AuthoringSession>));
    expect(screen.getByPlaceholderText(/what is wrong with the goal/)).toBeInTheDocument();
  });

  it("while gathering, invites an answer in the person's own words", () => {
    surface(with_({ phase: "gathering", pending_proposal: null,
      turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending") } as Partial<AuthoringSession>));
    expect(screen.getByPlaceholderText(/answer the question above/i)).toBeInTheDocument();
  });
});

describe("a sample that answered a question (issue 134)", () => {
  const question = (id: string, options: [string, string][]) => ({
    id, kind: "gap", draft_revision: 0, options: options.map(([o]) => o).sort(), edges: [],
    block: { kind: "question", id: `q-${id}`, asks: `asks ${id}`, why_open: "w",
      options: options.map(([o, label]) => ({ id: o, label, recommended: false })),
      exhaustive: true, phrasing: "none" },
  });
  const LENGTH = question("p-len", [["value", "Type it (bp)"],
    ["upload", "Not sure: upload a sample and I'll measure it"], ["cant_share", "I can't share it"]]);
  const STRAND = question("p-strand", [["forward", "forward"], ["reverse", "reverse"]]);
  const answered = {
    outcome: "measured", type_id: "fastq.reads", reason: null, recorded: ["read_length"], kept: [],
    disagreed: [], steps: [],
    facts: [{ measurement: "read_length", value: 151, undetermined: null,
      pieces: ["fastq@1.0.0", "read_length@1.0.0"], evidence: { records: 8412 } }],
    session: { pending_proposal: { id: "p-strand" } },
  };

  function shown(pending: unknown, onUpload = vi.fn().mockResolvedValue(answered)) {
    const props = {
      graph: FAKE_SESSION.graph, steps: FAKE_STEPS, preview: null, busy: () => false,
      onAccept: vi.fn(), onReject: vi.fn(), onPreviewOption: vi.fn(), onSelect: vi.fn(),
      onCompose: vi.fn(), onSay: vi.fn(), onRetry: vi.fn(), onAddStep: vi.fn(),
      onDismiss: vi.fn(), onSetParam: vi.fn(), onApplyChange: vi.fn(), onEdit: vi.fn(), onUpload,
    };
    const at = (p: unknown) => {
      const session = with_({ phase: "gathering", pending_proposal: p as never });
      return (
        <QueryClientProvider client={new QueryClient()}>
          <LivingSurface {...props} session={session}
            state={{ ...initialAuthoring, snapshot: session }} />
        </QueryClientProvider>
      );
    };
    const view = render(at(pending));
    return { ...view, at, onUpload };
  }

  it("keeps what it measured above the next question, and drops it once that is answered", async () => {
    const { rerender, at } = shown(LENGTH);
    const input = screen.getByLabelText(/upload a sample/i);
    fireEvent.change(input, { target: { files: [new File(["@r\nA\n+\nI\n"], "s.fq")] } });
    fireEvent.click(screen.getByRole("button", { name: "Measure" }));
    rerender(at(STRAND));
    expect(await screen.findByRole("region", { name: "what your sample measured" })).toBeInTheDocument();
    expect(screen.getByText(/read_length 151/)).toBeInTheDocument();
    rerender(at({ ...STRAND, id: "p-after" }));
    expect(screen.queryByRole("region", { name: "what your sample measured" })).toBeNull();
  });

  // Issue 231: with a pair picked, *Measure* and *I have it* were both drawn primary.
  it("draws one primary action while a sample is picked", () => {
    const READS = question("p-reads", [["upload", "I have it, and I'll upload a sample"],
      ["have", "I have it"], ["dont_have", "I don't have one"]]);
    shown(READS);
    const primaries = () => within(screen.getByRole("region", { name: "a question about your data" }))
      .getAllByRole("button")
      .filter((b) => b.className.includes("bg-[var(--link)]")).map((b) => b.textContent);
    expect(primaries()).toEqual(["I have it"]);
    fireEvent.change(screen.getByLabelText(/upload a sample/i),
      { target: { files: [new File(["@r\nA\n+\nI\n"], "s.fq")] } });
    expect(primaries()).toEqual(["Measure"]);
    fireEvent.click(screen.getByRole("button", { name: "Change" }));
    expect(primaries()).toEqual(["I have it"]);
  });

  it("draws the typed value's button secondary while a sample is picked", () => {
    shown(LENGTH);
    const card = () => within(screen.getByRole("region", { name: "a question about your data" }));
    fireEvent.change(screen.getByLabelText(/upload a sample/i),
      { target: { files: [new File(["@r\nA\n+\nI\n"], "s.fq")] } });
    expect(card().getByRole("button", { name: "Use this" }).className)
      .not.toContain("bg-[var(--link)]");
  });

  it("holds the question's other answers while a sample is out", async () => {
    shown(LENGTH, vi.fn(() => new Promise(() => {})));
    const input = screen.getByLabelText(/upload a sample/i);
    fireEvent.change(input, { target: { files: [new File(["@r\nA\n+\nI\n"], "s.fq")] } });
    fireEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByRole("button", { name: "I can't share it" })).toBeDisabled();
  });
});
