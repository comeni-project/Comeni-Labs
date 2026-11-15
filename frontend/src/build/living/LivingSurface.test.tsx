import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { framed } from "./frame";
import { LivingSurface } from "./LivingSurface";

/** The builder's shell (#463), against the static session that carries every state the agent's
 *  thread can be in.
 *
 * **What these cannot see is how it looks** — the browser check is the record of that. These hold
 * the structure: which regions exist, what each state says, and what the layout does not depend on.
 */

function surface(session: AuthoringSession = FAKE_SESSION, overrides = {}) {
  const props = {
    session: framed(session, FAKE_STEPS, FAKE_CHANNELS),
    graph: session.graph,
    preview: { revision: session.revision, state: "ready" as const, text: "version: 6\n", findings: [] },
    selected: null,
    onSelect: vi.fn(),
    composer: "",
    onCompose: vi.fn(),
    sending: [],
    onSay: vi.fn(),
    onAnswer: vi.fn(),
    onRetry: vi.fn(),
    onReviewed: vi.fn(),
    onDismiss: vi.fn(),
    onAddStep: vi.fn(),
    onSetParam: vi.fn(),
    onEdit: vi.fn(),
    ...overrides,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingSurface {...props} />
    </QueryClientProvider>,
  );
  return props;
}

const with_ = (changes: Partial<AuthoringSession>) =>
  ({ ...FAKE_SESSION, ...changes }) as AuthoringSession;

const idle = () => with_({ working: false, turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending") });

describe("the two surfaces", () => {
  it("has a canvas, one conversation, one header strip and a composer", () => {
    surface();
    expect(screen.getByRole("region", { name: "pipeline canvas" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "build panel" })).toBeInTheDocument();
    expect(screen.getByTestId("living-header")).toHaveTextContent("rnaseq-counts");
    expect(screen.getByRole("form", { name: "say something" })).toBeInTheDocument();
    expect(screen.getByRole("log", { name: "conversation" })).toHaveTextContent("I picked STAR over HISAT2");
  });

  it("swaps the canvas for what was understood, and back", () => {
    surface();
    fireEvent.click(screen.getByRole("radio", { name: "What was understood" }));
    expect(screen.getByRole("region", { name: "What was understood" })).toBeInTheDocument();
    expect(screen.getByTestId("build-canvas")).not.toBeVisible();
    fireEvent.click(screen.getByRole("radio", { name: "Canvas" }));
    expect(screen.getByTestId("build-canvas")).toBeVisible();
  });

  it("has a phone's three tabs, the conversation first", () => {
    surface();
    const tabs = screen.getByRole("tablist", { name: "on a phone" });
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Chat", "Canvas", "Understood"]);
    expect(screen.getByTestId("living").querySelector(".living")).toHaveAttribute("data-pane", "chat");
    fireEvent.click(within(tabs).getByRole("tab", { name: "Canvas" }));
    expect(screen.getByTestId("living").querySelector(".living")).toHaveAttribute("data-pane", "canvas");
  });

  it("keeps the canvas first in the document, whatever the stacked order draws", () => {
    // Stacked under 1000px the conversation is drawn first by CSS `order`; the canvas is still
    // what the page is about, so a screen reader meets it first.
    surface();
    const regions = screen.getAllByRole("region");
    expect(regions[0]).toHaveAccessibleName("pipeline canvas");
    expect(regions.findIndex((r) => r.getAttribute("aria-label") === "build panel")).toBeGreaterThan(0);
  });

  it("marks on the canvas the step the AI chose and nobody reviewed", () => {
    surface();
    expect(screen.getByTestId("node-ai-star_align")).toHaveTextContent(/^AI$/);
    expect(screen.queryByTestId("node-ai-trimgalore")).toBeNull();
  });

  it("opens a step over the conversation, with what the AI chose there and Looks right", () => {
    const props = surface(FAKE_SESSION, { selected: "star_align" });
    const sheet = screen.getByRole("region", { name: "step STAR_ALIGN" });
    expect(within(sheet).getByRole("region", { name: "What the AI chose" }))
      .toHaveTextContent("chose nf-core/star/align@2.7.11b");
    fireEvent.click(within(sheet).getByRole("button", { name: "Looks right" }));
    expect(props.onReviewed).toHaveBeenCalledWith("star_align");
  });
});

describe("the states a session can be in", () => {
  it("shows the agent working, and the composer stays open (issue 392)", () => {
    surface();
    expect(screen.getByRole("status", { name: "working" })).toHaveTextContent("Read SAMTOOLS_SORT");
    expect(screen.getByTestId("living-status")).toHaveTextContent("working");
    expect(screen.getByTestId("composer")).not.toBeDisabled();
  });

  it("restores a session with nothing working as built, with the whole conversation", () => {
    surface(idle());
    expect(screen.queryByRole("status", { name: "working" })).toBeNull();
    expect(screen.getByTestId("living-status")).toHaveTextContent("built");
    expect(screen.getByRole("log", { name: "conversation" })).toHaveTextContent("and what does the sorter do?");
  });

  it("says what the empty canvas is waiting for", () => {
    surface(with_({ graph: { nodes: [], edges: [] }, placement: {} }));
    expect(screen.getByText("The agent is working — steps appear here as it builds them")).toBeInTheDocument();
  });

  it("says plainly when no model is configured", () => {
    surface(with_({ model_configured: false }));
    expect(screen.getByTestId("no-model")).toHaveTextContent("No model is configured here");
  });

  it("offers Retry on the turn that failed, and sends that turn", () => {
    const props = surface(idle());
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(props.onRetry).toHaveBeenCalledWith(3);
  });

  it("answers only the newest question", () => {
    const asked = with_({ working: false, turns: FAKE_SESSION.turns.slice(0, 2) });
    const props = surface(asked);
    fireEvent.click(within(screen.getByRole("group", { name: "Are the reads stranded?" }))
      .getByRole("button", { name: "unstranded" }));
    expect(props.onAnswer).toHaveBeenCalledWith("q-strand", "unstranded");
    // Further on, the person has said more since; the question is a line in the record.
    surface(idle());
    expect(screen.getAllByText("Asked: Are the reads stranded?").length).toBeGreaterThan(0);
  });

  it("shows a server refusal as an alert that can be dismissed", () => {
    const props = surface(FAKE_SESSION, {
      notice: { code: "MI0201", text: "the pipeline changed since you last saw it" } });
    expect(screen.getByTestId("living-notice")).toHaveTextContent("MI0201");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(props.onDismiss).toHaveBeenCalledOnce();
  });
});

describe("the pipeline file", () => {
  it("takes the canvas's place, and the canvas comes back as it was", () => {
    surface();
    fireEvent.click(screen.getByTestId("living-view-artifact"));
    expect(screen.getByTestId("pipeline-file")).toBeInTheDocument();
    expect(screen.getByTestId("artifact-text")).toHaveTextContent("version: 6");
    expect(screen.getByTestId("build-canvas").closest(".living")).toHaveStyle({ display: "none" });

    fireEvent.click(screen.getByTestId("living-view-canvas"));
    expect(screen.queryByTestId("pipeline-file")).toBeNull();
    expect(screen.getByTestId("build-canvas").closest(".living")).not.toHaveStyle({ display: "none" });
  });
});
