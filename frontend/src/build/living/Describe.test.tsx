import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { FAKE_CHANNELS, FAKE_STEPS } from "./fake";
import { framed } from "./frame";
import { guidedStart } from "./guided";
import { LivingSurface } from "./LivingSurface";

/** Describe as the *Describe* board draws it: the goal **is** *What was understood*, and *Start
 *  building* confirms it — answering the pace with the card chosen when the installation asks. */

/** The settings menu as the API serves it, with only the entry the page reads. */
const menu = (pacing: string) => ({ sections: [{ key: "building", title: "Building", lede: "", order: 2,
  served_by: "mendel", entries: [{ setting: { key: "building.pacing" }, shown: { value: pacing, source: "default", locked: false } }] }] });

const FACTS: AuthoringSession["facts"] = [
  { kind: "input", subject: "fastq.reads", source: "person_said", states: [], pieces: [], heard: "12 paired-end RNA-seq samples" },
  { kind: "measurement", subject: "read_length", source: "measured", states: [], value: 151, pieces: [] },
  { kind: "measurement", subject: "organism", source: "model_read", states: [], value: "mouse", pieces: [], heard: "mouse liver" },
  { kind: "measurement", subject: "strandedness", source: "open", states: [], pieces: [] },
];

function page(session: AuthoringSession = { ...guidedStart(), facts: FACTS }, pacing: string | null = "ask") {
  const client = new QueryClient();
  if (pacing) client.setQueryData(["settings"], menu(pacing));
  const p = {
    session: framed(session, FAKE_STEPS, FAKE_CHANNELS),
    graph: session.graph,
    state: { ...initialAuthoring, snapshot: session },
    preview: null,
    busy: () => false,
    onAccept: vi.fn(), onReject: vi.fn(), onPreviewOption: vi.fn(), onSelect: vi.fn(),
    onCompose: vi.fn(), onSay: vi.fn(), onRetry: vi.fn(), onAddStep: vi.fn(), onDismiss: vi.fn(),
    onSetParam: vi.fn(), onApplyChange: vi.fn(), onEdit: vi.fn(),
  };
  const view = render(<QueryClientProvider client={client}><LivingSurface {...p} /></QueryClientProvider>);
  const again = (next: AuthoringSession) => view.rerender(
    <QueryClientProvider client={client}>
      <LivingSurface {...p} session={framed(next, FAKE_STEPS, FAKE_CHANNELS)} graph={next.graph}
                     state={{ ...initialAuthoring, snapshot: next }} />
    </QueryClientProvider>);
  return { ...p, again };
}

/** The engine asking the pace, as `ask_pacing` proposes it — still the describe page's. */
const pacingAsked = (): AuthoringSession => ({
  ...guidedStart(), phase: "building",
  pending_proposal: { id: "pace-1", kind: "pacing", draft_revision: 0, edges: [],
    options: ["together", "stop_where_needed"],
    block: { kind: "question", id: "pacing-s", asks: "How should we go through the build?",
             why_open: "Pacing is set to ask me every time.", options: [
               { id: "together", label: "Go through it together" },
               { id: "stop_where_needed", label: "Set it up, stop only where you need me" }] } },
} as unknown as AuthoringSession);

const table = () => screen.getByRole("region", { name: "the goal as understood" });

describe("describing in the same frame as building (one builder plan 3)", () => {
  it("is what was understood on the left and the conversation on the right, the strip saying Describing", () => {
    page();
    expect(table()).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "build panel" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "the plan" })).toHaveTextContent("Describing");
    expect(screen.queryByRole("region", { name: "describe" })).toBeNull();
  });

  it("asks a question about the data in the conversation, not on the left", () => {
    const asking = { ...guidedStart(), phase: "gathering", facts: FACTS,
      pending_proposal: { id: "g1", kind: "gap", draft_revision: 0, edges: [], options: ["a"],
        asked_at: "2026-10-27T09:00:00+00:00",
        block: { kind: "question", id: "q", asks: "Which strand were the reads made from?", why_open: "w",
                 exhaustive: true, options: [{ id: "a", label: "reverse" }] } } } as unknown as AuthoringSession;
    page(asking);
    expect(within(screen.getByRole("log", { name: "conversation" }))
      .getByText("Which strand were the reads made from?")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "What was understood" })).not.toHaveTextContent("Which strand");
    expect(screen.getByRole("button", { name: /Start building · 1 question left/ })).toBeDisabled();
  });
});

