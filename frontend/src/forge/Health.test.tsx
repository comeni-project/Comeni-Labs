import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Health } from "./Queue";

function withStrip(strip: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => strip }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Health />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the health strip", () => {
  it("withholds the counts until a check has actually run", async () => {
    // Found by running against a fresh database: matching is 0 because nothing was
    // MEASURED, not because nothing matches. "0 match their source" reads as
    // catastrophe when the truth is "unknown".
    withStrip({ contracts: 12, matching: 0, unverifiable: 0, types: 22, checked_at: null });
    await waitFor(() => expect(screen.getByText(/not checked yet/)).toBeTruthy());
    expect(screen.queryByText(/match their source/)).toBeNull();
  });

  it("shows them once one has", async () => {
    withStrip({
      contracts: 12, matching: 10, unverifiable: 2, types: 22,
      checked_at: "2026-08-18T13:54:00Z",
    });
    await waitFor(() => expect(screen.getByText(/match their source/)).toBeTruthy());
    expect(screen.getByText(/unverifiable/)).toBeTruthy();
  });
});
