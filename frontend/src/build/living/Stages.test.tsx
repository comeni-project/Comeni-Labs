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

describe("the describe stage", () => {
  it("is the build's frame: the goal being checked where the canvas will be, the conversation beside it", () => {
    page(guidedStart());
    expect(screen.getByRole("region", { name: "the goal as understood" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "build panel" })).toBeInTheDocument();
    expect(within(screen.getByTestId("describe-header")).getByRole("button", { name: /Start building/ }))
      .toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "pipeline canvas" })).toBeNull();
  });

  it("draws no header strip: the page is the describe page", () => {
    page(guidedStart());
    expect(screen.queryByTestId("living-header")).toBeNull();
  });

  it("offers no Pipeline file view while there is no pipeline", () => {
    page(guidedStart());
    expect(screen.queryByTestId("living-view-artifact")).toBeNull();
  });

  it("keeps a composer under the conversation, which holds what is said next", () => {
    const start = guidedStart();
    const { again } = page(start);
    expect(screen.getByRole("form", { name: "say something" })).toBeInTheDocument();
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
    expect(within(screen.getByRole("log", { name: "conversation" }))
      .getByText("How do you want to build it?")).toBeInTheDocument();
  });
});

describe("the build stage", () => {
  it("is the canvas beside one conversation, with the plan as a strip on top (one builder plan 3)", () => {
    page(FAKE_SESSION);
    expect(screen.getByRole("region", { name: "pipeline canvas" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Step|Assistant/ })).toBeNull();
    expect(screen.getByRole("navigation", { name: "the plan" })).toHaveTextContent("Step 4 of 5");
    expect(screen.queryByRole("region", { name: "describe" })).toBeNull();
  });

  it("holds what was said and the step on offer in one log, the offer newest", () => {
    page(FAKE_SESSION);
    const log = screen.getByRole("log", { name: "conversation" });
    expect(log).toHaveTextContent("why STAR and not HISAT2?");
    expect(within(within(log).getAllByRole("listitem").at(-1)!).getByRole("button", { name: "Add it" }))
      .toBeInTheDocument();
  });

  it("asks about an open step with the step attached, then closes it so the reply is seen", () => {
    const answered = with_({ turns: FAKE_SESSION.turns.slice(0, 6) });
    const p = page(answered, { state: { ...initialAuthoring, snapshot: answered, composer: "why?", selected: "star_align" } });
    expect(screen.getByPlaceholderText("Ask about this step…")).toBeInTheDocument();
    fireEvent.submit(screen.getByRole("form", { name: "say something" }));
    expect(p.onSay).toHaveBeenCalledWith("About STAR_ALIGN: why?");
    expect(p.onSelect).toHaveBeenCalledWith(null);
  });

  it("asks why this step in the conversation", () => {
    const p = page(FAKE_SESSION);
    fireEvent.click(screen.getByRole("button", { name: /why/i }));
    expect(p.onSay).toHaveBeenCalledWith(expect.stringMatching(/^Why is samtools_sort here\?$/));
  });

  it("puts the latest reply's change and setting request under From the conversation", () => {
    const quiet = with_({ turns: FAKE_SESSION.turns.slice(0, 4) });
    page(quiet);
    const from = screen.getByRole("region", { name: "From the conversation" });
    expect(within(from).getByRole("region", { name: "the change this would make" })).toBeInTheDocument();
    expect(within(from).getByRole("region", { name: "a value for seq_platform" })).toBeInTheDocument();
  });

  it("docks the open question above the composer once the person talks past it (issue 392)", () => {
    const gap = {
      id: "g1", kind: "gap", draft_revision: 4, options: ["a", "b"], edges: [], asked_at: "2026-10-27T09:00:00+00:00",
      block: { kind: "question", id: "q-g1", asks: "Which strand were the reads made from?",
        why_open: "No rule could settle it.", exhaustive: true,
        options: [{ id: "a", label: "reverse" }, { id: "b", label: "forward" }] },
    };
    const later = { seq: 99, role: "person", state: "answered", text: "what is a GTF?", blocks: [],
      base_revision: 4, at: "2026-10-27T09:05:00+00:00" };
    const p = page(with_({ phase: "building", pending_proposal: gap, turns: [...FAKE_SESSION.turns, later] } as
      Partial<AuthoringSession>));
    const dock = screen.getByRole("region", { name: "the open question" });
    expect(dock).toHaveTextContent("Still needed:Which strand were the reads made from?");
    fireEvent.click(within(dock).getByRole("button", { name: "reverse" }));
    expect(p.onAccept).toHaveBeenCalledWith(expect.objectContaining({ id: "g1" }), "a");
    expect(screen.getByTestId("asked-pointer")).toBeInTheDocument();
  });

  it("draws a gap raised during the build in the conversation", () => {
    const gap = {
      id: "g1", kind: "gap", draft_revision: 4, options: ["a"], edges: [],
      block: { kind: "question", id: "q-g1", asks: "Which strand were the reads made from?",
        why_open: "No rule could settle it.", exhaustive: true,
        options: [{ id: "a", label: "reverse" }] },
    };
    page(with_({ phase: "building", pending_proposal: gap } as Partial<AuthoringSession>));
    expect(within(screen.getByRole("log", { name: "conversation" }))
      .getByText("Which strand were the reads made from?")).toBeInTheDocument();
  });

  it("brings a newly waiting card into view in the conversation", () => {
    const scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled;
    const p = page(FAKE_SESSION);
    scrolled.mockClear();
    const next = { ...FAKE_SESSION.pending_proposal!, id: "p-next" } as AuthoringSession["pending_proposal"];
    p.again(with_({ pending_proposal: next }));
    const targets = scrolled.mock.contexts as Element[];
    expect(targets.some((el) => el.getAttribute("data-testid") === "waiting")).toBe(true);
  });

  it("names the step a value still needs the person on, instead of saying nothing is waiting (issue 385)", () => {
    const steps = { ...FAKE_STEPS, star_align: { ...FAKE_STEPS.star_align, settings: [
      ...FAKE_STEPS.star_align.settings,
      { name: "index_format", value: null, via: "positional", tier: 4, reason: "", because: "",
        axis_reason: "", premise: [], optional: false },
    ] } };
    const session = with_({ phase: "complete", pending_proposal: null, turns: [] });
    const p = props(session);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <LivingSurface {...p} session={framed(session, steps as typeof FAKE_STEPS, FAKE_CHANNELS)} />
      </QueryClientProvider>,
    );
    expect(screen.queryByText("Nothing is waiting for you.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "STAR_ALIGN has 1 value that needs you" }));
    expect(p.onSelect).toHaveBeenCalledWith("star_align");
  });

  it("draws nothing on offer when a restored session waits on nothing: absence is absence", () => {
    page(with_({ phase: "complete", pending_proposal: null, turns: [] }));
    expect(screen.queryByRole("button", { name: "Add it" })).toBeNull();
    expect(screen.queryByText("Nothing is waiting for you.")).toBeNull();
  });
});
