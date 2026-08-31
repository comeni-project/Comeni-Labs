import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const BOARD = {
  rows: [
    {
      ref: "nf-core:samtools/sort",
      tool: "samtools/sort",
      state: "landed",
      status: "drifted",
      consumes: ["alignment.bam"],
      produces: ["alignment.bam"],
      open_questions: 0,
      contract_id: "nf-core/samtools/sort@1.21.0",
      draft: null,
    },
    {
      ref: "nf-core:samtools/faidx",
      tool: "samtools/faidx",
      state: "drafted",
      status: null,
      consumes: [],
      produces: [],
      open_questions: 11,
      contract_id: null,
      draft: "faidx",
    },
    {
      ref: "nf-core:bedtools/sort",
      tool: "bedtools/sort",
      state: "undrafted",
      status: null,
      consumes: [],
      produces: [],
      open_questions: 0,
      contract_id: null,
      draft: null,
    },
  ],
  counts: { undrafted: 1, drafted: 1, landed: 1 },
  status_counts: { drifted: 1, unverifiable: 0, matching: 0 },
  known: null,
  sources: ["nf-core"],
};

function at(path = "/forge/tools", body: unknown = BOARD) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }),
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the tools board", () => {
  it("is one row shape for every stage of a tool's life", async () => {
    // **Spec §1.3.** Sources and Contracts were the same query at two stages, and two row
    // components would put that mistake back into the markup.
    at();
    await waitFor(() => expect(screen.getAllByTestId("tool-row")).toHaveLength(3));
  });

  it("says what a landed tool takes and gives", async () => {
    // The field the old contracts row omitted while spending 180px on `roles`. What a tool
    // consumes and produces is what tells you whether it is the one you want.
    at();
    await waitFor(() => expect(screen.getByText(/alignment\.bam/)).toBeTruthy());
  });

  it("says how much is open rather than telling you to go and look", async () => {
    // The old sources row said "answer it in the queue" with no number, so a draft with one
    // question left and a draft with eleven read identically.
    at();
    await waitFor(() => expect(screen.getByText(/11 open/)).toBeTruthy());
  });

  it("renders the catalogue total as an absence, never as a zero", async () => {
    // #77 — FORGE-REWORK: discovery reads the layer since Plan 5A, not `vendor/modules/`.
    // Either way it is the size of what somebody vendored, not of the known world.
    at();
    await waitFor(() => expect(screen.getByTestId("known").textContent).toBe("—"));
  });

  it("carries the status as a mark, not as a hundred-pixel word", async () => {
    at();
    const marks = await screen.findAllByTestId("standing");
    expect(marks.map((m) => m.getAttribute("data-standing"))).toEqual([
      "drifted",
      "drafted",
      "undrafted",
    ]);
  });
});
