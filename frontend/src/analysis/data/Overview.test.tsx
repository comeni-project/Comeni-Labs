import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";

import { analysis } from "./fixtures";

vi.mock("../../api/client", () => ({
  get: vi.fn(async (url: string) => url.endsWith("/vocabulary") ? { names: { "genome.fasta": "reference genome (FASTA)" } }
    : { canvas: { channels: [{ name: "genome", grain: "study", type_id: "genome.fasta", param: "genome", ports: [], states: [] }] } }),
  post: vi.fn(async () => ({ session_id: "s1" })),
}));

import { Across, Checks, ReferencesCard, ScanState } from "./Overview";

const mount = (ui: React.ReactNode) => render(
  <MemoryRouter><QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider></MemoryRouter>);

it("check these lists checks with their fixes, and a fix posts it", () => {
  const onFix = vi.fn();
  mount(<Checks data={analysis()} onFix={onFix} />);
  const checks = screen.getByRole("region", { name: "Check these" });
  expect(within(checks).getByText("L17_R1")).toBeTruthy();
  fireEvent.click(within(checks).getByRole("button", { name: "Use L17_2.fq.gz as L17_R1's mate" }));
  expect(onFix).toHaveBeenCalledWith({ kind: "use_file", sample: "L17_R1", file: "L17_2.fq.gz", by: "you", reason: null });
});

it("a sample odd in two measurements is one row, kept once for both (board 2026-11-16)", () => {
  const onFix = vi.fn();
  mount(<Checks onFix={onFix} data={analysis({ checks: [
    { sample: "BAC47", kind: "odd_fact", measurement: "contigs", detail: "Contigs is 65; the median is 4", fixes: [] },
    { sample: "BAC47", kind: "odd_fact", measurement: "n50", detail: "N50 is 85,010; the median is 2,814,816", fixes: [] }] })} />);
  const [row] = screen.getAllByTestId("check");
  expect(row).toHaveTextContent("Contigs is 65; the median is 4 · N50 is 85,010");
  fireEvent.click(within(row).getByRole("button", { name: "Keep BAC47 as it is" }));
  expect(onFix).toHaveBeenCalledOnce();
  expect(onFix.mock.calls[0][0].map((f: { measurement: string }) => f.measurement)).toEqual(["contigs", "n50"]);
});

it("a scan that stopped offers Read again (issue 526)", () => {
  const onRescan = vi.fn();
  mount(<ScanState data={analysis({ scan: { state: "failed", done: 0, total: 5, error: "boom", examples: [] } })} onRescan={onRescan} />);
  fireEvent.click(screen.getByRole("button", { name: "Read again" }));
  expect(onRescan).toHaveBeenCalled();
});

it("across the samples says a shared value for all, and a range with its median when it differs", () => {
  mount(<Across data={analysis()} />);
  const across = screen.getByRole("region", { name: "Across the samples" });
  expect(within(across).getByText("all 2")).toBeTruthy();
  expect(within(across).getByText("50 bp to 101 bp, median 75.5 bp")).toBeTruthy();
});

it("the references card lists what the pipeline reads, set or not", async () => {
  mount(<ReferencesCard data={analysis()} />);
  const [slot] = await screen.findAllByTestId("reference-slot");
  expect(slot).toHaveTextContent("Genome");
  expect(within(slot).getByRole("link", { name: "Choose a file" })).toBeTruthy();
});
