import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { DataTable } from "./DataTable";

type Row = { name: string; reads: number };
const rows: Row[] = Array.from({ length: 500 }, (_, i) => ({ name: `S${i}`, reads: i }));
const columns = [
  { id: "name", header: "Sample", cell: (r: Row) => r.name },
  { id: "reads", header: "Read pairs", cell: (r: Row) => String(r.reads), width: "120px" },
];

it("data table with 500 rows mounts far fewer than 500 row elements", () => {
  render(<DataTable label="Samples" rows={rows} columns={columns} rowKey={(r) => r.name} height={400} />);
  expect(screen.getByRole("columnheader", { name: "Sample" })).toBeTruthy();
  const mounted = screen.getAllByRole("row").length - 1; // less the header row
  expect(mounted).toBeGreaterThan(0);
  expect(mounted).toBeLessThan(60);
  expect(screen.getByRole("table", { name: "Samples" }).getAttribute("aria-rowcount")).toBe("501");
});

it("data table highlights rows the predicate marks", () => {
  render(<DataTable label="Samples" rows={rows.slice(0, 3)} columns={columns} rowKey={(r) => r.name}
                    height={400} highlight={(r) => r.name === "S1"} />);
  const marked = screen.getAllByRole("row").filter((row) => row.dataset.highlight === "true");
  expect(marked.map((row) => row.textContent)).toEqual(["S11"]);
});

it("a clickable row is reachable by keyboard and opens on Enter", () => {
  const opened: string[] = [];
  render(<DataTable label="Samples" rows={rows.slice(0, 2)} columns={columns} rowKey={(r) => r.name}
                    height={400} onRow={(r) => opened.push(r.name)} />);
  const [, first] = screen.getAllByRole("row");
  expect(first.tabIndex).toBe(0);
  fireEvent.keyDown(first, { key: "Enter" });
  expect(opened).toEqual(["S0"]);
});

it("the header scrolls sideways with the rows, in one box", () => {
  render(<DataTable label="Samples" rows={rows.slice(0, 3)} columns={columns} rowKey={(r) => r.name} height={400} />);
  const box = screen.getByTestId("table-scroll");
  expect(box.contains(screen.getByRole("columnheader", { name: "Sample" }))).toBe(true);
  expect(box.contains(screen.getAllByRole("row")[1])).toBe(true);
});

it("every row and the header share one width, so the columns line up (walk 2026-11-17)", () => {
  // Each row sized itself to its own content (`w-max`), so on a narrow page a row with a longer
  // file name spread its columns further than the next. One width, the same for all.
  render(<DataTable label="Samples" rows={rows.slice(0, 3)} columns={columns} rowKey={(r) => r.name} height={400} />);
  // Sample's default track (120) + Read pairs (120) + one gap (14) + the padding (40).
  expect(screen.getByRole("table").style.getPropertyValue("--least")).toBe("294px");
  for (const row of screen.getAllByRole("row")) {
    expect(row.className).toContain("w-[max(100%,var(--least))]");
    expect(row.className).not.toMatch(/\bw-max\b/);
  }
});