describe("what was understood", () => {
  it("is the goal, as a table: what you have and what you want, each on its line", () => {
    page();
    expect(within(table()).getByRole("heading")).toHaveTextContent("What was understood");
    const have = within(table()).getByRole("list", { name: "what you have" });
    expect(have).toHaveTextContent("You have");
    expect(have).toHaveTextContent("fastq.reads");
    expect(within(table()).getByRole("list", { name: "what you want" })).toHaveTextContent(/You want.*counts\.matrix/);
  });

  it("quotes the words a line was heard in, and says where each came from", () => {
    page();
    const have = within(table()).getByRole("list", { name: "what you have" });
    const reads = within(have).getByText(/fastq\.reads/).closest("li")!;
    expect(reads).toHaveTextContent('From "12 paired-end RNA-seq samples"');
    expect(within(reads).getByTestId("source")).toHaveTextContent("you said");
  });

  it("gives each fact a line in words, with its source as a chip, and an open one as needing you", () => {
    page();
    const facts = within(table()).getByRole("list", { name: "what the engine knows" });
    const row = (label: string) => within(facts).getByText(label).closest("li")!;
    expect(row("Read length")).toHaveTextContent("151");
    expect(within(row("Read length")).getByTestId("source")).toHaveTextContent("measured");
    expect(within(row("Organism")).getByTestId("source")).toHaveTextContent("read by AI");
    expect(row("Organism")).toHaveTextContent('From "mouse liver"');
    expect(row("Strandedness")).toHaveTextContent("Not known yet");
    expect(within(row("Strandedness")).getByTestId("source")).toHaveTextContent("needs you");
  });

  it("opens a line's editor when the line is clicked, and not before", () => {
    page();
    expect(screen.queryByRole("combobox", { name: "add to what you have" })).toBeNull();
    fireEvent.click(within(table()).getByRole("button", { name: "correct fastq.reads" }));
    expect(screen.getByRole("button", { name: "remove fastq.reads from what you have" })).toBeInTheDocument();
  });

  it("draws the goal once: no second list of the same answers under it", () => {
    page();
    expect(screen.getAllByRole("region", { name: /what was understood|the goal as understood/i })).toHaveLength(1);
  });
});

describe("starting to build", () => {
  it("confirms the goal with Start building, in the header", () => {
    const p = page();
    fireEvent.click(within(screen.getByTestId("describe-header")).getByRole("button", { name: /Start building/ }));
    expect(p.onAccept).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal" }), "keep", undefined);
  });

  it("draws no pace cards: when the installation asks, the engine asks in the conversation", () => {
    page();
    expect(screen.queryByRole("radiogroup", { name: "How do you want to build it?" })).toBeNull();
  });

  it("says how it will go when the installation has fixed the pace", () => {
    page(undefined, "together");
    expect(screen.getByText(/Goes through it together, step by step/)).toHaveTextContent("change it in Settings");
  });

  it("asks the pace question in the conversation when it arrives", () => {
    const p = page(pacingAsked());
    expect(p.onAccept).not.toHaveBeenCalled();
    expect(within(screen.getByRole("log", { name: "conversation" }))
      .getByText("How should we go through the build?")).toBeInTheDocument();
  });

  it("promises only what the engine keeps: the same goal and answers give the same pipeline", () => {
    page();
    expect(screen.getByText("The same goal and answers always give the same pipeline.")).toBeInTheDocument();
  });
});

describe("what was asked for and is not offered here (Part I.2)", () => {
  it("is said on the goal being checked", () => {
    page({ ...guidedStart(), facts: FACTS, not_offered: ["differential expression"] } as unknown as AuthoringSession);
    expect(within(table()).getByTestId("not-offered")).toHaveTextContent("Not offered here: differential expression");
  });
});

describe("the goal reads in names (Part I.2, issue 306)", () => {
  it("names a type the way the registry does, and shows the id where nothing names it", async () => {
    const client = new QueryClient();
    client.setQueryData(["settings"], menu("ask"));
    client.setQueryData(["authoring-vocabulary"], { types: {}, measurements: {}, measurers: [],
      names: { "fastq.reads": "Sequencing reads" } });
    const session = { ...guidedStart(), facts: FACTS };
    render(<QueryClientProvider client={client}><LivingSurface {...{
      session: framed(session, FAKE_STEPS, FAKE_CHANNELS), graph: session.graph,
      state: { ...initialAuthoring, snapshot: session }, preview: null, busy: () => false,
      onAccept: vi.fn(), onReject: vi.fn(), onPreviewOption: vi.fn(), onSelect: vi.fn(), onCompose: vi.fn(),
      onSay: vi.fn(), onRetry: vi.fn(), onAddStep: vi.fn(), onDismiss: vi.fn(), onSetParam: vi.fn(),
      onApplyChange: vi.fn(), onEdit: vi.fn() }} /></QueryClientProvider>);
    const have = within(table()).getByRole("list", { name: "what you have" });
    expect(have).toHaveTextContent("Sequencing reads");
    expect(within(table()).getByRole("list", { name: "what you want" })).toHaveTextContent("counts.matrix");
  });
});
