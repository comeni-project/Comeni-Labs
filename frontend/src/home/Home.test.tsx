import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

  it("draws what the system knows, and how well-founded each part is", async () => {
    // **Narrowed in phase 6, and the assertion narrowed with it.** This used to check for
    // "10 agree with their module" and "2 have no source that can re-read them" — which is now
    // exactly what the Tools board says, on the screen where you can act on it. Two places
    // answering one question is how a number goes stale in one of them, and the front door is
    // the one nobody would have corrected.
    at();
    await waitFor(() => expect(screen.getByText(/declared types/i)).toBeTruthy());
    expect(screen.getByText(/measurements a rule may read/i)).toBeTruthy();
    expect(screen.queryByText(/agree with the module/i)).toBeNull();
    // **Scoped, because `/nf-core/` alone is now ambiguous.** The hero quotes a contract id out
    // of a real `pipeline.yml`, so the bare pattern matches twice — which is the assertion
    // earning its keep rather than failing: the thing under test is that the block names where
    // the registry was READ FROM, and that is a different claim from a string appearing on the
    // page somewhere.
    expect(screen.getByText(/read from nf-core/i)).toBeTruthy();

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

  it("renders the same excerpt whatever the API says", async () => {
    // **The line between illustration and listing**, and the reason the hero is allowed to show
    // a contract id at all. The excerpt is quoted from
    // `notes/audits/fixtures/pipeline-v1/pipeline.yml` and is STATIC: it is documentation of the
    // artifact's format, not a view of the registry's current contents. The moment it varies
    // with the response it has become the Overview page that was cut (spec §1).
    at(QUIET);
    const quiet = (await screen.findByTestId("artifact")).textContent;
    cleanup();
    vi.unstubAllGlobals();

    at(BUSY);
    const busy = (await screen.findByTestId("artifact")).textContent;
    expect(busy).toBe(quiet);
    expect(busy).toContain("please review");
  });

  it("says the builder is not built rather than showing it as empty", async () => {
    // An absence is not a zero — the same discipline as `pipeline_pins: None`.
    at();
    await waitFor(() => expect(screen.getByText(/not built yet/i)).toBeTruthy());
    expect(screen.queryByText(/0 pipelines/i)).toBeNull();
  });
});
