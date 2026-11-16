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
