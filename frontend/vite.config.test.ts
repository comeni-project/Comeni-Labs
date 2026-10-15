// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import config from "./vite.config.ts";

afterEach(() => vi.unstubAllEnvs());

it("uses configured Compose ports for both APIs and preserves WebSocket forwarding", () => {
  vi.stubEnv("API_HOST_PORT", "58000");
  vi.stubEnv("WEB_HOST_PORT", "58080");
  vi.stubEnv("VITE_HOST_PORT", "55173");
  const value = config({ command: "serve", mode: "test" });
  expect(value.server?.proxy?.["/api"]).toBe("http://127.0.0.1:58000");
  expect(value.server?.proxy?.["/api/artifacts"]).toBe("http://127.0.0.1:58080");
  expect(value.server?.proxy?.["/api/runs"]).toEqual({
    target: "http://127.0.0.1:58080", ws: true,
  });
  expect(value.server?.host).toBe("127.0.0.1");
  expect(value.server?.port).toBe(55173);
  expect(value.server?.strictPort).toBe(true);
});
