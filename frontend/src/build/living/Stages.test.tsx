import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { framed } from "./frame";
import { guidedStart } from "./guided";
import { LivingSurface } from "./LivingSurface";

/** The two stages of the page (#377): a describe page while there is nothing to draw, then the
 *  canvas beside a panel whose Step tab holds the engine's cards and whose Assistant tab is the chat. */

function props(session: AuthoringSession, overrides = {}) {
  return {
    session: framed(session, FAKE_STEPS, FAKE_CHANNELS),
    graph: session.graph,
    state: { ...initialAuthoring, snapshot: session },
    preview: null,
    busy: () => false,
    onAccept: vi.fn(), onReject: vi.fn(), onPreviewOption: vi.fn(), onSelect: vi.fn(),
    onCompose: vi.fn(), onSay: vi.fn(), onRetry: vi.fn(), onAddStep: vi.fn(), onDismiss: vi.fn(),
    onSetParam: vi.fn(), onApplyChange: vi.fn(), onEdit: vi.fn(),
    ...overrides,
  };
}

function page(session: AuthoringSession, overrides = {}) {
  const p = props(session, overrides);
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingSurface {...p} />
    </QueryClientProvider>,
  );
  const again = (next: AuthoringSession) => view.rerender(
    <QueryClientProvider client={new QueryClient()}>
      <LivingSurface {...p} {...props(next, overrides)} />
    </QueryClientProvider>,
  );
  return { ...p, again };
}

const with_ = (changes: Partial<AuthoringSession>) => ({ ...FAKE_SESSION, ...changes }) as AuthoringSession;
const tab = (name: string) => screen.getByRole("tab", { name });

