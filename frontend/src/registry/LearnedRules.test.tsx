import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const HISAT2 = "nf-core/hisat2/align@2.2.2";
const STAR = "nf-core/star/align@2.7.11b";
const PROPOSAL = {
  id: "p1", target_key: "implementation:alignment", target: "Which tool fills alignment",
  rows: [{ when: { paired: true, read_length: "absent" }, then: HISAT2,
           because: "our runs are paired", cite: "kept pipelines a, b, c, decision alignment.bam" }],
  why: "every person chose HISAT2 on paired reads", model: "fake/rules", invocation: "inv1",
  evidence: [
    { pipeline: "a", decision: "alignment.bam", answer: HISAT2, reason: "short reads here" },
    { pipeline: "b", decision: "alignment.bam", answer: HISAT2, reason: "" },
    { pipeline: "c", decision: "alignment.bam", answer: HISAT2, reason: "" },
  ],
  check: [],
  replay: [
    { pipeline: "m", decision: "alignment.bam", recorded: STAR, would: HISAT2, agrees: false, by_person: false },
    { pipeline: "a", decision: "alignment.bam", recorded: HISAT2, would: HISAT2, agrees: true, by_person: true },
    { pipeline: "b", decision: "alignment.bam", recorded: HISAT2, would: HISAT2, agrees: true, by_person: true },
  ],
  stale: false, created_at: "2026-11-14T10:00:00Z",
};
const PAGE = { proposals: [PROPOSAL], refused: [], in_use: [], running: false, model: true };
const IN_USE = { slug: "implementation-alignment", target_key: "implementation:alignment",
                 target: "Which tool fills alignment", rows: PROPOSAL.rows,
                 approved_by: "rafael", approved_at: "2026-11-14T11:00:00Z", proposal: "p1" };

function at(body: object) {
  const calls: { url: string; method: string }[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method ?? "GET" });
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/registry/learned"] })} />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("the tab links here", async () => {
  at(PAGE);
  const tab = await screen.findByRole("link", { name: "Learned rules" });
  expect(tab.getAttribute("href")).toBe("/registry/learned");
});

it("a proposal shows its row, the model's reason, its evidence, check and replay", async () => {
  at(PAGE);
  expect(await screen.findByText("Which tool fills alignment")).toBeTruthy();
  expect(screen.getByText(/When paired is yes and read length is not known/)).toBeTruthy();
  expect(screen.getByText("our runs are paired")).toBeTruthy();
  expect(screen.getAllByText(/the model's reason/).length).toBeGreaterThan(0);
  expect(screen.getByText(/short reads here/)).toBeTruthy();
  expect(screen.getByText("Checks pass")).toBeTruthy();
  expect(screen.getByText(/would change 1 past decision/)).toBeTruthy();
  expect(screen.getByText(/would settle 2 past decisions the same way/)).toBeTruthy();
});

it("Approve posts", async () => {
  const calls = at(PAGE);
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.method === "POST"
    && c.url.endsWith("/rules/proposals/p1/approve"))).toBe(true));
});

it("a failing check disables Approve and says why", async () => {
  at({ ...PAGE, proposals: [{ ...PROPOSAL, check: ["MD0323: row 3 is first for no case"] }] });
  expect(await screen.findByText(/MD0323: row 3 is first for no case/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
});

it("no model disables Propose and says where to set one", async () => {
  at({ ...PAGE, proposals: [], model: false });
  expect(await screen.findByText(/No model is set \(Settings → Models → Adapting tools\)/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Propose" }) as HTMLButtonElement).disabled).toBe(true);
});

it("the empty state says when proposals come", async () => {
  at({ ...PAGE, proposals: [] });
  expect(await screen.findByText(/No proposals yet\. When people answer the same question in three kept pipelines, choose Propose\./)).toBeTruthy();
});

it("Withdraw posts", async () => {
  const calls = at({ ...PAGE, proposals: [], in_use: [IN_USE] });
  fireEvent.click(await screen.findByRole("button", { name: "Withdraw" }));
  await vi.waitFor(() => expect(calls.some((c) => c.method === "POST"
    && c.url.endsWith("/rules/learned/implementation-alignment/withdraw"))).toBe(true));
});
