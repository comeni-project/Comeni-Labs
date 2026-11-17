import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { ChatgptSignin } from "./ChatgptSignin";

afterEach(() => vi.unstubAllGlobals());

it("shows a storage failure accurately and recovers when the person retries", async () => {
  let attempts = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const start = url.endsWith("/sign-in");
    if (start) attempts++;
    const failed = start && attempts === 1;
    const body = failed ? { detail: "Comeni cannot write its ChatGPT sign-in folder. Repair folder permissions." }
      : start ? { session: "test", user_code: "TEST-CODE", verification_url: "https://auth.openai.com/codex/device", interval: 5, expires_at: Date.now() / 1000 + 900 }
      : url.endsWith("/chatgpt") ? { signed_in: false } : { state: "pending" };
    return { ok: !failed, status: failed ? 503 : 200, json: async () => body };
  }));
  render(<QueryClientProvider client={new QueryClient()}><ChatgptSignin onReady={vi.fn()} /></QueryClientProvider>);
  const button = await screen.findByRole("button", { name: "Continue with ChatGPT" });
  await userEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent("Repair folder permissions.");
  await userEvent.click(button);
  expect(await screen.findByText("TEST-CODE")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByRole("link", { name: "Open sign-in page ↗" }).getAttribute("href")).toBe("https://auth.openai.com/codex/device");
});
