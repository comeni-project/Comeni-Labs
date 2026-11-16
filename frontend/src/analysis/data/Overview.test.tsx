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
  fireEvent.click(within(checks).getByRole("button", { name: "Use L17_2.fq.gz" }));
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
