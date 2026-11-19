import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { ModelConnections } from "./ModelConnections";
import type { Entry, Menu } from "./usePreferences";

const entry = { setting: { key: "models.connections", fields: ["provider", "name", "server", "endpoint", "key"].map((key) => ({ key: `connection.${key}` })) }, shown: { value: [], locked: false } } as unknown as Entry;
const menu = { sections: [{ entries: [{ setting: { key: "models.default" }, shown: { value: null, locked: false } }] }] } as unknown as Menu;
afterEach(() => vi.unstubAllGlobals());

it("saves the connection before assigning the default model", async () => {
  const writes: { key: string; value: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === "PUT") writes.push({ key: url, value: JSON.parse(String(init.body)).value });
    return { ok: true, status: 200, json: async () => url.endsWith("/detect")
      ? [{ endpoint: "http://ollama:11434", models: ["ollama_chat/local"] }] : {} };
  }));
  render(<QueryClientProvider client={new QueryClient()}><ModelConnections entry={entry} menu={menu} /></QueryClientProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Add connection" }));
  await userEvent.click(screen.getByRole("button", { name: /Ollama Models on/ }));
  await userEvent.click(await screen.findByRole("button", { name: "local" }));
  await userEvent.click(screen.getByRole("button", { name: "Finish setup" }));
  await screen.findByText("Ollama saved and set as the default.");
  expect(writes).toEqual([
    { key: "/api/settings/models.connections", value: [{ provider: "ollama", name: "Ollama", server: "ollama", endpoint: "http://ollama:11434", key: null }] },
    { key: "/api/settings/models.default", value: { connection: "Ollama", model: "ollama_chat/local" } },
  ]);
});

it("removes only the chosen record and retains masked keys without storing environment records", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
  vi.stubGlobal("fetch", fetch);
  const populated = { ...entry, shown: { ...entry.shown, value: [
    { name: "From .env", provider: "custom", server: "ollama", endpoint: "http://env", locked: true },
    { name: "Keep", provider: "openai", server: "hosted", endpoint: "https://api.openai.com/v1", key: { set: true, last4: "1234" } },
    { name: "Remove", provider: "ollama", server: "ollama", endpoint: "http://ollama:11434" },
  ] } } as unknown as Entry;
  render(<QueryClientProvider client={new QueryClient()}><ModelConnections entry={populated} menu={menu} /></QueryClientProvider>);
  await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);
  await userEvent.click(screen.getByRole("button", { name: "Remove connection" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/settings/models.connections", expect.objectContaining({
    method: "PUT", body: JSON.stringify({ value: [{ provider: "openai", name: "Keep", server: "hosted", endpoint: "https://api.openai.com/v1", key: null }] }),
  })));
});

it("reuses an existing subscription sign-in and offers clickable account models", async () => {
  const writes: { key: string; value: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "PUT") writes.push({ key: url, value: JSON.parse(String(init.body)).value });
    const body = url.endsWith("/chatgpt") ? { signed_in: true }
      : url.endsWith("/chatgpt/models") ? { ok: true, says: "Found models", values: ["chatgpt/plan-model"] } : {};
    return { ok: true, status: 200, json: async () => body };
  }));
  render(<QueryClientProvider client={new QueryClient()}><ModelConnections entry={entry} menu={menu} /></QueryClientProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Add connection" }));
  await userEvent.click(screen.getByRole("button", { name: /ChatGPT subscription Use/ }));
  await userEvent.click(await screen.findByRole("button", { name: "plan-model" }));
  await userEvent.click(screen.getByRole("button", { name: "Finish setup" }));
  await screen.findByText("ChatGPT subscription saved and set as the default.");
  expect(writes[0].value).toEqual([{ provider: "chatgpt", name: "ChatGPT subscription", server: "hosted", endpoint: "", key: null }]);
  expect(writes[1].value).toEqual({ connection: "ChatGPT subscription", model: "chatgpt/plan-model", temperature: 1 });
});
