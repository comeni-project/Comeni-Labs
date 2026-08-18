import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Lookup } from "./Lookup";

const CARD = {
  id: "alignment.bam",
  states: ["coordinate_sorted", "indexed"],
  produced_by: ["nf-core/samtools/sort@1.21"],
  consumed_by: ["nf-core/samtools/index@1.21", "nf-core/subread/featurecounts@2.0.6"],
};

function at(search: string) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => CARD,
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/forge/queue${search}`]}>
        <Lookup />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the registry lookup", () => {
  it("shows nothing when no type is being looked up", () => {
    at("");
    expect(screen.queryByText("alignment.bam")).toBeNull();
  });

  it("shows a type's states and who uses it", async () => {
    at("?lookup=alignment.bam");
    // Wait on the DATA, not the heading: the panel renders the id from the URL immediately —
    // instant feedback is deliberate — so waiting on the heading passes before the fetch
    // resolves and everything after it reads a loading state.
    await waitFor(() => expect(screen.getByText(/coordinate_sorted/)).toBeTruthy());
    expect(screen.getByText("alignment.bam")).toBeTruthy();
    // The count is the decision aid: "is this the normal choice" is what a curator is asking.
    expect(screen.getByText(/2 consume/i)).toBeTruthy();
  });
});
