import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

const ASKED_BY_TWO = {
  total: 2,
  questions: [
    {
      subject: "consumes[0].type_id", what: "what arrives on channel 0",
      why_open: "nf-core declares it as type: file", band: "routing",
      asked_by: ["samtools-index", "samtools-sort"], closed: true,
      candidates: [{ value: "alignment.bam", note: "7 contracts" }],
      evidence: [{ locator: "meta.yml:input.bam", text: "BAM/CRAM/SAM file" }],
      suggested: "alignment.bam", changed_at: null, proposed: null,
    },
  ],
};

function open(fetchImpl: typeof fetch, at = "/forge/queue/question/consumes%5B0%5D.type_id") {
  vi.stubGlobal("fetch", fetchImpl);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [at] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const reading = () =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ASKED_BY_TWO });

afterEach(() => vi.unstubAllGlobals());

describe("the answer screen", () => {
  it("names who is asking, as prose", async () => {
    // Design §5: "Asked by X and Y — answering once settles both." The first draft put this
    // in a bordered card and it read as clutter.
    open(reading() as unknown as typeof fetch);
    await waitFor(() =>
      expect(screen.getByText(/answering once settles both/i)).toBeTruthy());
  });

  it("marks a model's suggestion as MODEL", async () => {
    // Who answered is what a reviewer needs: a model suggestion and a human answer oblige
    // different amounts of trust.
    open(reading() as unknown as typeof fetch);
    await waitFor(() => expect(screen.getByText("MODEL")).toBeTruthy());
  });

  it("collapses evidence to one line and opens it into the URL", async () => {
    const router = open(reading() as unknown as typeof fetch);
    await waitFor(() => expect(screen.getByText(/1 line from the module/i)).toBeTruthy());
    expect(screen.queryByText(/BAM\/CRAM\/SAM/)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /evidence/i }));

    expect(screen.getByText(/BAM\/CRAM\/SAM/)).toBeTruthy();
    // In the URL, because a curator sending a link to a confusing question is sending it
    // BECAUSE of the evidence.
    expect(router.state.location.search).toContain("evidence=open");
  });

  it("offers answering every draft that asks, and says how many", async () => {
    open(reading() as unknown as typeof fetch);
    await waitFor(() => expect(screen.getByText("alignment.bam")).toBeTruthy());
    expect(screen.getByRole("button", { name: /all 2 drafts/i })).toBeTruthy();
  });

  it("reports a partial batch rather than claiming success", async () => {
    // The one thing that must not be silent. A 200 with refusals is not a success.
    const fetchImpl = vi.fn((_url: string, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve({
            ok: true, status: 200,
            json: async () => ({
              subject: "consumes[0].type_id", settled: ["samtools-index"],
              refused: [{ draft: "samtools-sort", detail: "MF0003: not legal" }],
            }),
          })
        : Promise.resolve({ ok: true, status: 200, json: async () => ASKED_BY_TWO }));
    open(fetchImpl as unknown as typeof fetch);

    await waitFor(() => expect(screen.getByText("alignment.bam")).toBeTruthy());
    await userEvent.click(screen.getByLabelText("alignment.bam"));
    await userEvent.type(screen.getByLabelText(/reason/i), "it takes a BAM");
    await userEvent.click(screen.getByRole("button", { name: /all 2 drafts/i }));

    // Twice, because `Refusal` shows the code in the message AND in the `forge explain`
    // hint beside it. That is deliberate, so any assertion on a code must expect both.
    await waitFor(() => expect(screen.getAllByText(/MF0003/).length).toBe(2));
    // Also twice: once in the "Asked by" prose, once in the refusal report. Both right.
    expect(screen.getAllByText(/samtools-sort/).length).toBe(2);
  });

  it("always offers nothing here fits", async () => {
    // Invariant 7's escape hatch. A closed choice with no way to decline forces a wrong
    // answer — never buried behind a disclosure.
    open(reading() as unknown as typeof fetch);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /nothing here fits/i })).toBeTruthy());
  });
});
