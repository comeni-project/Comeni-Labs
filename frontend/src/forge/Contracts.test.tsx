import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useSearchParams } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Contracts } from "./Contracts";

const LISTING = {
  total: 3,
  counts: { drifted: 1, unverifiable: 1, matching: 1 },
  rows: [
    { id: "nf-core/star/align@1.11.0", roles: ["alignment"], source: "nf-core",
      status: "drifted" },
    { id: "comeni/profile/collect@0.1.0", roles: ["profiling"], source: "comeni",
      status: "unverifiable" },
    { id: "nf-core/fastqc@0.12.1", roles: ["qc_per_sample"], source: "nf-core",
      status: "matching" },
  ],
};

function Show() {
  const [params] = useSearchParams();
  return <output data-testid="url">{params.toString()}</output>;
}

function at(search = "") {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => LISTING,
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/forge/contracts${search}`]}>
        <Contracts />
        <Show />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the contracts list", () => {
  it("shows every contract with its status", async () => {
    at();
    await waitFor(() => expect(screen.getByText("nf-core/fastqc@0.12.1")).toBeTruthy());
    expect(screen.getByText("comeni/profile/collect@0.1.0")).toBeTruthy();
  });

  it("counts unverifiable separately from matching", async () => {
    // Slice 1 shipped the opposite once: 12 contracts, 10 checked, and the strip claimed 12
    // matched. A contract nothing checks looks exactly like a contract that agrees.
    at();
    // Wait on a ROW, not the facet label: the labels are static and render before the fetch
    // resolves, so waiting on them reads the counts while they are still `{}`. Phase 2's
    // Lookup test had exactly this bug.
    await waitFor(() => expect(screen.getByText("nf-core/fastqc@0.12.1")).toBeTruthy());
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(3);
  });

  it("puts a chosen facet in the URL", async () => {
    at();
    await waitFor(() => expect(screen.getByText("nf-core/fastqc@0.12.1")).toBeTruthy());
    await userEvent.click(screen.getByRole("button", { name: /unverifiable/i }));
    expect(screen.getByTestId("url").textContent).toContain("against=unverifiable");
  });

  it("opens on the facet the URL describes", async () => {
    at("?against=drifted");
    await waitFor(() => expect(screen.getByText("nf-core/star/align@1.11.0")).toBeTruthy());
    expect(screen.getByTestId("url").textContent).toContain("against=drifted");
  });
});
