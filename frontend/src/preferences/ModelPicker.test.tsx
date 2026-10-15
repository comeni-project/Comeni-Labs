import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelPicker } from "./ModelPicker";
import type { Entry, Menu } from "./usePreferences";

const HELP = "Phrases the questions the build asks you and reads your replies.";
const MENU = {
  sections: [{ key: "models", title: "Models", order: 3, served_by: "mendel", entries: [{
    setting: { key: "models.connections", kind: "collection", label: "Connections", help: HELP },
    shown: { value: [{ name: "Local", server: "ollama", endpoint: "http://o:11434", key: { set: false, last4: null } }],
             source: "installation", locked: false, reason: null },
  }] }],
} as unknown as Menu;
const ENTRY = {
  setting: { key: "models.talk", label: "Talking with you", help: HELP, kind: "model", of: "models.connections", default: null },
  shown: { value: null, source: "default", locked: false, reason: null },
} as unknown as Entry;

afterEach(() => vi.unstubAllGlobals());

describe("the model picker", () => {
  it("offers the default and every listed model, and writes a choice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ ok: true, says: "2 models", values: ["ollama_chat/gemma3:4b", "ollama_chat/qwen2.5:7b"] }),
    }));
    const onWrite = vi.fn();
    render(<QueryClientProvider client={new QueryClient()}>
      <ModelPicker entry={ENTRY} menu={MENU} onWrite={onWrite} />
    </QueryClientProvider>);
    const select = screen.getByRole("combobox", { name: "Talking with you" });
    await waitFor(() => expect(screen.getByRole("option", { name: "Local · gemma3:4b" })).toBeTruthy());
    expect(screen.getByRole("option", { name: "Same as the default" })).toBeTruthy();
    await userEvent.selectOptions(select, "Local · gemma3:4b");
    expect(onWrite).toHaveBeenCalledWith({ connection: "Local", model: "ollama_chat/gemma3:4b" });
  });

  it("says which connection could not be listed, and still offers Other", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ModelPicker entry={ENTRY} menu={MENU} onWrite={vi.fn()} />
    </QueryClientProvider>);
    expect(await screen.findByText("Could not list models on Local.")).toBeTruthy();
    expect(screen.getByRole("option", { name: "Other…" })).toBeTruthy();
  });

  it("says what the server said when a connection could not list its models", async () => {
    // Review M4, re-graded: an `ok: false` answer is not an error to the query, so say it here.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ ok: false, says: "Could not list models at http://o:11434 (ConnectError).", values: [] }),
    }));
    render(<QueryClientProvider client={new QueryClient()}>
      <ModelPicker entry={ENTRY} menu={MENU} onWrite={vi.fn()} />
    </QueryClientProvider>);
    expect(await screen.findByText("Could not list models on Local.")).toBeTruthy();
  });
});
