import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { Understood } from "./Understood";

const open = {
  ...FAKE_SESSION,
  turns: [{ seq: 1, role: "person", state: "answered", text: "gene counts from mouse liver", blocks: [],
    base_revision: 0, at: "2026-10-27T08:00:00+00:00" }],
  facts: [], inputs: [], fact_subjects: ["strandedness"],
} as unknown as AuthoringSession;

function understood(session: AuthoringSession, overrides = {}) {
  const props = { session, disabled: false, ...overrides };
  render(<QueryClientProvider client={new QueryClient()}><Understood {...props} /></QueryClientProvider>);
  return props;
}

describe("what was understood, beside the conversation (one builder plan 3)", () => {
  it("quotes the person's sentence above the record", () => {
    understood(open);
    expect(screen.getByRole("region", { name: "What was understood" })).toBeInTheDocument();
    expect(screen.getByTestId("your-sentence")).toHaveTextContent("gene counts from mouse liver");
  });
});
