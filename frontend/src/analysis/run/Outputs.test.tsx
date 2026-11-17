import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

vi.mock("../../wiener/api/client", () => ({
  get: vi.fn(async () => ({ published: true, total: 2, files: [{ process: "quast", name: "report.html", size_bytes: 2048, viewable: true }, { process: "star", name: "WT.bam", size_bytes: 4096, viewable: false }] })),
}));
vi.mock("./useRuns", () => ({ useBuildCanvas: () => ({ data: undefined }), factsOf: () => ({}) }));

import { Outputs } from "./Outputs";

it("Open is a link to the file in a new tab: no popup to block, nothing loaded into the page (Checkpoint D)", async () => {
  render(<QueryClientProvider client={new QueryClient()}><Outputs draftId="d1" runId="r1" live={false} /></QueryClientProvider>);
  const open = await screen.findByRole("link", { name: "Open report.html" });
  expect(open.getAttribute("href")).toBe("/api/runs/r1/results/file?process=quast&name=report.html");
  expect(open.getAttribute("target")).toBe("_blank");
  expect(open.getAttribute("rel")).toContain("noopener");
});

it("does not offer Open for a file a browser cannot show, such as a BAM (walk 2026-11-17)", async () => {
  render(<QueryClientProvider client={new QueryClient()}><Outputs draftId="d1" runId="r1" live={false} /></QueryClientProvider>);
  expect(await screen.findByText("WT.bam")).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Open WT.bam" })).toBeNull();
  expect(screen.getByRole("link", { name: "Open report.html" })).toBeTruthy();
});
