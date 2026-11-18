import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";

import { analysis } from "./fixtures";

vi.mock("../../api/client", () => ({
  get: vi.fn(async (url: string) => {
    if (url.endsWith("/reference-types")) return ["annotation.gff", "annotation.gtf", "genome.fasta"];
    if (url.endsWith("/vocabulary")) return { names: { "annotation.gff": "reference annotation (GFF)", "genome.fasta": "reference genome (FASTA)" } };
    if (url === "/data/readers") return [{ id: "fasta", type_id: "assembly.fasta", extensions: [".fasta", ".fna"], compressed: [".gz"], measures: [] }];
    if (url.startsWith("/pipeline/authoring/")) return { canvas: { channels: [
      { name: "genome", grain: "study", type_id: "genome.fasta", param: "genome", ports: [], states: [] },
      { name: "gff", grain: "study", type_id: "annotation.gff", param: "gff", ports: [], states: [] },
      { name: "asm", grain: "sample", type_id: "assembly.fasta", param: "asm", ports: [], states: [] }] } };
    return { total: 4, files: [
      { path: "/d/ref/genome.fna", name: "genome.fna", size: 2856716, sample: null, recognised: null, used_as: "reference" },
      { path: "/d/ref/genes.gff", name: "genes.gff", size: 1407171, sample: null, recognised: null, used_as: "candidate" },
      { path: "/d/notes.txt", name: "notes.txt", size: 10, sample: null, recognised: null, used_as: null },
      { path: "/d/asm/BAC47.fna", name: "BAC47.fna", size: 10, sample: "BAC47", recognised: "assembly.fasta", used_as: null }] };
  }),
  post: vi.fn(async () => ({ session_id: "s1" })),
}));

import { guessKind, References } from "./References";

function refs(data = analysis(), add = vi.fn(), remove = vi.fn()) {
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <References data={data} onAdd={add} onRemove={remove} />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return { add, remove };
}

const withGenome = () => analysis({ references: [{ path: "/d/ref/genome.fna", name: "genome.fna", type_id: "genome.fasta",
                                                   origin: "you", facts: [] }] });

it("one slot a study-wide input of the pipeline: set ones say their file, open ones offer files by kind (board 2026-11-16)", async () => {
  const { add, remove } = refs(withGenome());
  const genome = await screen.findByRole("region", { name: "Genome" });
  expect(within(genome).getByText("genome.fna")).toBeTruthy();
  fireEvent.click(within(genome).getByRole("button", { name: "Change genome.fna" }));
  expect(remove).toHaveBeenCalledWith(0);
  const gff = screen.getByRole("region", { name: "Annotation" });
  // The GFF in the reference folder comes first; a sample's file is never offered.
  const offered = await within(gff).findAllByTestId("candidate");
  expect(offered[0]).toHaveTextContent("genes.gff");
  expect(within(gff).queryByText("BAC47.fna")).toBeNull();
  fireEvent.click(within(offered[0]).getByRole("button", { name: /Use as/ }));
  expect(add).toHaveBeenCalledWith("/d/ref/genes.gff", "annotation.gff");
});

it("another file can be found by name, and standard references are later", async () => {
  refs(withGenome());
  const gff = await screen.findByRole("region", { name: "Annotation" });
  fireEvent.change(within(gff).getByRole("textbox", { name: /Find another file/ }), { target: { value: "notes" } });
  expect(await within(gff).findByText("notes.txt")).toBeTruthy();
  expect(screen.getByText(/downloaded once and kept/)).toBeTruthy();
  expect(screen.queryByText("one file each, for the whole analysis")).toBeNull();
});

it("guesses a reference's kind from its file name, and only when one kind fits (issue 535)", () => {
  const kinds = ["annotation.gff", "annotation.gtf", "genome.fai", "genome.fasta"];
  expect(guessKind("genome.fasta", kinds)).toBe("genome.fasta");
  expect(guessKind("Saccharomyces.R64.gtf.gz", kinds)).toBe("annotation.gtf");
  expect(guessKind("notes.txt", kinds)).toBe("");
  expect(guessKind("x.fasta", ["genome.fasta", "assembly.fasta"])).toBe("");
});
