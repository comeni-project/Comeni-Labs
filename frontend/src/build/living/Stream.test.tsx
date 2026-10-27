import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringProposal, AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { docked } from "./format";
import { QuestionDock } from "./QuestionDock";
import { Stream } from "./Stream";

const ASKED = "2026-10-27T09:00:00+00:00";
const gap = {
  id: "p-genome", kind: "gap", draft_revision: 4, asked_at: ASKED, edges: [],
  options: ["grcm38", "grcm39", "not_sure"],
  block: {
    kind: "question", id: "q-genome", asks: "Which mouse genome should the reads be aligned to?",
    why_open: "Nothing you've said settles the assembly.", exhaustive: true, phrasing: "done",
    options: [
      { id: "grcm39", label: "GRCm39", recommended: false, note: "current assembly" },
      { id: "grcm38", label: "GRCm38 / mm10", recommended: false, note: "older" },
      { id: "not_sure", label: "Not sure", recommended: false },
    ],
  },
  envelope: { offer: "gap", subject: "genome", kind: "measurement", why: "STAR reads it" },
} as unknown as AuthoringProposal;

const person = (seq: number, text: string, at: string) =>
  ({ seq, role: "person", state: "answered", text, blocks: [], base_revision: 4, at });

function session(after: boolean): AuthoringSession {
  return {
    ...FAKE_SESSION,
    phase: "gathering",
    pending_proposal: gap,
    turns: [
      person(1, "gene counts from mouse liver", "2026-10-27T08:59:00+00:00"),
      ...(after ? [person(2, "wait, what is a GTF?", "2026-10-27T09:01:00+00:00")] : []),
    ],
  } as unknown as AuthoringSession;
}

function stream(s: AuthoringSession, overrides = {}) {
  const props = {
    session: s, sending: [], onRetry: vi.fn(), onAsk: vi.fn(),
    waiting: { busy: () => false, onAccept: vi.fn(), onReject: vi.fn(), onPreview: vi.fn(), onSelect: vi.fn() },
    ...overrides,
  };
  render(<Stream {...props} />);
  return props;
}

describe("the open question in the conversation (issue 392)", () => {
  it("is the newest message while nothing has been said after it", () => {
    stream(session(false));
    const log = screen.getByRole("log", { name: "conversation" });
    const items = within(log).getAllByRole("listitem");
    expect(items.at(-1)).toHaveTextContent("Which mouse genome should the reads be aligned to?");
    expect(screen.queryByTestId("asked-pointer")).toBeNull();
    expect(docked(session(false))).toBe(false);
  });

  it("collapses to a pointer once the person talks past it, and is docked", () => {
    stream(session(true));
    const pointer = screen.getByTestId("asked-pointer");
    expect(pointer).toHaveTextContent("Asked: Which mouse genome should the reads be aligned to? · see it");
    expect(screen.queryByRole("button", { name: "GRCm39" })).toBeNull();
    expect(docked(session(true))).toBe(true);
  });

  it("shows the whole question again from its pointer", () => {
    stream(session(true));
    fireEvent.click(screen.getByTestId("asked-pointer"));
    expect(screen.getByText("Nothing you've said settles the assembly.")).toBeInTheDocument();
  });

  it("folds who asked and who worded it into one quiet line", () => {
    stream(session(false));
    expect(screen.getByTestId("provenance")).toHaveTextContent("asked by the engine · worded by the model");
  });
});

describe("the dock above the composer", () => {
  it("answers with one click, its answers the question's own", () => {
    const onAnswer = vi.fn();
    render(<QuestionDock proposal={gap} busy={false} onAnswer={onAnswer} onShow={vi.fn()} />);
    expect(screen.getByText("Still needed:")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "GRCm39" }));
    expect(onAnswer).toHaveBeenCalledWith("grcm39");
  });

  it("brings back the full question", () => {
    const onShow = vi.fn();
    render(<QuestionDock proposal={gap} busy={false} onAnswer={vi.fn()} onShow={onShow} />);
    fireEvent.click(screen.getByRole("button", { name: "show the full question" }));
    expect(onShow).toHaveBeenCalled();
  });

  it("docks a step on offer as Add it, never its whole card", () => {
    const step = { ...FAKE_SESSION.pending_proposal, asked_at: ASKED } as AuthoringProposal;
    const onAnswer = vi.fn();
    render(<QuestionDock proposal={step} busy={false} onAnswer={onAnswer} onShow={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Add it" }));
    expect(onAnswer).toHaveBeenCalledWith("keep");
  });
});
