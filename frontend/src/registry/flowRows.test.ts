import { expect, it } from "vitest";

import { ribbons, sideRows } from "./flowRows";

const TALLY = { bam: 150, txt: 105, vcf: 79, log: 41, table: 76, bai: 38, cram: 37, report: 36, h5ad: 2 };

it("shows the top seven, leaving out what says little", () => {
  const rows = sideRows(TALLY, "", null, {});
  expect(rows.map((r) => r.format)).toEqual(["bam", "txt", "vcf", "table", "bai", "cram", "report"]);
  expect(rows[0].share).toBe(1);
});

it("search reaches the long tail, log included", () => {
  expect(sideRows(TALLY, "h5", null, {}).map((r) => r.format)).toEqual(["h5ad"]);
  expect(sideRows(TALLY, "log", null, {}).map((r) => r.format)).toEqual(["log"]);
});

it("an alias finds its format", () => {
  expect(sideRows({ fasta: 5 }, "fna", null, { fna: "fasta" }).map((r) => r.format)).toEqual(["fasta"]);
});

it("keeps a picked format on show even when it is rare", () => {
  const rows = sideRows(TALLY, "", "h5ad", {});
  expect(rows).toHaveLength(7);
  expect(rows[0].format).toBe("h5ad");
});

it("draws each link between the rows it joins, widest for the strongest", () => {
  const links = [{ reads: "a", makes: "x", modules: 100 }, { reads: "b", makes: "y", modules: 1 }];
  const drawn = ribbons(links, ["a", "b"], ["x", "y"], null, null);
  expect(drawn).toHaveLength(2);
  expect(drawn[0].width).toBeGreaterThan(drawn[1].width);
  expect(drawn[1].d).toContain("M 0 44");
});

it("once a format is picked, only its links are drawn, lit", () => {
  const links = [{ reads: "a", makes: "x", modules: 9 }, { reads: "b", makes: "x", modules: 9 }];
  const drawn = ribbons(links, ["a", "b"], ["x"], "a", null);
  expect(drawn).toHaveLength(1);
  expect(drawn[0].lit).toBe(true);
});

it("at rest it keeps only the strongest links", () => {
  const links = Array.from({ length: 30 }, (_, n) => ({ reads: "a", makes: `m${n}`, modules: n + 1 }));
  const drawn = ribbons(links, ["a"], links.map((l) => l.makes), null, null);
  expect(drawn).toHaveLength(18);
});
