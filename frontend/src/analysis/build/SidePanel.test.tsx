import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { SidePanel } from "./SidePanel";

function Harness() {
  const [tab, setTab] = useState<"step" | "assistant">("assistant");
  const [draft, setDraft] = useState("");
  return (
    <SidePanel tab={tab} onTab={setTab}
               step={<p>the step</p>}
               assistant={<textarea aria-label="Ask" value={draft} onChange={(e) => setDraft(e.target.value)} />} />
  );
}

describe("SidePanel", () => {
  it("step tab and assistant tab switch without losing the chat draft", () => {
    render(<Harness />);
    fireEvent.change(screen.getByRole("textbox", { name: "Ask" }), { target: { value: "why STAR?" } });
    fireEvent.click(screen.getByRole("tab", { name: "Step" }));
    expect(screen.getByText("the step")).toBeTruthy();
    expect(screen.getByRole("tabpanel", { name: "Step" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Assistant" }));
    expect((screen.getByRole("textbox", { name: "Ask" }) as HTMLTextAreaElement).value).toBe("why STAR?");
  });
});
