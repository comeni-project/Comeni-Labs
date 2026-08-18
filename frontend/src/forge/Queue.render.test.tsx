import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Queue } from "./Queue";

/** The real shape, copied from a live `GET /questions` against a two-draft workspace. */
const REAL = {
  total: 13,
  questions: [
    { subject: "consumes[0].type_id", what: "what arrives on channel 0",
      why_open: "nf-core declares it as type: file", band: "routing",
      asked_by: ["fastqc", "samtools-index"], candidates: [], closed: true,
      evidence: [], suggested: null },
    { subject: "roles", what: "the job this contract does",
      why_open: "a module declares no role", band: "routing",
      asked_by: ["fastqc", "samtools-index"], candidates: [], closed: true,
      evidence: [], suggested: null },
  ],
};
const STRIP = { contracts: 12, matching: 10, unverifiable: 2, types: 22,
                checked_at: "2026-08-18T14:04:59Z" };

afterEach(() => vi.unstubAllGlobals());

describe("the queue, end to end from a response", () => {
  it("renders the rows the API actually returns", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({
      ok: true, json: async () => (String(url).includes("health") ? STRIP : REAL),
    })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><Queue /></QueryClientProvider>);

    await waitFor(() => expect(screen.getByText("consumes[0].type_id")).toBeTruthy());
    expect(screen.getByText("roles")).toBeTruthy();
    // the count line reports rows AND the pre-aggregation total. `getByText("2")` is
    // ambiguous here — the strip alone contains 12, 22 and 2 — so assert the line.
    expect(screen.getByText(/rows ·/)).toBeTruthy();
    expect(screen.getByText("13")).toBeTruthy();
    // both drafts asked each question, so each row says so
    expect(screen.getAllByText(/2 modules/)).toHaveLength(2);
    // and the strip rendered from the other endpoint
    expect(screen.getByText(/match their source/)).toBeTruthy();
  });
});
