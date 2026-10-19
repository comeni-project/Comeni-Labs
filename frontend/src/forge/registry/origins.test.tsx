import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { OriginKey } from "./ReviewDiff";
import { Provenance } from "./Validation";

/** A model's answer awaiting review is amber, as it is on Home; what a rule or the source
 *  settled spends no colour (`docs/explanation/visual-identity.md`). */

function swatchOf(word: string): HTMLElement {
  const row = screen.getByText(word, { exact: false }).closest("span")!;
  return row.querySelector("[aria-hidden]") as HTMLElement;
}

it("keys a model's proposal amber and what was read from the source in no colour", () => {
  render(<OriginKey />);
  const model = swatchOf("proposed by the model");
  expect(model.style.background).toBe("var(--measured)");
  expect(model.nextElementSibling?.getAttribute("style")).toContain("var(--measured-ink)");
  const source = swatchOf("read from the source");
  expect(source.style.background).toBe("var(--rail)");
  const forge = swatchOf("derived by the forge");
  expect(forge.style.background).not.toMatch(/--(?:done|now)\b/);
});

it("draws the provenance bar with the model amber and the source neutral", () => {
  const { container } = render(<Provenance origins={{ derived: 2, model: 1, human: 1, open: 1 }} />);
  const tones = Array.from(container.querySelectorAll<HTMLElement>(".grow-x")).map((bar) => bar.style.background);
  expect(tones).toHaveLength(4);
  expect(tones).toEqual(["var(--rail)", "var(--measured)", "var(--ink-2)", "var(--needs-you)"]);
});
