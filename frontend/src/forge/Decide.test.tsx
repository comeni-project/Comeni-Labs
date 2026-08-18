import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Decide } from "./Decide";

const PROPOSAL = {
  id: "qc.index_stats",
  description: "per-reference index statistics",
  why: "nothing declared covers idxstats output",
  by: "rafael",
  decision: "open",
  decided_by: "",
  decided_why: "",
  decided_id: "",
};

function at(proposal = PROPOSAL) {
  const fetchImpl = vi.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ draft: "fastqc", subject: "produces[0].type_id",
                         value: "qc.index_stats", still_open: false }),
  });
  vi.stubGlobal("fetch", fetchImpl);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Decide draft="fastqc" subject="produces[0].type_id" proposal={proposal} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchImpl;
}

afterEach(() => vi.unstubAllGlobals());

describe("deciding a proposal", () => {
  it("shows what was proposed, by whom, and why", () => {
    at();
    expect(screen.getByText("qc.index_stats")).toBeTruthy();
    expect(screen.getByText(/idxstats output/)).toBeTruthy();
    expect(screen.getByText(/rafael/)).toBeTruthy();
  });

  it("will not decide without a reason", async () => {
    at();
    expect(screen.getByRole("button", { name: /^approve$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^reject$/i })).toBeDisabled();
  });

  it("approves under the proposed id by default", async () => {
    const fetchImpl = at();
    await userEvent.type(screen.getByLabelText(/reason/i), "a real distinct output");
    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));

    const body = JSON.parse(fetchImpl.mock.calls[0][1].body);
    expect(body.decision).toBe("approved");
    expect(body.id).toBeNull();
  });

  it("sends a different id when the reviewer renames it", async () => {
    // A rename is approve-with-a-different-id, not a third verb.
    const fetchImpl = at();
    await userEvent.clear(screen.getByLabelText(/approve as/i));
    await userEvent.type(screen.getByLabelText(/approve as/i), "qc.idxstats");
    await userEvent.type(screen.getByLabelText(/reason/i), "clearer");
    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));

    const body = JSON.parse(fetchImpl.mock.calls[0][1].body);
    expect(body.id).toBe("qc.idxstats");
  });

  it("shows a decided proposal as decided, with no buttons", () => {
    at({ ...PROPOSAL, decision: "rejected", decided_by: "reviewer",
         decided_why: "it is a measurement, not a type" });
    expect(screen.getByText(/measurement, not a type/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^approve$/i })).toBeNull();
  });
});
