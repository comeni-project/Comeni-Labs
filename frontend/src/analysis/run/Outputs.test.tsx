import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

const FILES = [
  { process: "subread_featurecounts", name: "WT_REP1.featureCounts.tsv", size_bytes: 4200, viewable: true },
  { process: "subread_featurecounts", name: "WT_REP2.featureCounts.tsv", size_bytes: 4200, viewable: true },
  { process: "samtools_sort", name: "WT_REP1.bam", size_bytes: 3_100_000, viewable: false },
  { process: "multiqc", name: "report.html", size_bytes: 2048, viewable: true },
];
vi.mock("../../wiener/api/client", () => ({
  get: vi.fn(async (url: string) => (url.includes("/measured") ? { facts: [], decided: [] }
    : { published: true, total: 4, files: FILES })),
}));
const lit: (string[] | null)[] = [];
vi.mock("./RunCanvas", () => ({
  RunCanvas: (p: { lit: string[] | null }) => { lit.push(p.lit); return <div data-testid="canvas" />; },
}));
vi.mock("./useRuns", () => ({
  useBuildCanvas: () => ({ data: { canvas: {
    steps: [{ id: "samtools_sort" }, { id: "subread_featurecounts" }, { id: "multiqc" }],
    graph: { edges: [{ from_node: "samtools_sort", to_node: "subread_featurecounts" }] },
  } } }),
  factsOf: () => ({ samtools_sort: { does: "Sort alignments" }, subread_featurecounts: { does: "Count reads" } }),
  useSamples: () => ["WT_REP1", "WT_REP2"],
  useRun: () => ({ graph: { data: { nodes: [] } } }),
  useAnalysisRuns: () => ({ list: [] }),
}));

import { kindOf, Outputs, sampleOf, upstream } from "./Outputs";

function page() {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, text: async () => "Geneid\tWT_REP1.bam\nYAL068C\t3\n" })));
  render(<QueryClientProvider client={new QueryClient()}><Outputs draftId="d1" runId="r1" live={false} /></QueryClientProvider>);
}
afterEach(() => { vi.unstubAllGlobals(); lit.length = 0; });

it("opens on what the pipeline made, with Open a link in a new tab (Checkpoint D)", async () => {
  page();
  const results = await screen.findByRole("region", { name: "Your results" });
  expect(within(results).getByText("Count reads")).toBeTruthy();
  const open = await screen.findByRole("link", { name: "Open WT_REP1.featureCounts.tsv" });
  expect(open.getAttribute("href")).toBe("/api/runs/r1/results/file?process=subread_featurecounts&name=WT_REP1.featureCounts.tsv");
  expect(open.getAttribute("target")).toBe("_blank");
  expect(open.getAttribute("rel")).toContain("noopener");
});

it("lights where the chosen file came from on the pipeline", async () => {
  page();
  await screen.findByRole("region", { name: "Your results" });
  expect(lit.at(-1)).toEqual(["samtools_sort", "subread_featurecounts"]);
});

it("offers no Open for a binary, such as a BAM", async () => {
  page();
  const files = await screen.findByRole("region", { name: "All files" });
  fireEvent.click(await within(files).findByText("WT_REP1.bam"));
  expect(await screen.findByText("BAM · binary")).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Open WT_REP1.bam" })).toBeNull();
});

it("groups files by sample, each group folding, and finds a sample", async () => {
  page();
  const files = await screen.findByRole("region", { name: "All files" });
  const wt2 = await within(files).findByRole("button", { name: /^WT_REP2 ?\d+$/ });
  expect(within(files).getByText("WT_REP2.featureCounts.tsv")).toBeTruthy();
  fireEvent.click(wt2);
  expect(wt2.getAttribute("aria-expanded")).toBe("false");
  expect(within(files).queryByText("WT_REP2.featureCounts.tsv")).toBeNull();
  fireEvent.change(within(files).getByRole("textbox", { name: "Find a sample or file" }), { target: { value: "rep2" } });
  expect(within(files).getByText("WT_REP2.featureCounts.tsv")).toBeTruthy();
  expect(within(files).queryByText("WT_REP1.bam")).toBeNull();
});

it("names a file's kind, its sample and its upstream from names and the graph", () => {
  expect(kindOf("WT.featureCounts.tsv")).toBe("table");
  expect(kindOf("WT.bam")).toBe("bam");
  expect(kindOf("WT.bam.bai")).toBe("index");
  expect(kindOf("WT_1_val_1.fq.gz")).toBe("reads");
  expect(kindOf("genome.measured.json")).toBe("fact");
  expect(kindOf("WT.Log.final.out")).toBe("log");
  expect(sampleOf("WT_REP10.bam", ["WT_REP1", "WT_REP10"])).toBe("WT_REP10");
  expect(sampleOf("genome.fasta.fai", ["WT_REP1"])).toBeNull();
  expect(upstream("c", [{ from_node: "a", to_node: "b" }, { from_node: "b", to_node: "c" }]).sort()).toEqual(["a", "b"]);
});
