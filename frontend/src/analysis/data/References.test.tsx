import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { analysis } from "./fixtures";
import { References } from "./References";

vi.mock("../../api/client", () => ({
  get: vi.fn(async (url: string) => url.endsWith("/reference-types") ? ["annotation.gtf", "genome.fasta"]
    : { total: 2, files: [{ path: "/d/genome.fasta", name: "genome.fasta", size: 10, sample: "genome", recognised: null, used_as: null },
                          { path: "/d/L01_R1.fq.gz", name: "L01_R1.fq.gz", size: 10, sample: "L01", recognised: "fastq.reads", used_as: null }] }),
}));

function refs(data = analysis(), add = vi.fn(), remove = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <References data={data} onAdd={add} onRemove={remove} />
    </QueryClientProvider>,
  );
  return { add, remove };
}

it("references: standard is shown as later; from a file names the file and its type", async () => {
  const { add } = refs();
  expect(screen.getByText(/Standard references/)).toBeTruthy();
  expect(screen.getByText("later")).toBeTruthy();
  // The file and its kind share a name here: wait for both lists.
  await screen.findByRole("option", { name: "annotation.gtf" });
  expect(await screen.findAllByRole("option", { name: "genome.fasta" })).toHaveLength(2);
  fireEvent.change(screen.getByRole("combobox", { name: "File" }), { target: { value: "/d/genome.fasta" } });
  fireEvent.change(screen.getByRole("combobox", { name: "Kind" }), { target: { value: "genome.fasta" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reference" }));
  expect(add).toHaveBeenCalledWith("/d/genome.fasta", "genome.fasta");
});

it("a reference is listed with its kind and can be removed", () => {
  const { remove } = refs(analysis({ references: [{ path: "/d/genes.gtf", name: "genes.gtf", type_id: "annotation.gtf",
                                                    origin: "you", facts: [] }] }));
  expect(screen.getByText("genes.gtf")).toBeTruthy();
  expect(screen.getByText("annotation.gtf")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Remove genes.gtf" }));
  expect(remove).toHaveBeenCalledWith(0);
});
