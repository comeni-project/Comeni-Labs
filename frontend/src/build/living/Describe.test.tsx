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

describe("the describe page's words", () => {
  it("asks the board's question and says how to answer it", () => {
    page();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("What do you want to analyse?");
    expect(screen.getByText(/Say it the way you would to a colleague/)).toBeInTheDocument();
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
  it("confirms the goal with Start building", () => {
    const p = page();
    fireEvent.click(screen.getByRole("button", { name: /Start building/ }));
    expect(p.onAccept).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal" }), "keep", undefined);
  });

  it("offers the two paces when the installation asks every time, step by step first", () => {
    page();
    const paces = screen.getByRole("radiogroup", { name: "How do you want to build it?" });
    expect(within(paces).getAllByRole("radio").map((r) => (r as HTMLInputElement).value))
      .toEqual(["together", "stop_where_needed"]);
    expect(within(paces).getByRole("radio", { name: /Step by step, with me/ })).toBeChecked();
  });

  it("answers the engine's pace question with the card chosen, once, when it arrives", () => {
    const p = page();
    fireEvent.click(screen.getByRole("radio", { name: /All at once/ }));
    fireEvent.click(screen.getByRole("button", { name: /Start building/ }));
    const asked = pacingAsked();
    p.again(asked);
    expect(p.onAccept).toHaveBeenLastCalledWith(asked.pending_proposal, "stop_where_needed");
    p.again({ ...asked });
    expect(p.onAccept.mock.calls.filter(([proposal]) => proposal.kind === "pacing")).toHaveLength(1);
  });

  it("draws no pace cards when the installation has fixed the pace, and says how it will go", () => {
    page(undefined, "together");
    expect(screen.queryByRole("radiogroup", { name: "How do you want to build it?" })).toBeNull();
    expect(screen.getByText(/Goes through it together, step by step/)).toHaveTextContent("change it in Settings");
  });

  it("leaves the pace question to its card when nothing was chosen on this page", () => {
    const p = page(pacingAsked());
    expect(p.onAccept).not.toHaveBeenCalled();
    expect(screen.getByText("How should we go through the build?")).toBeInTheDocument();
  });

  it("promises only what the engine keeps: the same goal and answers give the same pipeline", () => {
    page();
    expect(screen.getByText("The same goal and answers always give the same pipeline.")).toBeInTheDocument();
  });
});
