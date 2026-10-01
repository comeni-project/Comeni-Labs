import { afterEach, describe, expect, it, vi } from "vitest";

import { put, Refused } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("the client", () => {
  it("turns a 409 into a Refused carrying the coded detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 409,
      json: async () => ({ detail: "MI0300: building.pacing is locked: Pinned by .env" }),
    }));
    await expect(put("/settings/building.pacing", { value: "ask" }))
      .rejects.toEqual(new Refused("MI0300: building.pacing is locked: Pinned by .env"));
  });
});
