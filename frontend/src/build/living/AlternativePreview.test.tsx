import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS, fakePreview } from "./fake";
import { framed } from "./frame";
import { LivingSurface } from "./LivingSurface";

/** The complete preview on the surface: what opens it, what cannot close it, what it forbids,
 *  and that the build underneath comes back exactly as it was. */

const SESSION = framed(FAKE_SESSION, FAKE_STEPS, FAKE_CHANNELS);

function surface({ session = SESSION, read = vi.fn(async (path: string) =>
  fakePreview(session, path.split("?")[0].split("/").pop()!)) } = {}) {
  const props = {
    session, graph: session.graph,
    state: { ...initialAuthoring, snapshot: session },
    preview: null, busy: () => false,
    onAccept: vi.fn(), onReject: vi.fn(), onPreviewOption: vi.fn(), onSelect: vi.fn(),
    onCompose: vi.fn(), onSay: vi.fn(), onRetry: vi.fn(), onAddStep: vi.fn(), onDismiss: vi.fn(),
    onSetParam: vi.fn(), onApplyChange: vi.fn(), onEdit: vi.fn(),
    run: { onRun: vi.fn(), busy: false, stage: null, error: null, kept: false, sheet: null },
    readPreview: read,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingSurface {...props} />
    </QueryClientProvider>,
  );
  return { props, read };
}

const option = () => screen.getByTestId("option-alt_1");

describe("the complete preview", () => {
  it("opens on hover, closes on leaving, and is read once however often it is looked at", async () => {
    const { read } = surface();
    fireEvent.mouseEnter(option());
    await screen.findByTestId("alternative-preview");
    fireEvent.mouseLeave(option());
    expect(screen.queryByTestId("alternative-preview")).toBeNull();
    fireEvent.mouseEnter(option());
    await screen.findByTestId("alternative-preview");
    expect(read).toHaveBeenCalledTimes(1);
  });

  it("opens on keyboard focus as well", async () => {
    surface();
    fireEvent.focus(within(option()).getByRole("radio"));
    await screen.findByTestId("alternative-preview");
  });

  it("stays pinned through hover and focus elsewhere, and Escape returns focus to Preview", async () => {
    surface();
    const button = screen.getByTestId("preview-alt_1");
    button.focus();
    fireEvent.click(button);
    await screen.findByTestId("alternative-preview");
    fireEvent.mouseLeave(option());
    fireEvent.mouseEnter(screen.getByTestId("option-keep"));
    fireEvent.mouseLeave(screen.getByTestId("option-keep"));
    expect(screen.getByTestId("alternative-preview")).toBeInTheDocument();
    screen.getByTestId("accept-step").focus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("alternative-preview")).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it("keeps the build mounted, hidden and inert, and gives it back unchanged", async () => {
    surface();
    const build = screen.getByTestId("build-canvas");
    fireEvent.click(screen.getByTestId("preview-alt_1"));
    await screen.findByTestId("alternative-preview");
    expect(screen.getByTestId("build-canvas")).toBe(build);
    expect(build).toHaveClass("hidden");
    expect(build).toHaveAttribute("inert");
    fireEvent.click(screen.getByTestId("preview-close"));
    expect(screen.getByTestId("build-canvas")).toBe(build);
    expect(build).not.toHaveAttribute("inert");
  });

  it("cannot be edited while it shows: no step moves, and nothing can be added", async () => {
    surface();
    fireEvent.click(screen.getByTestId("preview-alt_1"));
    const preview = await screen.findByTestId("alternative-preview");
    const node = within(preview).getByTestId("living-node-samtools_sormadup");
    fireEvent.pointerDown(node, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(node, { clientX: 80, clientY: 60, pointerId: 1 });
    fireEvent.pointerUp(node, { pointerId: 1 });
    expect(within(preview).queryByTestId("tidy")).toBeNull();
    expect(within(preview).queryByTestId("add-step")).toBeNull();
  });

  it("choosing the alternative still sends the card's own checked offer", async () => {
    const { props } = surface();
    fireEvent.click(screen.getByTestId("preview-alt_1"));
    await screen.findByTestId("alternative-preview");
    fireEvent.click(within(option()).getByRole("radio"));
    fireEvent.click(screen.getByTestId("accept-step"));
    expect(props.onAccept).toHaveBeenCalledWith(SESSION.pending_proposal, "alt_1", undefined, undefined);
  });

  it("says a failed read beside the build, and asks again only on Retry", async () => {
    const read = vi.fn(async () => { throw new Error("refused"); });
    surface({ read: read as never });
    fireEvent.click(screen.getByTestId("preview-alt_1"));
    await screen.findByTestId("preview-error");
    expect(screen.getByTestId("build-canvas")).not.toHaveClass("hidden");
    fireEvent.click(screen.getByTestId("preview-alt_1"));
    fireEvent.click(screen.getByTestId("preview-alt_1"));
    expect(read).toHaveBeenCalledTimes(1);
    fireEvent.click(await screen.findByTestId("preview-retry"));
    await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  });

  it("offers no Preview for an alternative with no saved preview", () => {
    const legacy = { ...SESSION, pending_proposal: { ...SESSION.pending_proposal!, envelope: undefined } };
    surface({ session: legacy as unknown as AuthoringSession });
    expect(screen.queryByTestId("preview-alt_1")).toBeNull();
  });

  it("a stale build still says so beside a preview", async () => {
    const stale = { ...SESSION, canvas: { ...SESSION.canvas!, current: false } };
    surface({ session: stale as AuthoringSession });
    expect(screen.getByTestId("canvas-stale")).toBeInTheDocument();
  });
});
