import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { Files } from "./Files";

vi.mock("../../api/client", () => ({
  get: vi.fn(async () => ({ total: 3, files: [
    { path: "/d/L01_R1.fq.gz", name: "L01_R1.fq.gz", size: 2048, sample: "L01", recognised: "fastq.reads", used_as: null },
    { path: "/d/genome.fasta", name: "genome.fasta", size: 10, sample: null, recognised: null, used_as: "reference" },
    { path: "/d/notes.txt", name: "notes.txt", size: 10, sample: null, recognised: null, used_as: null },
  ] })),
}));

it("files lists recognised-as and used-as, paged", async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Files draftId="d1" />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("L01_R1.fq.gz")).toBeTruthy();
  expect(screen.getByText("fastq.reads")).toBeTruthy();
  expect(screen.getByText("sample L01")).toBeTruthy();
  expect(screen.getByText("reference")).toBeTruthy();
  expect(screen.getByText("did not fit the rule")).toBeTruthy();
  expect(screen.getByText("3 files · what each was recognised as")).toBeTruthy();
});
