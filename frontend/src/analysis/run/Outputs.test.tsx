import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

vi.mock("../../wiener/api/client", () => ({
  get: vi.fn(async () => ({ published: true, total: 1, files: [{ process: "quast", name: "report.html", size_bytes: 2048 }] })),
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
