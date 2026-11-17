import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const FASTQ = { id: "fastq", type_id: "edam:format_1930", by: "code", uses: null, extensions: [".fastq", ".fq"], compressed: [".gz"],
  runs: ["server", "pipeline"], measures: ["paired", "read_length"],
  facts: [{ measurement: "paired", unit: null, description: null, rules: [], settings: [], tests: ["one file"] },
          { measurement: "read_length", unit: "bp", description: null, settings: [], tests: ["uniform 150 is decided"],
            rules: [{ role: "alignment", rows: [{ when: { read_length: ">= 70" }, then: "nf-core/star/align@2.7.11b" }] }] }] };
const FAI = { id: "genome_length_fai", type_id: "fai", by: "tool", uses: "nf-core/samtools/faidx@1.24", extensions: [], compressed: [],
  runs: ["pipeline"], measures: ["genome_length"],
  facts: [{ measurement: "genome_length", unit: "bp", description: null, rules: [], tests: [],
            settings: [{ name: "star_sa_index_nbases", formula: "round(min(14, log₂(genome length) / 2 − 1))" }] }] };

function at(body: object) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) =>
    Promise.resolve({ ok: true, status: 200, json: async () => (String(url).includes("/data/readers") ? body : []) })));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/registry/measurers"] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("lists one measurer a reader and shows what the first measures, with the rule that decides by it", async () => {
  at([FASTQ, FAI]);
  const detail = await screen.findByRole("region", { name: "Selected measurer" });
  expect(within(detail).getByRole("heading", { name: "FASTQ reader" })).toBeTruthy();
  expect(within(detail).getAllByTestId("fact")).toHaveLength(2);
  expect(within(detail).getByText("Decides · which alignment")).toBeTruthy();
  expect(within(detail).getByText("uniform 150 is decided")).toBeTruthy();
});

it("a tool's output says the setting it works out, and the chip narrows the list", async () => {
  at([FASTQ, FAI]);
  fireEvent.click(await screen.findByRole("button", { name: /By a tool in the run/ }));
  const detail = await screen.findByRole("region", { name: "Selected measurer" });
  expect(within(detail).getByRole("heading", { name: "samtools faidx output" })).toBeTruthy();
  expect(within(detail).getByText("round(min(14, log₂(genome length) / 2 − 1))")).toBeTruthy();
});
