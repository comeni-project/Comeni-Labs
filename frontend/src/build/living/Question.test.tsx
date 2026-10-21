import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession, Step } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { framed } from "./frame";
import { LivingSurface } from "./LivingSurface";

/** The *Question* board: opening a step asks each of its open values as a card. */

const OPEN = { name: "index_format", value: null, via: "ext", tier: 4, because: "", axis_reason: "",
               reason: "No rule settles it, and nothing measured it.", premise: [],
               domain: { kind: "enum", values: ["bai", "csi"] } };
const FREE = { ...OPEN, name: "seq_platform", reason: "Your description does not say.", domain: null };

function opened(settings: object[], graph = FAKE_SESSION.graph, overrides = {}) {
  const steps = { ...FAKE_STEPS, star_align: { ...FAKE_STEPS.star_align,
    settings: [...FAKE_STEPS.star_align.settings, ...settings] } as Step };
  const props = {
    session: framed(FAKE_SESSION, steps, FAKE_CHANNELS),
    graph: graph as AuthoringSession["graph"],
    state: { ...initialAuthoring, snapshot: FAKE_SESSION, selected: "star_align" },
    preview: { revision: FAKE_SESSION.revision, state: "ready" as const, text: "version: 6\n", findings: [] },
    busy: () => false,
    onAccept: vi.fn(), onReject: vi.fn(), onPreviewOption: vi.fn(), onSelect: vi.fn(), onCompose: vi.fn(),
    onSay: vi.fn(), onRetry: vi.fn(), onAddStep: vi.fn(), onDismiss: vi.fn(), onSetParam: vi.fn(),
    onApplyChange: vi.fn(), onEdit: vi.fn(),
    ...overrides,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LivingSurface {...props} />
    </QueryClientProvider>,
  );
  return props;
}

const panel = () => screen.getByRole("region", { name: "build panel" });

describe("an opened step", () => {
  it("names the step and its tool under it", () => {
    opened([]);
    const step = within(panel()).getByRole("region", { name: "step STAR_ALIGN" });
    expect(within(step).getByRole("heading", { level: 2 })).toHaveTextContent("STAR_ALIGN");
    expect(step).toHaveTextContent(FAKE_STEPS.star_align.contract_id);
  });

  it("asks each open value as a question: the setting, needs you, its path and why it is open", () => {
    opened([OPEN]);
    const card = screen.getByRole("region", { name: "a value for index_format" });
    expect(within(card).getByRole("heading")).toHaveTextContent("What should index_format be?");
    expect(card).toHaveTextContent("needs you");
    expect(card).toHaveTextContent("settings.index_format");
    expect(card).toHaveTextContent("No rule settles it, and nothing measured it.");
  });

  it("offers the declared values as the only answers, and says so", () => {
    opened([OPEN]);
    const card = screen.getByRole("region", { name: "a value for index_format" });
    expect(within(card).getAllByRole("radio").map((r) => (r as HTMLInputElement).value)).toEqual(["bai", "csi"]);
    expect(card).toHaveTextContent("these two are all the answers there are");
  });

  it("asks for a typed value where the contract declares none", () => {
    opened([FREE]);
    const card = screen.getByRole("region", { name: "a value for seq_platform" });
    expect(within(card).queryAllByRole("radio")).toHaveLength(0);
    expect(within(card).getByRole("textbox", { name: "seq_platform" })).toBeInTheDocument();
  });

  it("saves the answer with the person's reason, through the setting write", () => {
    const props = opened([OPEN]);
    const card = screen.getByRole("region", { name: "a value for index_format" });
    fireEvent.click(within(card).getByRole("radio", { name: /csi/ }));
    fireEvent.change(within(card).getByRole("textbox", { name: "Your reason" }),
                     { target: { value: "our viewer reads csi" } });
    fireEvent.click(within(card).getByRole("button", { name: "Save answer" }));
    expect(props.onSetParam).toHaveBeenCalledWith("star_align", "index_format", "csi", "our viewer reads csi");
  });

  it("cannot save before an answer is chosen", () => {
    opened([OPEN]);
    const card = screen.getByRole("region", { name: "a value for index_format" });
    expect(within(card).getByRole("button", { name: "Save answer" })).toBeDisabled();
  });

  it("closes the step with Cancel, and with the ×", () => {
    const props = opened([OPEN]);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(props.onSelect).toHaveBeenLastCalledWith(null);
    fireEvent.click(within(panel()).getByRole("button", { name: "Close the step" }));
    expect(props.onSelect).toHaveBeenCalledTimes(2);
  });

  it("asks nothing for a step with no open values, and keeps its tools under Change this step", () => {
    opened([]);
    expect(screen.queryByRole("region", { name: /^a value for/ })).toBeNull();
    const tools = within(panel()).getByRole("region", { name: "Change this step" });
    expect(tools).toBeInTheDocument();
  });

  it("asks nothing once the person has typed the value into the draft", () => {
    const graph = { ...FAKE_SESSION.graph, nodes: FAKE_SESSION.graph.nodes.map((n) => n.id === "star_align"
      ? { ...n, params: [{ name: "index_format", value: "bai", why: "" }] } : n) };
    opened([OPEN], graph);
    expect(screen.queryByRole("region", { name: "a value for index_format" })).toBeNull();
  });
});
