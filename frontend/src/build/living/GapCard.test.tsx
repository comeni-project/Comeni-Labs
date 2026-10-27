import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringProposal } from "../../api/types";
import { GapCard } from "./blocks/GapCard";

/** 14.7.3: the engine asks for what the want needs, one gap at a time, and a click answers. */

const gap = (options: [string, string][], asks: string): AuthoringProposal => {
  const block = {
    kind: "question" as const,
    id: "gap-3", asks, why_open: "a step reads it to decide",
    options: options.map(([id, label]) => ({ id, label, recommended: false })),
    exhaustive: true, phrasing: "none" as const,
  };
  return {
    id: "p-gap", kind: "gap", draft_revision: 0, asked_at: "2026-10-27T09:00:00+00:00",
    options: options.map(([id]) => id).sort(), edges: [], block,
    envelope: {
      offer: "gap", subject: "read_length", kind: "measurement", why: "a step reads it",
      options: Object.fromEntries(options), block,
      context: { draft_revision: 0, decision_revision: 0, session_version: 1, registry: "" },
    },
  };
};

const PAIRED = gap(
  [["yes", "Yes"], ["no", "No"], ["not_sure", "Not sure"], ["cant_share", "I can't share it"]],
  "Whether the library was sequenced paired-end?",
);
const LENGTH = gap(
  [["value", "Type it (bp)"], ["not_sure", "Not sure"], ["cant_share", "I can't share it"]],
  "Sequenced read length?",
);

