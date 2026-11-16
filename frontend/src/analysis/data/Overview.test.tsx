import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";

import { analysis } from "./fixtures";
import { Overview } from "./Overview";

function overview(data = analysis(), onFix = vi.fn()) {
  render(<MemoryRouter><Overview data={data} onFix={onFix} /></MemoryRouter>);
  return onFix;
}

it("overview tiles render from summary.tiles in order", () => {
  overview();
  const tiles = screen.getAllByTestId("data-tile").map((t) => t.textContent);
  expect(tiles).toEqual(["Samples2", "Kinds of data1", "Size on disk4.2 GB", "Files5"]);
});

it("compare-by picker lists summary.compare_by and draws one bar per sample", () => {
  overview();
  const compare = screen.getByRole("region", { name: "Compare samples by" });
  expect(within(compare).getByRole("combobox", { name: "Measured fact" }).textContent).toContain("Read length");
  expect(within(compare).getAllByTestId("compare-bar")).toHaveLength(2);
  expect(within(compare).getByText(/median 75.5 bp/)).toBeTruthy();
});

it("check these lists checks with their fixes, and a fix posts it", () => {
  const onFix = overview();
  const checks = screen.getByRole("region", { name: "Check these" });
  expect(within(checks).getByText("L17_R1")).toBeTruthy();
  fireEvent.click(within(checks).getByRole("button", { name: "Use L17_2.fq.gz as L17_R1's mate" }));
  expect(onFix).toHaveBeenCalledWith({ kind: "use_file", sample: "L17_R1", file: "L17_2.fq.gz", by: "you", reason: null });
});

it("what was measured says measured or varies with a source tag", () => {
  overview();
  const measured = screen.getByRole("region", { name: "What was measured" });
  expect(within(measured).getByText("Paired")).toBeTruthy();
  expect(within(measured).getByText("yes")).toBeTruthy();
  expect(within(measured).getAllByText("MEASURED").length).toBeGreaterThan(0);
  expect(within(measured).getByText("differs between samples")).toBeTruthy();
});

it("an empty analysis shows only the folder prompt", () => {
  overview(analysis({ folders: [], samples: [], files: 0, checks: [],
                      summary: { tiles: [], compare_by: [], measured: [] } }));
  expect(screen.getByText(/Tick the folders that hold your data/)).toBeTruthy();
  expect(screen.queryByRole("region", { name: "Check these" })).toBeNull();
});

it("a running scan shows how far it has got", () => {
  overview(analysis({ scan: { state: "scanning", done: 12, total: 48, error: null, examples: [] } }));
  expect(screen.getByRole("status").textContent).toContain("12 of 48");
});

it("an odd value can be kept, and each leave-out names its sample", () => {
  const data = analysis({ checks: [{ sample: "L02", kind: "odd_fact", measurement: "read_length",
                                     detail: "Read length is 50; most samples have 101",
                                     fixes: [{ kind: "leave_out", sample: "L02", file: null, measurement: null,
                                               by: "you", reason: null }] }] });
  const onFix = overview(data);
  fireEvent.click(screen.getByRole("button", { name: "Leave L02 out" }));
  expect(onFix).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "leave_out", sample: "L02" }));
  fireEvent.click(screen.getByRole("button", { name: "Keep L02's read_length" }));
  expect(onFix).toHaveBeenLastCalledWith({ kind: "keep", sample: "L02", measurement: "read_length" });
});

it("hundreds of samples do not widen the page", () => {
  const values = Array.from({ length: 500 }, (_, i) => ({ sample: `S${i}`, value: i }));
  overview(analysis({ summary: { ...analysis().summary,
    compare_by: [{ measurement: "read_length", label: "Read length", unit: "bp", values, median: 250 }] } }));
  const bars = screen.getByTestId("compare-bars");
  expect(bars.className).toContain("overflow-hidden");
  expect(bars.className).toContain("gap-0");
});

it("a scan that stopped offers Read again (issue 526)", () => {
  const onRescan = vi.fn();
  render(<MemoryRouter><Overview data={analysis({ scan: { state: "failed", done: 0, total: 5, error: "boom", examples: [] } })}
                                  onFix={vi.fn()} onRescan={onRescan} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Read again" }));
  expect(onRescan).toHaveBeenCalled();
});

it("compare colours only the samples flagged for the chosen measurement, and reads bases in Mb (issue 532)", () => {
  const base = analysis();
  overview(analysis({
    checks: [{ sample: "BAC47", kind: "odd_fact", measurement: "contigs", detail: "Contigs is 65; the median is 4", fixes: [] }],
    summary: { ...base.summary, compare_by: [{ measurement: "assembly_length", label: "Assembly length", unit: "bp",
      values: [{ sample: "BAC47", value: 2837243 }, { sample: "N315", value: 2839469 }], median: 2838356 }] },
  }));
  const compare = screen.getByRole("region", { name: "Compare samples by" });
  expect(within(compare).getByText(/median 2.84 Mb/)).toBeTruthy();
  const bars = within(compare).getAllByTestId("compare-bar");
  expect(bars.filter((b) => b.className.includes("bg-measured"))).toHaveLength(0);
});
