import { describe, expect, it } from "vitest";

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
