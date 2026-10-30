import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";

const rev = (n: number, move: string, actor: string, value: unknown, because = "") =>
  ({ n, move, actor, value, because, by: actor === "person" ? "rafael" : null, invocation: null });

const item = (key: string, piece: string, status: string, revisions: unknown[]) => ({
  key, piece, status, current_n: revisions.length,
  value: (revisions[revisions.length - 1] as { value: unknown }).value, revisions,
});

const BASE = {
  id: "a1", source: "nf-core", path: "quast", version: "5.3.0", base: "v0.4.0", reforge: null,
  depends_on: [], started_by: "rafael", started_at: "2026-10-30T10:00:00Z", abandoned_at: null,
  messages: [], ready: false,
};

const ANSWERED = item("questions:role", "questions", "approved",
  [rev(1, "answer", "person", { choice: "assembly_qc" })]);

const PARAM = item("parameters:param:min_contig", "parameters", "proposed",
  [rev(1, "draft", "ai", { position: 0, name: "min_contig", default: 500, via: "ext", key: "args" },
       "QUAST's default")]);

function at(view: object, extra: Record<string, unknown> = {}) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method ?? "GET",
                 body: init?.body ? JSON.parse(String(init.body)) : null });
    const reply = Object.entries(extra).find(([path]) => String(url).endsWith(path))?.[1] ?? view;
    return Promise.resolve({ ok: true, status: 200, json: async () => reply });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/registry/forging/a1"] })} />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("a piece not started offers drafting with the AI or writing it yourself", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "contract", items: [ANSWERED] });
  const draft = await screen.findByRole("button", { name: "Draft with the AI" });
  expect(screen.getByRole("button", { name: "Write it myself" })).toBeTruthy();
  fireEvent.click(draft);
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/forge/adaptations/a1/draft")
    && (c.body as { piece: string }).piece === "contract")).toBe(true));
});

it("approve sends the command with the revision it was made against", async () => {
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] });
  const row = await screen.findByRole("group", { name: "min_contig" });
  fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.url.endsWith("/commands"));
    expect(sent?.body).toEqual({ move: "approve", item: "parameters:param:min_contig", expected: 1 });
  });
});

it("reject opens the chat on the item", async () => {
  at({ ...BASE, phase: "reviewing", next_piece: "parameters", items: [ANSWERED, PARAM] });
  const row = await screen.findByRole("group", { name: "min_contig" });
  fireEvent.click(within(row).getByRole("button", { name: "Reject" }));
  const chat = screen.getByRole("complementary", { name: "Chat with the AI" });
  expect(within(chat).getByText(/about parameters:param:min_contig/)).toBeTruthy();
});

it("an AI proposal in the chat can be approved there", async () => {
  const proposal = { seq: 2, role: "ai", item: null, content: "Here's a revision.", pending: false,
    at: "2026-10-30T10:01:00Z",
    commands: [{ move: "revise", item: "parameters:param:min_contig", value: { default: 200 },
                 because: "viral" }] };
  const calls = at({ ...BASE, phase: "reviewing", next_piece: "parameters",
                     items: [ANSWERED, PARAM], messages: [proposal] });
  const chat = await screen.findByRole("complementary", { name: "Chat with the AI" });
  fireEvent.click(within(chat).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/commands")
    && (c.body as { move: string }).move === "approve")).toBe(true));
});

it("shows drafting while the AI works", async () => {
  at({ ...BASE, phase: "drafting", next_piece: "parameters", items: [ANSWERED] });
  expect(await screen.findByText(/drafting/i)).toBeTruthy();
});

it("all approved: assembling shows the files and the result", async () => {
  const assembled = { loaded: true, conforms: true, problems: [], blames: null,
                      files: ["tools/nf-core/quast/contract.yml"] };
  at({ ...BASE, phase: "reviewing", next_piece: null, ready: true, items: [ANSWERED] },
     { "/assemble": assembled });
  fireEvent.click(await screen.findByRole("button", { name: "Assemble" }));
  expect(await screen.findByText("tools/nf-core/quast/contract.yml")).toBeTruthy();
  expect(screen.getByText(/Loads over the registry/)).toBeTruthy();
});
