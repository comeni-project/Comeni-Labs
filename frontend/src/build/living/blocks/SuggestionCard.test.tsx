import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { byEdit, SuggestionCard } from "./SuggestionCard";

/** Part I.0: the model's suggestion waits for one click, and says whose reading it is. */

const OFFERED = { id: "s1", says: "read length is 50", heard: false, quote: null,
                  kind: "measurement", subject: "read_length" };

describe("a suggestion", () => {
  it("says what it would change and that it is the model's reading", () => {
    render(<SuggestionCard suggestion={OFFERED} busy={false} onApply={vi.fn()}
                           onDismiss={vi.fn()} />);
    expect(screen.getByText("read length is 50")).toBeInTheDocument();
    expect(screen.getByText("suggested by AI")).toBeInTheDocument();
  });

  it("names the words it was heard in when it quoted the person", () => {
    render(<SuggestionCard suggestion={{ ...OFFERED, heard: true, quote: "50 bp" }} busy={false}
                           onApply={vi.fn()} onDismiss={vi.fn()} />);
    expect(screen.getByText('you said "50 bp"')).toBeInTheDocument();
  });

  it("applies or dismisses on one click", () => {
    const onApply = vi.fn();
    const onDismiss = vi.fn();
    render(<SuggestionCard suggestion={OFFERED} busy={false} onApply={onApply}
                           onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onApply).toHaveBeenCalledWith("s1");
    expect(onDismiss).toHaveBeenCalledWith("s1");
  });

  it("asks Yes or No when the value is against what the sample measured (issue 345)", () => {
    const onApply = vi.fn();
    const onDismiss = vi.fn();
    const asked = { ...OFFERED, heard: true, quote: "read length is 50", measured: 101,
                    says: "Are you sure the read length is 50? Your sample measured 101." };
    render(<SuggestionCard suggestion={asked} busy={false} onApply={onApply}
                           onDismiss={onDismiss} />);
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    fireEvent.click(screen.getByRole("button", { name: "No" }));
    expect(onApply).toHaveBeenCalledWith("s1");
    expect(onDismiss).toHaveBeenCalledWith("s1");
  });
});

/** One builder (#395): a hand edit read by the engine waits as one card per edit, said as the
 *  engine's reading of what the person did — not as the model's suggestion. */
describe("a reading of a hand edit", () => {
  const WANT = { id: "r1", says: "So you also want qc.report, made by FASTQC — right?", heard: false,
                 quote: null, kind: "want", subject: "qc.report", edit: "e1" };
  const PIN = { ...WANT, id: "r2", says: "…made by FASTQC.", kind: "pin" };

  it("is one card per edit, worded by its first reading", () => {
    expect(byEdit([WANT, PIN, OFFERED])).toEqual({ readings: [WANT], suggestions: [OFFERED] });
  });

  it("says it was read from your edit, and asks yes or no", () => {
    const onApply = vi.fn();
    const onDismiss = vi.fn();
    render(<SuggestionCard suggestion={WANT} busy={false} onApply={onApply} onDismiss={onDismiss} />);
    expect(screen.getByText("from your edit")).toBeInTheDocument();
    expect(screen.queryByText("suggested by AI")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onApply).toHaveBeenCalledWith("r1");
    fireEvent.click(screen.getByRole("button", { name: "No, undo" }));
    expect(onDismiss).toHaveBeenCalledWith("r1");
  });
});