describe("a gap card", () => {
  it("draws a closed question's options as buttons, and a click answers it", () => {
    const onAnswer = vi.fn();
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onAnswer).toHaveBeenCalledWith("yes", undefined);
  });

  it("says why the engine is asking", () => {
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByText("a step reads it to decide")).toBeInTheDocument();
  });

  it("draws a number field for an open value, with not sure and can't share beside it", () => {
    const onAnswer = vi.fn();
    render(<GapCard proposal={LENGTH} busy={false} onAnswer={onAnswer} />);
    fireEvent.change(screen.getByRole("spinbutton", { name: "Type it (bp)" }), {
      target: { value: "150" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Use this" }));
    expect(onAnswer).toHaveBeenCalledWith("value", 150);
    expect(screen.getByRole("button", { name: "Not sure" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "I can't share it" })).toBeInTheDocument();
  });

  it("draws only the ordinary answer as primary — never the one that stops the analysis", () => {
    // Issue 168: *I don't have one* ends the session and was styled like *I have it*.
    const INPUT = gap(
      [["have_it", "I have it"], ["cant_share", "I have it, but can't share it"],
       ["dont_have", "I don't have one"]],
      "This analysis needs genome.fasta. Do you have one?",
    );
    render(<GapCard proposal={INPUT} busy={false} onAnswer={vi.fn()} />);
    const primary = (name: string) =>
      screen.getByRole("button", { name }).className.includes("bg-action");
    expect(primary("I have it")).toBe(true);
    expect(primary("I don't have one")).toBe(false);
    expect(primary("I have it, but can't share it")).toBe(false);
  });

  it("draws a suggested answer with where it came from, and waits for the click", () => {
    // Issues 170 and 171: what the person said is heard, and still confirmed by them.
    const suggested: AuthoringProposal = {
      ...PAIRED,
      block: { ...PAIRED.block, options: (PAIRED.block as { options: { id: string; label: string }[] })
        .options.map((o) => ({ ...o, recommended: o.id === "yes",
          note: o.id === "yes" ? "you mentioned it" : null })) } as AuthoringProposal["block"],
    };
    const onAnswer = vi.fn();
    render(<GapCard proposal={suggested} busy={false} onAnswer={onAnswer} />);
    expect(screen.getByTestId("suggested")).toHaveTextContent("Yes — you mentioned it");
    expect(onAnswer).not.toHaveBeenCalled();
    const primary = (name: string) =>
      screen.getByRole("button", { name }).className.includes("bg-action");
    expect(primary("Yes")).toBe(true);
    expect(primary("No")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onAnswer).toHaveBeenCalledWith("yes", undefined);
  });

  it("pre-fills a suggested value, still sent only by the person", () => {
    const filled = { ...LENGTH, block: { ...LENGTH.block, value: 150 } } as AuthoringProposal;
    const onAnswer = vi.fn();
    render(<GapCard proposal={filled} busy={false} onAnswer={onAnswer} />);
    expect(screen.getByRole("spinbutton", { name: "Type it (bp)" })).toHaveValue(150);
    fireEvent.click(screen.getByRole("button", { name: "Use this" }));
    expect(onAnswer).toHaveBeenCalledWith("value", 150);
  });

  it("says in its one quiet line that a question was worded by the model, and the swap keeps the options in place", () => {
    const phrased = { ...PAIRED, block: { ...PAIRED.block, phrasing: "done",
      asks: "Were both ends of each fragment sequenced?" } } as AuthoringProposal;
    const labels = () => screen.getAllByRole("button").map((b) => b.textContent);
    const { rerender } = render(<GapCard proposal={PAIRED} busy={false} onAnswer={vi.fn()} />);
    const before = labels();
    expect(screen.getByTestId("provenance")).toHaveTextContent(/^asked by the engine$/);
    rerender(<GapCard proposal={phrased} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByText("Were both ends of each fragment sequenced?")).toBeInTheDocument();
    expect(screen.getByTestId("provenance")).toHaveTextContent("asked by the engine · worded by the model");
    expect(labels()).toEqual(before);
  });

  it("cannot send an empty value", () => {
    render(<GapCard proposal={LENGTH} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Use this" })).toBeDisabled();
  });
});

describe("a gap card that takes a sample", () => {
  const LENGTH_WITH_UPLOAD = gap(
    [["value", "Type it (bp)"], ["upload", "Not sure — measure it from a sample"],
     ["cant_share", "I can't share it"]],
    "Sequenced read length?",
  );

  it("draws the upload answer as a file picker, never a button that sends it", () => {
    const onAnswer = vi.fn();
    render(<GapCard proposal={LENGTH_WITH_UPLOAD} busy={false} onAnswer={onAnswer}
      onUpload={vi.fn()} />);
    expect(screen.getByLabelText(/a sample$/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /a sample$/i })).toBeNull();
    expect(screen.getByRole("button", { name: "I can't share it" })).toBeTruthy();
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("without an upload handler, leaves the upload answer out rather than send it", () => {
    render(<GapCard proposal={LENGTH_WITH_UPLOAD} busy={false} onAnswer={vi.fn()} />);
    expect(screen.queryByText(/a sample$/i)).toBeNull();
  });

  it("holds the other answers while the AI reads a sample (issue 135)", () => {
    const reading = { ...LENGTH_WITH_UPLOAD, block: { ...LENGTH_WITH_UPLOAD.block,
      reading: { state: "pending", attempt: 1 } } } as AuthoringProposal;
    render(<GapCard proposal={reading} busy={false} onAnswer={vi.fn()} onUpload={vi.fn()} />);
    expect((screen.getByRole("button", { name: "I can't share it" }) as HTMLButtonElement)
      .disabled).toBe(true);
    expect(screen.getByText(/being read by AI/)).toBeTruthy();
  });

  it("draws the explanation under the question, and none for an offer made before it", () => {
    // Part I.1, and Review Focus 1: an offer stored before explanations carries none.
    const explained = { ...PAIRED, envelope: { ...PAIRED.envelope, explain: {
      name: "Whether the library was sequenced paired-end", what: "Read from both ends.",
      needed: [], reads: null, settles: [], read_by: null } } } as AuthoringProposal;
    const { unmount } = render(<GapCard proposal={explained} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByText("Read from both ends.")).toBeInTheDocument();
    unmount();
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={vi.fn()} />);
    expect(screen.queryByTestId("explain")).toBeNull();
  });
});

describe("no repeated why under a question (Part I.2, issue 306)", () => {
  it("draws no mechanical line when the explanation already says why", () => {
    const explained = { ...PAIRED, envelope: { ...PAIRED.envelope, explain: {
      what: "Whether both ends of each fragment were read.", needed: [{ text: "STAR_ALIGN", detail: null }],
      reads: "steps", read_by: null, files: 1 } } } as unknown as AuthoringProposal;
    render(<GapCard proposal={explained} busy={false} onAnswer={vi.fn()} />);
    expect(screen.queryByText("a step reads it to decide")).toBeNull();
  });

  it("keeps the line when nothing else says why", () => {
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByText("a step reads it to decide")).toBeInTheDocument();
  });
});
