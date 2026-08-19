import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

const CATALOGUE = {
  sources: ["nf-core"],
  counts: { undrafted: 2, drafted: 1, landed: 1 },
  rows: [
    { ref: "nf-core:samtools/faidx", state: "undrafted", contract_id: null, draft: null },
    { ref: "nf-core:bedtools/sort", state: "undrafted", contract_id: null, draft: null },
    { ref: "nf-core:picard/markduplicates", state: "drafted", contract_id: null, draft: "picard" },
    {
      ref: "nf-core:fastqc",
      state: "landed",
      contract_id: "nf-core/fastqc@0.12.1",
      draft: null,
    },
  ],
};

function at(post?: { ok: boolean; body: unknown }) {
  const fetchMock = vi.fn().mockImplementation((_url: string, init?: { method?: string }) =>
    init?.method === "POST"
      ? Promise.resolve({
          ok: post?.ok ?? true,
          status: post?.ok === false ? 422 : 200,
          json: async () => post?.body ?? { name: "faidx", target: "t", holes: [], filled: {} },
        })
      : Promise.resolve({ ok: true, status: 200, json: async () => CATALOGUE }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/forge/sources"] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("sources", () => {
  it("puts what you can start at the top", async () => {
    at();
    await waitFor(() => expect(screen.getByText("nf-core:samtools/faidx")).toBeTruthy());
    const rows = screen.getAllByTestId("tool-row");
    expect(rows[0].getAttribute("data-state")).toBe("undrafted");
  });

  it("links a landed tool to its contract and a drafted one to the queue", async () => {
    at();
    const landed = await screen.findByRole("link", { name: /nf-core\/fastqc@0\.12\.1/ });
    expect(landed.getAttribute("href")).toBe("/forge/contracts/nf-core/fastqc@0.12.1");
    expect(screen.getByRole("link", { name: /picard/ }).getAttribute("href")).toContain(
      "/forge/queue",
    );
  });

  it("offers the form only on a tool you can start", async () => {
    // The half that must fail: a screen that always renders a form proves nothing below.
    at();
    await waitFor(() => expect(screen.getAllByLabelText("version").length).toBe(2));
    expect(screen.getAllByLabelText("version").length).toBe(
      CATALOGUE.rows.filter((r) => r.state === "undrafted").length,
    );
  });

  it("sends no path in the draft body", async () => {
    // The boundary claim, held in the one place a future convenience parameter would break it.
    //
    // **`/draft it/i`, not `/draft/i`** — the state facet has a button called "drafted", and
    // the looser regex clicked that instead, filtering the list rather than submitting.
    const fetchMock = at();
    const version = (await screen.findAllByLabelText("version"))[0];
    await userEvent.type(version, "1.24");
    await userEvent.type((await screen.findAllByLabelText("name"))[0], "faidx");
    await userEvent.click(screen.getAllByRole("button", { name: /draft it/i })[0]);

    await waitFor(() => {
      const posted = fetchMock.mock.calls.find((c) => c[1]?.method === "POST");
      expect(posted).toBeTruthy();
      expect(Object.keys(JSON.parse(posted![1].body)).sort()).toEqual([
        "name",
        "ref",
        "version",
      ]);
    });
  });

  it("renders the API's coded refusal on a name that is taken", async () => {
    at({ ok: false, body: { detail: "MF0010: a draft named 'faidx' already exists" } });
    await userEvent.type((await screen.findAllByLabelText("version"))[0], "1.24");
    await userEvent.type((await screen.findAllByLabelText("name"))[0], "faidx");
    await userEvent.click(screen.getAllByRole("button", { name: /draft it/i })[0]);

    // `Refusal` renders a code twice — in the message and in the `forge explain` hint.
    await waitFor(() => expect(screen.getAllByText(/MF0010/).length).toBe(2));
  });
});
