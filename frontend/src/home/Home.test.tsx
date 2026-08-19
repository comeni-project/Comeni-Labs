import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const STANDING = {
  contracts: 12,
  matching: 10,
  unverifiable: 2,
  drifted: 0,
  types: 22,
  roles: 9,
  rules: 1,
  measurements: 12,
  sources: ["nf-core"],
  undrafted: 3,
};

const QUIET = {
  forge: [
    {
      what: "3 tools nobody has drafted",
      where: "/forge/sources?state=undrafted",
      count: 3,
      urgency: "idle",
    },
  ],
  mendel: [],
  standing: STANDING,
};

const BUSY = {
  forge: [
    {
      what: "1 contract no longer matches its source",
      where: "/forge/contracts?against=drifted",
      count: 1,
      urgency: "blocking",
    },
    { what: "11 questions waiting on a decision", where: "/forge/queue", count: 11, urgency: "waiting" },
    {
      what: "3 tools nobody has drafted",
      where: "/forge/sources?state=undrafted",
      count: 3,
      urgency: "idle",
    },
  ],
  mendel: [],
  standing: { ...STANDING, drifted: 1, matching: 9 },
};

function at(body: unknown = QUIET) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }),
  );
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the front door", () => {
  it("says what this is", async () => {
    // The question a stranger has, and the one no destination answers. The repository is
    // public and this is the first screen.
    at();
    await waitFor(() =>
      expect(screen.getByText(/traces to a constraint, a convention, a measurement/i)).toBeTruthy(),
    );
  });

  it("draws what the registry holds, and how well-founded each part is", async () => {
    // **Not the bare total.** The block says 10 agree and 2 cannot be re-read rather than
    // "12 contracts", because the split is the informative half — a contract nothing checks
    // is not a contract that agrees. Each row carries the stroke that says which it is.
    at();
    await waitFor(() => expect(screen.getByText(/agree with the module/i)).toBeTruthy());
    expect(screen.getByText(/have no source that can re-read them/i)).toBeTruthy();
    expect(screen.getByText(/nf-core/)).toBeTruthy();

    const grounds = screen
      .getAllByTestId("ground")
      .map((el) => el.getAttribute("data-ground"));
    expect(new Set(grounds).size).toBeGreaterThan(1);
  });

  it("leads with what needs a person, worst first", async () => {
    at(BUSY);
    const calls = await screen.findAllByTestId("call");
    expect(calls[0].getAttribute("data-urgency")).toBe("blocking");
    expect(calls.map((c) => c.getAttribute("data-urgency"))).toEqual([
      "blocking",
      "waiting",
      "idle",
    ]);
  });

  it("directs rather than apologises when nothing is waiting", async () => {
    // Today's real screen: 0 open questions, 0 drift. `dashboard.md` §7 — an empty state
    // directs, and this is the largest empty state in the product.
    at();
    await waitFor(() => expect(screen.getByText(/nothing is waiting on you/i)).toBeTruthy());
    expect(screen.queryByText(/no data|nothing to show|error/i)).toBeNull();
  });

  it("never lists a question, a contract or a drift row", async () => {
    // **The discipline the whole page rests on** — spec §1. An Overview page was designed and
    // cut for answering the Queue's question; the moment this renders one row it has become
    // that page. A contract id or a question subject appearing here is the failure.
    at(BUSY);
    await screen.findAllByTestId("call");
    expect(screen.queryByText(/nf-core\/fastqc@/)).toBeNull();
    expect(screen.queryByText(/consumes\[0\]/)).toBeNull();
    expect(screen.queryAllByTestId("tool-row")).toHaveLength(0);
  });

  it("says the builder is not built rather than showing it as empty", async () => {
    // An absence is not a zero — the same discipline as `pipeline_pins: None`.
    at();
    await waitFor(() => expect(screen.getByText(/not built yet/i)).toBeTruthy());
    expect(screen.queryByText(/0 pipelines/i)).toBeNull();
  });
});
