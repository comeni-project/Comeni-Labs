import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { ConnectionSetup } from "./ConnectionSetup";

function draw(extra: Partial<React.ComponentProps<typeof ConnectionSetup>> = {}) {
  const onSave = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ConnectionSetup names={[]} defaultAllowed suggestDefault pending={false} error={null}
      onSave={onSave} onCancel={vi.fn()} {...extra} />
  </QueryClientProvider>);
  return onSave;
}
const response = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
afterEach(() => vi.unstubAllGlobals());

it("detects a local server, lets the person click a model, and finishes without typing", async () => {
  const fetch = vi.fn().mockResolvedValue(response([
    { endpoint: "http://ollama:11434", models: ["ollama_chat/gemma3:4b", "ollama_chat/qwen:7b"] },
  ]));
  vi.stubGlobal("fetch", fetch);
  const save = draw();
  await userEvent.click(screen.getByRole("button", { name: /Ollama Models on/ }));
  await userEvent.click(await screen.findByRole("button", { name: "gemma3:4b" }));
  expect(screen.getByRole("heading", { name: "Ready to connect" })).toBeTruthy();
  expect(screen.queryByLabelText("API key")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Finish setup" }));
  expect(save).toHaveBeenCalledWith({ connection: { name: "Ollama", provider: "ollama", server: "ollama",
    endpoint: "http://ollama:11434", key: null }, model: "ollama_chat/gemma3:4b", useDefault: true });
  expect(fetch).toHaveBeenCalledWith("/api/settings/models/detect", expect.objectContaining({ body: JSON.stringify({ provider: "ollama" }) }));
});

it("needs only a key for a cloud provider and preserves nested model IDs", async () => {
  const fetch = vi.fn().mockResolvedValue(response({ ok: true, says: "Found models", values: ["openai/anthropic/claude-test"] }));
  vi.stubGlobal("fetch", fetch);
  const save = draw({ names: ["OpenRouter"] });
  await userEvent.click(screen.getByRole("button", { name: /OpenRouter Multiple providers/ }));
  expect(screen.getByRole("button", { name: "Connect & find models" }).hasAttribute("disabled")).toBe(true);
  await userEvent.type(screen.getByLabelText("API key"), "sk-test");
  await userEvent.click(screen.getByRole("button", { name: "Connect & find models" }));
  await userEvent.click(await screen.findByRole("button", { name: "anthropic/claude-test" }));
  await userEvent.click(screen.getByRole("button", { name: "Assign later" }));
  await userEvent.click(screen.getByRole("button", { name: "Finish setup" }));
  expect(save).toHaveBeenCalledWith({ connection: { name: "OpenRouter 2", provider: "openrouter", server: "hosted",
    endpoint: "https://openrouter.ai/api/v1", key: "sk-test" }, model: "openai/anthropic/claude-test", useDefault: false });
});

it("does not advance on a refused key and lets the person correct it", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: false, says: "The API key was not accepted.", values: [] })));
  draw();
  await userEvent.click(screen.getByRole("button", { name: /OpenAI API Connect with/ }));
  await userEvent.type(screen.getByLabelText("API key"), "wrong-key");
  await userEvent.click(screen.getByRole("button", { name: "Connect & find models" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The API key was not accepted.");
  expect(screen.getByRole("heading", { name: "Connect to OpenAI API" })).toBeTruthy();
  await userEvent.clear(screen.getByLabelText("API key"));
  expect(screen.queryByRole("alert")).toBeNull();
});

it("reuses a saved key when checking an unchanged connection and saves null to retain it", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: true, says: "Found models", values: ["openai/test-model"] })));
  const save = draw({ initial: { name: "My OpenAI", provider: "openai", server: "hosted", endpoint: "https://api.openai.com/v1", key: { set: true, last4: "1234" } } });
  await userEvent.click(screen.getByRole("button", { name: "Connect & find models" }));
  await userEvent.click(await screen.findByRole("button", { name: "test-model" }));
  await userEvent.click(screen.getByRole("button", { name: "Finish setup" }));
  expect(save.mock.calls[0][0].connection.key).toBeNull();
  expect(fetch).toHaveBeenCalledWith("/api/settings/models.connections/items/My%20OpenAI/models", expect.anything());
});

it("ignores a late local detection after going back and choosing another provider", async () => {
  let answer: (value: unknown) => void = () => {};
  vi.stubGlobal("fetch", vi.fn(() => new Promise((resolve) => { answer = resolve; })));
  draw();
  await userEvent.click(screen.getByRole("button", { name: /Ollama Models on/ }));
  await userEvent.click(screen.getByRole("button", { name: "← Back" }));
  await userEvent.click(screen.getByRole("button", { name: /OpenAI API Connect with/ }));
  answer(response([{ endpoint: "http://ollama:11434", models: ["ollama_chat/late"] }]));
  await waitFor(() => expect(screen.getByRole("heading", { name: "Connect to OpenAI API" })).toBeTruthy());
  expect(screen.queryByRole("button", { name: "late" })).toBeNull();
});
