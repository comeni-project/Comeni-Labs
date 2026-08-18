import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

const PAGE = {
  id: "nf-core/fastqc@0.12.1",
  roles: ["qc_per_sample"],
  container: "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
  consumes: [{ name: "reads", type_id: "fastq.reads" }],
  produces: [{ name: "html", type_id: "qc.report" }],
  source_path: "vendor/modules/nf-core/fastqc/main.nf",
  emits_total: 3,
  emits_declared: 1,
  rules_aiming: [],
  inputs_from: [],
  outputs_feed: ["nf-core/multiqc@1.25"],
  competes_with: [],
  pipeline_pins: null,
};

function at(page = PAGE) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => page,
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, {
    initialEntries: ["/forge/contracts/nf-core/fastqc@0.12.1"],
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the module page", () => {
  it("states how many emit channels are declared, with the reason", async () => {
    at();
    await waitFor(() => expect(screen.getByText(/1 of 3/)).toBeTruthy());
    // Not a warning: a contract may legitimately model a subset.
    expect(screen.getByText(/may model a subset/i)).toBeTruthy();
  });

  it("says nothing rather than zero when the module cannot be read", async () => {
    at({ ...PAGE, source_path: null, emits_total: null, emits_declared: null });
    await waitFor(() => expect(screen.getByText(/no module source/i)).toBeTruthy());
    expect(screen.queryByText(/0 of 0/)).toBeNull();
  });

  it("names what points at the module", async () => {
    at();
    await waitFor(() => expect(screen.getByText("nf-core/multiqc@1.25")).toBeTruthy());
  });

  it("says pipeline pins are not tracked rather than showing zero", async () => {
    // Dropping a designed claim silently is what the spec warns against.
    at();
    await waitFor(() => expect(screen.getByText(/not tracked yet/i)).toBeTruthy());
  });
});
