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

describe("the new phases say what is happening (14.7.3)", () => {
  it("reads gathering as gathering what it needs", () => {
    surface(with_({ phase: "gathering", pending_proposal: null }));
    expect(screen.getByTestId("living-status")).toHaveTextContent("gathering what it needs");
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
