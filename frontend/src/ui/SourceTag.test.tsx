import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { SourceTag, type Source } from "./SourceTag";

it("source tag renders each source with its label", () => {
  const words: Record<Source, string> = {
    measured: "MEASURED", rule: "RULE", default: "DEFAULT", you: "YOU", ai: "AI", not_set: "NOT SET",
  };
  for (const [source, word] of Object.entries(words) as [Source, string][]) {
    const { unmount } = render(<SourceTag source={source} />);
    expect(screen.getByText(word).dataset.source).toBe(source);
    unmount();
  }
});
