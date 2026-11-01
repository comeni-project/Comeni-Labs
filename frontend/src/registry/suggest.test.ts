import { expect, it } from "vitest";

import { suggest } from "./suggest";

const COUNTS = {
  reads: { bam: 443, fasta: 714, fastq: 190 }, makes: { bam: 218, vcf: 245, mgatk: 1 },
  topics: { alignment: 182 }, suites: { gatk4: 65, gatk: 3, solo: 1 },
};
const ALIASES = { fa: "fasta", fq: "fastq" };
const ROWS = [{ path: "gatk4/haplotypecaller", description: "Call germline SNPs" }];

it("turns `bam to vcf` into that conversion", () => {
  const [first] = suggest("bam to vcf", COUNTS, ALIASES, []);
  expect(first.title).toBe("That conversion");
  expect(first.items[0]).toMatchObject({ label: "bam → vcf", pick: { reads: "bam", makes: "vcf" } });
});

it("reads an alias as its format", () => {
  const groups = suggest("fa to vcf", COUNTS, ALIASES, []);
  expect(groups[0].items[0].pick).toEqual({ reads: "fasta", makes: "vcf" });
});

it("offers each side of a format, only where it exists", () => {
  const formats = suggest("bam", COUNTS, ALIASES, []).find((g) => g.title === "File formats");
  expect(formats?.items.map((i) => i.kind)).toEqual(["reads", "makes"]);
  const vcf = suggest("vcf", COUNTS, ALIASES, []).find((g) => g.title === "File formats");
  expect(vcf?.items.map((i) => i.kind)).toEqual(["makes"]);
});

it("a rare format is found by its exact name, and is not noise for a near one", () => {
  const found = (q: string) => suggest(q, COUNTS, ALIASES, []).find((g) => g.title === "File formats");
  expect(found("mgatk")).toBeDefined();
  expect(found("gatk")).toBeUndefined();
});

it("finds suites and the modules on the page", () => {
  const groups = suggest("gatk", COUNTS, ALIASES, ROWS);
  expect(groups.find((g) => g.title === "Tool suites")?.items.map((i) => i.label)).toEqual(["gatk4", "gatk"]);
  expect(groups.find((g) => g.title === "Modules")?.items[0].pick).toEqual({ module: "gatk4/haplotypecaller" });
});

it("starts with the common formats and topics before anything is typed", () => {
  const titles = suggest("", COUNTS, ALIASES, []).map((g) => g.title);
  expect(titles).toEqual(["File formats", "Topics"]);
});
