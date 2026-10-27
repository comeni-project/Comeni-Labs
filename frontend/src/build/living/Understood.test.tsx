import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { Understood } from "./Understood";

const open = {
  ...FAKE_SESSION,
  turns: [{ seq: 1, role: "person", state: "answered", text: "gene counts from mouse liver", blocks: [],
    base_revision: 0, at: "2026-10-27T08:00:00+00:00" }],
  facts: [], inputs: [], fact_subjects: ["strandedness"],
  pending_proposal: { id: "g1", kind: "gap", draft_revision: 4, options: ["a"], edges: [],
    asked_at: "2026-10-27T09:00:00+00:00",
    block: { kind: "question", id: "q", asks: "Which strand?", why_open: "w", exhaustive: true, options: [] },
    envelope: { offer: "gap", subject: "strandedness", kind: "measurement" } },
} as unknown as AuthoringSession;

function understood(session: AuthoringSession, overrides = {}) {
  const props = { session, disabled: false, onOpenQuestion: vi.fn(), ...overrides };
  render(<QueryClientProvider client={new QueryClient()}><Understood {...props} /></QueryClientProvider>);
  return props;
}

describe("what was understood, beside the conversation (one builder plan 3)", () => {
  it("quotes the person's sentence above the record", () => {
    understood(open);
    expect(screen.getByRole("region", { name: "What was understood" })).toBeInTheDocument();
    expect(screen.getByTestId("your-sentence")).toHaveTextContent("gene counts from mouse liver");
  });

  it("points an open fact at the question asking it", () => {
    const p = understood(open);
    fireEvent.click(screen.getByRole("button", { name: "Answer strandedness in the chat" }));
    expect(p.onOpenQuestion).toHaveBeenCalled();
  });
});
