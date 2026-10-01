import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SettingRow } from "./SettingRow";
import type { Entry } from "./usePreferences";

const HELP = "How the build walks you through its steps, one at a time.";

function entry(over: Record<string, unknown> = {}, shown: Record<string, unknown> = {}): Entry {
  return {
    setting: {
      key: "building.pacing", label: "Pacing", help: HELP, kind: "choice", default: "ask",
      env: null, options: [{ value: "together", label: "Together" }, { value: "ask", label: "Ask" }],
      minimum: null, maximum: null, unavailable: null, where: "installation", ...over,
    },
    shown: { value: "ask", source: "default", locked: false, reason: null, set: null, last4: null, ...shown },
  } as unknown as Entry;
}

describe("a setting row", () => {
  it("draws a choice and writes the option picked", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry()} onWrite={onWrite} />);
    await userEvent.click(screen.getByLabelText("Together"));
    expect(onWrite).toHaveBeenCalledWith("together");
    expect(screen.getByText("Default")).toBeTruthy();
  });

  it("greys a locked row, marks it, and says why in its ⓘ", async () => {
    const reason = { kind: "pinned", env: "COMENI_BUILD_PACING", says: "Pinned by .env (COMENI_BUILD_PACING). Change it there and restart." };
    render(<SettingRow entry={entry({}, { locked: true, source: "environment", reason })} onWrite={vi.fn()} />);
    expect((screen.getByLabelText("Together") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByLabelText("Locked")).toBeTruthy();
    expect(screen.getByText("Pinned by .env")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "About Pacing" }));
    expect(screen.getByText(/Change it there and restart/)).toBeTruthy();
  });

  it("marks a designed setting as not built", () => {
    const reason = { kind: "designed", where: "arrives with the consultant build", says: "Designed, not built yet: arrives with the consultant build." };
    render(<SettingRow entry={entry({}, { locked: true, reason })} onWrite={vi.fn()} />);
    expect(screen.getByText("not built")).toBeTruthy();
  });

  it("draws a toggle", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry({ kind: "toggle", options: [], default: false }, { value: false })} onWrite={onWrite} />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Pacing" }));
    expect(onWrite).toHaveBeenCalledWith(true);
  });

  it("draws a number and writes it on blur", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry({ kind: "number", options: [], default: 30 }, { value: 30 })} onWrite={onWrite} />);
    const box = screen.getByRole("spinbutton", { name: "Pacing" });
    await userEvent.clear(box);
    await userEvent.type(box, "45");
    await userEvent.tab();
    expect(onWrite).toHaveBeenCalledWith(45);
  });

  it("shows a set secret by its last four and never asks for it back", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry({ kind: "secret", options: [], default: null }, { value: null, set: true, last4: "1234" })} onWrite={onWrite} />);
    expect(screen.getByText(/ending 1234/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Replace" }));
    await userEvent.type(screen.getByLabelText("Pacing"), "sk-new-5678");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onWrite).toHaveBeenCalledWith("sk-new-5678");
  });

  it("draws a kind it does not know as read-only text", () => {
    render(<SettingRow entry={entry({ kind: "hologram", options: [] }, { value: "shimmer" })} onWrite={vi.fn()} />);
    expect(screen.getByText("shimmer")).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("shows a refusal under the row", () => {
    render(<SettingRow entry={entry()} onWrite={vi.fn()} refusal="MI0302: building.pacing: 'x' is not one of together, ask" />);
    expect(screen.getByText(/MI0302: building.pacing/)).toBeTruthy();
  });
});
