import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { Chat } from "./Chat";
import { FAKE_SESSION } from "./fake";

function chat(session: AuthoringSession = FAKE_SESSION, overrides = {}) {
  const props = { session, sending: [], failedPhase: false, onRetry: vi.fn(), onPoint: vi.fn(), ...overrides };
  render(<Chat {...props} />);
  return props;
}

describe("the chat holds speech", () => {
  it("draws what the person said and what the model said", () => {
    chat();
    const log = screen.getByRole("log", { name: "conversation" });
    expect(log).toHaveTextContent("I have 12 paired RNA-seq samples");
    expect(log).toHaveTextContent("why STAR and not HISAT2?");
    expect(log).toHaveTextContent("STAR is here because the reads are 150bp");
    expect(log).toHaveTextContent("you moved STAR_ALIGN on the canvas");
    expect(log).toHaveTextContent("The reply named an option nobody offered");
  });

  it("draws no card: an engine block in a reply is one line pointing at the Step panel", () => {
    chat();
    expect(screen.queryByRole("button", { name: /apply/i })).toBeNull();
    expect(screen.queryByRole("radio")).toBeNull();
    const pointers = screen.getAllByTestId("pointer");
    expect(pointers.length).toBeGreaterThan(0);
    expect(pointers.map((p) => p.textContent)).toEqual([
      "Read the goal — see Step",
      "Asked a question — see Step",
      "Asked for a setting on STAR_ALIGN — see Step",
      "Suggested a change: Swap the aligner — see Step",
    ]);
  });

  it("a pointer line takes the person to the step it is about", () => {
    const props = chat();
    fireEvent.click(screen.getByText("Suggested a change: Swap the aligner — see Step"));
    expect(props.onPoint).toHaveBeenCalledWith("star_align");
    fireEvent.click(screen.getByText("Asked a question — see Step"));
    expect(props.onPoint).toHaveBeenCalledWith(null);
  });

  it("leaves answered decisions out: they are the step line's", () => {
    chat();
    expect(screen.queryByText(/you chose/)).toBeNull();
    expect(screen.queryByText("Goal confirmed")).toBeNull();
  });

  it("says a reply is on its way, and draws a follow-up as sending", () => {
    chat(FAKE_SESSION, { sending: ["and the counter?"] });
    expect(screen.getByText(/The canvas is still yours/)).toBeInTheDocument();
    const sending = screen.getByTestId("saying");
    expect(sending).toHaveTextContent("and the counter?");
    expect(within(sending.closest("li")!).getByText("sending…")).toBeInTheDocument();
  });

  it("offers Try again on an unreachable model only while the session has failed", () => {
    const unreachable = {
      ...FAKE_SESSION,
      turns: [{ seq: 0, role: "assistant", state: "answered", base_revision: 0, at: "2026-01-01T00:00:00Z", text: "",
        blocks: [{ kind: "notice", id: "n", notice: "refusal", code: "MA0002", text: "No model answered." }] }],
    } as AuthoringSession;
    chat(unreachable);
    expect(screen.queryByTestId("retry")).toBeNull();
  });

  it("offers Try again on an unreachable model when the session has failed", () => {
    const unreachable = {
      ...FAKE_SESSION,
      turns: [{ seq: 0, role: "assistant", state: "answered", base_revision: 0, at: "2026-01-01T00:00:00Z", text: "",
        blocks: [{ kind: "notice", id: "n", notice: "refusal", code: "MA0002", text: "No model answered." }] }],
    } as AuthoringSession;
    const props = chat(unreachable, { failedPhase: true });
    fireEvent.click(screen.getByTestId("retry"));
    expect(props.onRetry).toHaveBeenCalled();
  });
});

describe("messages wait in line (issue 392)", () => {
  const person = (seq: number, text: string) =>
    ({ seq, role: "person", state: "answered", text, blocks: [], base_revision: 0, at: "" });
  const reply = (seq: number, state: string) =>
    ({ seq, role: "assistant", state, text: "", blocks: [], base_revision: 0, at: "" });
  const queued = {
    ...FAKE_SESSION,
    turns: [person(1, "what is a GTF?"), reply(2, "pending"), person(3, "and a GFF?"), reply(4, "pending")],
  } as unknown as AuthoringSession;

  it("marks a message behind another's reply as waiting, and not the one being answered", () => {
    chat(queued);
    const waiting = screen.getAllByTestId("waiting-in-line");
    expect(waiting).toHaveLength(1);
    expect(waiting[0].closest("li")).toHaveTextContent("and a GFF?");
    expect(waiting[0]).toHaveTextContent("waiting: I'll answer as soon as I finish the one above");
  });

  it("draws each message still sending", () => {
    chat(FAKE_SESSION, { sending: ["one", "two"] });
    expect(screen.getAllByTestId("saying").map((s) => s.textContent)).toEqual(["one", "two"]);
  });
});

describe("an announcement points at what it changed (one builder plan 3)", () => {
  const announced = (about: Record<string, string | null>) => ({
    ...FAKE_SESSION,
    turns: [{ seq: 1, role: "assistant", state: "answered", text: "", base_revision: 0, at: "",
      blocks: [{ kind: "receipt", id: "r1", summary: "Your correction: read_length is 150.", revision: 5,
        by: "person", about }] }],
  }) as unknown as AuthoringSession;

  it("links a step it changed", () => {
    const onAbout = vi.fn();
    chat(announced({ node: "star_align", subject: null }), { onAbout });
    fireEvent.click(screen.getByRole("button", { name: "show STAR_ALIGN" }));
    expect(onAbout).toHaveBeenCalledWith({ node: "star_align", subject: null });
  });

  it("links a line of what was understood it changed", () => {
    const onAbout = vi.fn();
    chat(announced({ node: null, subject: "read_length" }), { onAbout });
    fireEvent.click(screen.getByRole("button", { name: "show read_length" }));
    expect(onAbout).toHaveBeenCalledWith({ node: null, subject: "read_length" });
  });
});
