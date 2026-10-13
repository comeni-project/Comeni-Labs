import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SuggestionCard } from "./SuggestionCard";

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
});
