import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

const QUESTION = {
  subject: "roles", what: "the job this contract does",
  why_open: "a module declares no role", band: "routing",
  asked_by: ["fastqc"], closed: true, evidence: [], suggested: null,
  candidates: [{ value: "qc_per_sample", note: "7 contracts" },
               { value: "alignment", note: "6 contracts" }],
};

function open(fetchImpl: typeof fetch) {
  vi.stubGlobal("fetch", fetchImpl);
  const client = new QueryClient({ defaultOptions: {
    queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/forge/queue/question/roles"] });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

afterEach(() => vi.unstubAllGlobals());

describe("answering one question", () => {
  it("offers the candidates the API said were legal", async () => {
    open(vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ questions: [QUESTION], total: 1 }),
    }) as unknown as typeof fetch);

    await waitFor(() => expect(screen.getByText("qc_per_sample")).toBeTruthy());
    expect(screen.getByText("alignment")).toBeTruthy();
  });

  it("will not submit without a reason", async () => {
    // Every value carries a reason a reader can act on. The UI is the one place that could
    // quietly break that, so Accept stays disabled until there is one.
    open(vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ questions: [QUESTION], total: 1 }),
    }) as unknown as typeof fetch);

    await waitFor(() => expect(screen.getByText("qc_per_sample")).toBeTruthy());
    await userEvent.click(screen.getByLabelText("qc_per_sample"));
    expect(screen.getByRole("button", { name: /accept/i })).toBeDisabled();
  });

  it("shows the API's refusal rather than a generic failure", async () => {
    const fetchImpl = vi.fn((url: string, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve({ ok: false, status: 422,
            json: async () => ({ detail: "MF0003: 'alignment' is not legal for roles" }) })
        : Promise.resolve({ ok: true, status: 200,
            json: async () => ({ questions: [QUESTION], total: 1 }) }));
    open(fetchImpl as unknown as typeof fetch);

    await waitFor(() => expect(screen.getByText("alignment")).toBeTruthy());
    await userEvent.click(screen.getByLabelText("alignment"));
    await userEvent.type(screen.getByLabelText(/reason/i), "trying it");
    await userEvent.click(screen.getByRole("button", { name: /accept/i }));

    await waitFor(() => expect(screen.getByText(/MF0003/)).toBeTruthy());
  });
});
