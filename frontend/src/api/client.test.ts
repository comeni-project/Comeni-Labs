import { afterEach, describe, expect, it, vi } from "vitest";

import { postForm, put, Refused } from "./client";

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

  it("turns a coded 403 into a Refused", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 403, json: async () => ({ detail: "MI0213: the level is sealed" }),
    }));
    await expect(postForm("/x/samples", new FormData()))
      .rejects.toEqual(new Refused("MI0213: the level is sealed"));
  });

  // Issue 228: a proxy's own 403 page is not this API refusing anything.
  it("leaves a 403 with no coded reason an error naming the path", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 403, json: async () => { throw new SyntaxError("<html>"); },
    }));
    const failed = postForm("/x/samples", new FormData());
    await expect(failed).rejects.not.toBeInstanceOf(Refused);
    await expect(failed).rejects.toThrow("/x/samples → 403");
  });
});
