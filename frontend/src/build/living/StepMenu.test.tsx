import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { makeClient } from "../../app/queryClient";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { framed } from "./frame";
import { MemoryRouter } from "react-router";
import { LivingSurface } from "./LivingSurface";

/** A step's tools open from the step itself (#499): a menu, and one card beside the step, while
 *  the conversation stays where it is. */

afterEach(() => vi.unstubAllGlobals());

const idle = { ...FAKE_SESSION, working: false } as AuthoringSession;

function surface(session: AuthoringSession = idle, selected: string | null = null) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })));
  const props = {
    session: framed(session, FAKE_STEPS, FAKE_CHANNELS), graph: session.graph, preview: null,
    selected, onSelect: vi.fn(), composer: "", onCompose: vi.fn(), sending: [], onSay: vi.fn(),
    onAnswer: vi.fn(), onRetry: vi.fn(), onReviewed: vi.fn(), onDismiss: vi.fn(), onAddStep: vi.fn(),
    onSetParam: vi.fn(), onEdit: vi.fn(),
  };
  const view = render(<MemoryRouter><QueryClientProvider client={makeClient()}><LivingSurface {...props} /></QueryClientProvider></MemoryRouter>);
  const again = (next: Partial<typeof props>) =>
    view.rerender(<MemoryRouter><QueryClientProvider client={makeClient()}><LivingSurface {...props} {...next} /></QueryClientProvider></MemoryRouter>);
  return { props, again };
}

const node = (id: string) => screen.getByTestId(`living-node-${id}`);
const items = () => within(screen.getByRole("menu")).getAllByRole("menuitem").map((i) => i.textContent);

describe("the step menu", () => {
  it("opens on a right-click with the items the step allows", () => {
    surface();
    fireEvent.contextMenu(node("star_align"));
    expect(items()).toEqual(["Ask about this step", "Settings…", "Swap tool…", "Show in pipeline file",
      "Looks right", "Remove step…"]);
    expect(screen.queryByText(/Why is it here/)).toBeNull();
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    fireEvent.contextMenu(node("trimgalore"));
    expect(items()).not.toContain("Looks right");
  });

  it("works from the keyboard, and gives focus back to the step", () => {
    surface();
    node("star_align").focus();
    fireEvent.keyDown(node("star_align"), { key: "F10", shiftKey: true });
    const menu = screen.getByRole("menu");
    expect(document.activeElement).toHaveTextContent("Ask about this step");
    fireEvent.keyDown(menu, { key: "ArrowDown" });
    expect(document.activeElement).toHaveTextContent("Settings…");
    fireEvent.keyDown(menu, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(node("star_align"));
  });

  it("names the step in the composer for Ask about this step", () => {
    const { props } = surface();
    fireEvent.contextMenu(node("star_align"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Ask about this step" }));
    expect(props.onCompose).toHaveBeenCalledWith("About STAR_ALIGN: ");
  });

  it("reviews the AI's step with Looks right", () => {
    const { props } = surface();
    fireEvent.contextMenu(node("star_align"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Looks right" }));
    expect(props.onReviewed).toHaveBeenCalledWith("star_align");
  });

  it("removes a step only after asking, through the edit", () => {
    const { props } = surface();
    fireEvent.contextMenu(node("star_align"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove step…" }));
    const card = screen.getByRole("region", { name: "remove STAR_ALIGN" });
    expect(props.onEdit).not.toHaveBeenCalled();
    fireEvent.click(within(card).getByRole("button", { name: "Remove STAR_ALIGN" }));
    expect(props.onEdit.mock.calls[0][0].nodes.map((n: { id: string }) => n.id)).not.toContain("star_align");
  });

  it("opens the swap card from Swap tool…", () => {
    surface();
    fireEvent.contextMenu(node("star_align"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Swap tool…" }));
    expect(screen.getByRole("region", { name: "step card STAR_ALIGN" })).toBeInTheDocument();
  });
});

describe("the menu and the card together (plan 2 review)", () => {
  it("closes the menu when another step is clicked, and opens that step's card", () => {
    surface();
    fireEvent.contextMenu(node("star_align"));
    fireEvent.click(node("trimgalore"));
    expect(screen.queryByRole("menu")).toBeNull();
    expect(within(screen.getByRole("tabpanel", { name: "Step" })).getByRole("heading", { name: "TRIMGALORE" }))
      .toBeInTheDocument();
  });

  it("closes the menu on a click on the empty canvas", () => {
    surface();
    fireEvent.contextMenu(node("star_align"));
    fireEvent.click(screen.getByTestId("canvas"));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("Settings… opens the step in the Step tab", () => {
    surface();
    node("star_align").focus();
    fireEvent.keyDown(node("star_align"), { key: "F10", shiftKey: true });
    fireEvent.click(screen.getByRole("menuitem", { name: "Settings…" }));
    expect(screen.getByRole("tab", { name: "Step" })).toHaveAttribute("aria-selected", "true");
    expect(within(screen.getByRole("tabpanel", { name: "Step" })).getByRole("heading", { name: "STAR_ALIGN" }))
      .toBeInTheDocument();
  });
});

describe("a step's card", () => {
  it("opens in the Step tab on a click, and the conversation stays mounted", () => {
    surface(idle, "star_align");
    const card = screen.getByRole("tabpanel", { name: "Step" });
    expect(within(card).getByRole("region", { name: "What the AI chose" })).toBeInTheDocument();
    expect(screen.getByRole("log", { name: "conversation", hidden: true })).toBeInTheDocument();
  });

  it("closes when its step is no longer in the pipeline", () => {
    const { again } = surface(idle, "star_align");
    const without = { ...idle, graph: { ...idle.graph, nodes: idle.graph.nodes.filter((n) => n.id !== "star_align") } };
    again({ session: framed(without as AuthoringSession, FAKE_STEPS, FAKE_CHANNELS), graph: without.graph });
    expect(screen.queryByRole("region", { name: "step card STAR_ALIGN" })).toBeNull();
  });
});