describe("the describe stage", () => {
  it("is a page of its own: the sentence, the goal waiting to be checked, and no canvas", () => {
    page(guidedStart());
    const describe_ = screen.getByRole("region", { name: "describe" });
    expect(within(describe_).getByRole("heading", { name: "What do you want to analyse?" })).toBeInTheDocument();
    expect(within(describe_).getByTestId("your-sentence")).toHaveTextContent("12 paired RNA-seq samples");
    expect(within(describe_).getByRole("button", { name: "That's right" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "pipeline canvas" })).toBeNull();
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("keeps a composer below the card, and the conversation once there is more than the sentence", () => {
    const start = guidedStart();
    const { again } = page(start);
    expect(screen.getByRole("form", { name: "say something" })).toBeInTheDocument();
    expect(screen.queryByRole("log", { name: "conversation" })).toBeNull();
    again({ ...start, turns: [...start.turns,
      { seq: 9, role: "person", state: "answered", base_revision: 0, at: "2026-10-20T10:00:00Z",
        blocks: [], text: "it is mouse, not human" }] } as AuthoringSession);
    expect(screen.getByRole("log", { name: "conversation" })).toHaveTextContent("it is mouse, not human");
  });

  it("does not repeat the sentence in the conversation, nor point at a Step tab it does not have", () => {
    page(guidedStart());
    expect(screen.getAllByText(/12 paired RNA-seq samples/)).toHaveLength(1);
    expect(screen.queryByText(/see Step/)).toBeNull();
  });

  it("does not scroll the page to the conversation, away from the card waiting", () => {
    const scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled;
    const start = guidedStart();
    page({ ...start, turns: [...start.turns,
      { seq: 9, role: "person", state: "answered", base_revision: 0, at: "2026-10-20T10:00:00Z",
        blocks: [], text: "it is mouse" }] } as AuthoringSession);
    const targets = scrolled.mock.contexts as Element[];
    expect(targets.some((el) => el.closest("[aria-label='Conversation']"))).toBe(false);
  });

  it("asks the pacing question as How do you want to build it?", () => {
    const pacing = {
      id: "pq", kind: "pacing", draft_revision: 0, options: ["together"], edges: [],
      block: { kind: "question", id: "pacing-s1", asks: "How should we go through the build?",
        why_open: "Pacing is set to ask me every time.", exhaustive: true,
        options: [{ id: "together", label: "Go through it together" }] },
    };
    page(with_({ phase: "building", pending_proposal: pacing } as Partial<AuthoringSession>));
    expect(within(screen.getByRole("region", { name: "describe" }))
      .getByText("How do you want to build it?")).toBeInTheDocument();
  });
});

describe("the build stage", () => {
  it("is the canvas beside a panel with two tabs, Step first", () => {
    page(FAKE_SESSION);
    expect(screen.getByRole("region", { name: "pipeline canvas" })).toBeInTheDocument();
    expect(tab("Step")).toHaveAttribute("aria-selected", "true");
    expect(tab("Assistant")).toHaveAttribute("aria-selected", "false");
    expect(screen.queryByRole("region", { name: "describe" })).toBeNull();
  });

  it("holds the step on offer under Step, beside the step line", () => {
    page(FAKE_SESSION);
    const step = screen.getByRole("tabpanel", { name: "Step" });
    expect(within(step).getByRole("list", { name: "the plan" })).toBeInTheDocument();
    expect(within(step).getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });

  it("holds only speech under Assistant", () => {
    page(FAKE_SESSION);
    fireEvent.click(tab("Assistant"));
    const assistant = screen.getByRole("tabpanel", { name: "Assistant" });
    expect(within(assistant).getByRole("log", { name: "conversation" })).toHaveTextContent("why STAR and not HISAT2?");
    expect(within(assistant).queryByRole("button", { name: "Continue" })).toBeNull();
    expect(screen.queryByRole("list", { name: "the plan" })).toBeNull();
  });

  it("turns to the Assistant when the person says something from the Step tab", () => {
    const answered = with_({ turns: FAKE_SESSION.turns.slice(0, 6) });
    const p = page(answered, { state: { ...initialAuthoring, snapshot: answered, composer: "why?" } });
    fireEvent.submit(screen.getByRole("form", { name: "say something" }));
    expect(p.onSay).toHaveBeenCalledWith("why?");
    expect(tab("Assistant")).toHaveAttribute("aria-selected", "true");
  });

  it("turns to the Assistant when asked why this step", () => {
    page(FAKE_SESSION);
    fireEvent.click(screen.getByRole("button", { name: /why/i }));
    expect(tab("Assistant")).toHaveAttribute("aria-selected", "true");
  });

  it("marks the Assistant tab when a reply arrives while Step is showing, and clears it when opened", () => {
    const quiet = with_({ turns: FAKE_SESSION.turns.slice(0, 2) });
    const p = page(quiet);
    expect(screen.queryByRole("tab", { name: "Assistant, new reply" })).toBeNull();
    p.again(with_({ turns: FAKE_SESSION.turns.slice(0, 4) }));
    fireEvent.click(screen.getByRole("tab", { name: "Assistant, new reply" }));
    expect(screen.queryByRole("tab", { name: "Assistant, new reply" })).toBeNull();
  });

  it("a pointer line in the chat turns back to Step and selects the step it names", () => {
    const p = page(FAKE_SESSION);
    fireEvent.click(tab("Assistant"));
    fireEvent.click(screen.getByText("Asked for a setting on STAR_ALIGN — see Step"));
    expect(tab("Step")).toHaveAttribute("aria-selected", "true");
    expect(p.onSelect).toHaveBeenCalledWith("star_align");
  });

  it("puts the latest reply's change and setting request under From the conversation", () => {
    const quiet = with_({ turns: FAKE_SESSION.turns.slice(0, 4) });
    page(quiet);
    const from = screen.getByRole("region", { name: "From the conversation" });
    expect(within(from).getByRole("region", { name: "the change this would make" })).toBeInTheDocument();
    expect(within(from).getByRole("region", { name: "a value for seq_platform" })).toBeInTheDocument();
  });

  it("draws a gap raised during the build under Step", () => {
    const gap = {
      id: "g1", kind: "gap", draft_revision: 4, options: ["a"], edges: [],
      block: { kind: "question", id: "q-g1", asks: "Which strand were the reads made from?",
        why_open: "No rule could settle it.", exhaustive: true,
        options: [{ id: "a", label: "reverse" }] },
    };
    page(with_({ phase: "building", pending_proposal: gap } as Partial<AuthoringSession>));
    const step = screen.getByRole("tabpanel", { name: "Step" });
    expect(within(step).getByText("Which strand were the reads made from?")).toBeInTheDocument();
  });

  it("brings a newly waiting card into view in the Step tab", () => {
    const scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled;
    const p = page(FAKE_SESSION);
    scrolled.mockClear();
    const next = { ...FAKE_SESSION.pending_proposal!, id: "p-next" } as AuthoringSession["pending_proposal"];
    p.again(with_({ pending_proposal: next }));
    const targets = scrolled.mock.contexts as Element[];
    expect(targets.some((el) => el.getAttribute("data-testid") === "waiting")).toBe(true);
  });

  it("says nothing is waiting when a restored session has nothing on offer", () => {
    page(with_({ phase: "complete", pending_proposal: null, turns: [] }));
    expect(within(screen.getByRole("tabpanel", { name: "Step" }))
      .getByText("Nothing is waiting for you.")).toBeInTheDocument();
  });
});
