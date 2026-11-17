import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";

vi.mock("../../api/client", () => ({
  get: vi.fn(async (url: string) => {
    if (url === "/data/tree") return { path: null, files: 0, folders: [{ name: "data", path: "/d", files: 0, folders: 2, looks_like: [] }] };
    if (url === "/data/tree?path=%2Fd") return { path: "/d", files: 0, folders: [
      { name: "reads", path: "/d/reads", files: 10, folders: 0, looks_like: [{ type_id: "fastq.reads", count: 10 }] },
      { name: "reference", path: "/d/reference", files: 2, folders: 0,
        looks_like: [{ type_id: "annotation.gtf", count: 1 }, { type_id: "genome.fasta", count: 1 }] }] };
    if (url === "/data/readers") return [{ id: "fastq", by: "code", type_id: "fastq.reads", extensions: [".fastq", ".fq"], compressed: [".gz"],
                                           measures: ["paired", "read_length"] }];
    if (url === "/data/reference-types") return ["annotation.gtf", "genome.fasta"];
    if (url.endsWith("/vocabulary")) return { names: { "fastq.reads": "sequencing reads (FASTQ)", "genome.fasta": "reference genome (FASTA)",
                                                        "annotation.gtf": "gene annotation (GTF)" } };
    return {};
  }),
}));

import { Start } from "./Start";

it("picks folders on the page, each saying what it looks like, then reads them (board 2026-11-16)", async () => {
  const onTick = vi.fn();
  render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><Start ticked={[]} onTick={onTick} /></QueryClientProvider></MemoryRouter>);
  const folders = await screen.findByRole("region", { name: "Folders" });
  expect(await within(folders).findByText("10 · sequencing reads (FASTQ)")).toBeTruthy();
  expect(within(folders).getByText("reference genome (FASTA)")).toBeTruthy();
  fireEvent.click(within(folders).getByRole("checkbox", { name: "Use reads" }));
  fireEvent.click(within(folders).getByRole("checkbox", { name: "Use reference" }));
  expect(within(folders).getByText("2 folders", { selector: "b" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Read these folders" }));
  expect(onTick).toHaveBeenCalledWith(["/d/reads", "/d/reference"]);
  const reads = screen.getByRole("region", { name: "What Comeni reads" });
  expect(await within(reads).findByText("sequencing reads (FASTQ)")).toBeTruthy();
  expect(within(reads).getByText(".fastq .fq, and .gz")).toBeTruthy();
  expect(within(reads).getByText("Paired, read length")).toBeTruthy();
});
