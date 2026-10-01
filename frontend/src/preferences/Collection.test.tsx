import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Collection } from "./Collection";
import type { Entry } from "./usePreferences";

const HELP = "Where models are reached, from this machine or a provider.";
const field = (key: string, kind: string, extra = {}) => ({
  key, label: key.split(".")[1], help: HELP, kind, default: kind === "secret" ? null : "",
  env: null, options: [], minimum: null, maximum: null, unavailable: null, where: "installation",
  fields: [], item_name: "name", from_env: null, actions: [], of: null, ...extra,
});
const ENTRY = {
  setting: {
    ...field("models.connections", "collection", { default: [] }),
    label: "Connections", actions: ["test", "models"],
    fields: [field("connection.name", "text"), field("connection.endpoint", "text"), field("connection.key", "secret")],
  },
  shown: {
    value: [
      { name: "From .env", endpoint: "http://ollama:11434", key: { set: false, last4: null }, locked: true },
      { name: "Cloud", endpoint: "", key: { set: true, last4: "1234" } },
    ],
    source: "installation", locked: false, reason: null, set: null, last4: null,
  },
} as unknown as Entry;

function draw(onWrite = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Collection entry={ENTRY} onWrite={onWrite} />
    </QueryClientProvider>,
  );
  return onWrite;
}

afterEach(() => vi.unstubAllGlobals());

describe("connections", () => {
  it("shows each record, the env one locked", () => {
    draw();
    expect(screen.getByText("From .env")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Remove/ })).toHaveLength(1);
    expect(screen.getByText(/ending 1234/)).toBeTruthy();
  });

  it("adds a record and saves the list without the env record and without retyping keys", async () => {
    const onWrite = draw();
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await userEvent.type(screen.getByLabelText("name", { selector: "#new-name" }), "Local");
    await userEvent.type(screen.getByLabelText("endpoint", { selector: "#new-endpoint" }), "http://o:11434");
    await userEvent.click(screen.getByRole("button", { name: "Save connections" }));
    expect(onWrite).toHaveBeenCalledWith([
      { name: "Cloud", endpoint: "", key: null },
      { name: "Local", endpoint: "http://o:11434", key: null },
    ]);
  });

  it("runs an action and shows what it said", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ ok: true, says: "Something answers at http://ollama:11434.", values: [] }),
    }));
    draw();
    await userEvent.click(screen.getAllByRole("button", { name: "test" })[0]);
    expect(await screen.findByText(/Something answers/)).toBeTruthy();
  });
});
