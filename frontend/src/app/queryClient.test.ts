import { describe, expect, it } from "vitest";

import { Unauthorized } from "../wiener/api/client";
import { makeClient } from "./queryClient";

describe("the query client", () => {
  it("does not refetch on window focus", () => {
    // A 250ms endpoint refetched on every alt-tab was audit A137. The mutations invalidate
    // precisely, so the cache does not need refetch-on-everything propping it up.
    expect(makeClient().getDefaultOptions().queries?.refetchOnWindowFocus).toBe(false);
  });

  it("treats data as fresh for long enough that navigating feels instant", () => {
    const stale = makeClient().getDefaultOptions().queries?.staleTime;
    expect(stale).toBeGreaterThanOrEqual(30_000);
  });

  it("bounds that window rather than trusting the cache forever", () => {
    // The registry moves under the tool — the nightly check, a `forge land` in a terminal.
    // A screen left open must catch up on its own.
    const stale = makeClient().getDefaultOptions().queries?.staleTime;
    expect(stale).toBeLessThanOrEqual(5 * 60_000);
  });
});

describe("what it will not retry", () => {
  it("does not retry a refused credential", () => {
    // Three retries with backoff means seconds of spinner before the page can offer the field
    // that fixes it — and three requests with a token that is known to be wrong.
    const retry = makeClient().getDefaultOptions().queries?.retry as (
      count: number, error: Error,
    ) => boolean;
    expect(retry(0, new Unauthorized("no"))).toBe(false);
    expect(retry(0, new Error("a real failure"))).toBe(true);
  });
});
