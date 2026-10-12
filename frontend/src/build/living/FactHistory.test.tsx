import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FactHistory } from "./FactHistory";
import { get } from "../../api/client";
vi.mock("../../api/client", () => ({ get: vi.fn() }));
it("loads ordered selections and unused evidence without an undo control", async () => {
  vi.mocked(get).mockResolvedValue({ subject: "paired", entries: [
    { seq: 1, value: false, origin: "person_said", selected: true, current: true,
      actor_kind: "person", who: "ana", action: "select", revision_id: "r1", at: "2026-10-11T10:00:00Z" },
    { seq: 2, value: true, origin: "measured", selected: false, current: false,
      action: "observed", observation_id: "o2", at: "2026-10-11T10:01:00Z" },
  ] });
  render(<FactHistory sessionId="s1" subject="paired" revision={2} />);
  expect(get).not.toHaveBeenCalled();
  const details = screen.getByText("History of paired").closest("details")!;
  details.open = true; fireEvent(details, new Event("toggle"));
  expect(await screen.findByText(/no · you said · current answer/)).toBeInTheDocument();
  expect(screen.getByText(/yes · measured · unused observation/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /undo/i })).toBeNull();
  expect(get).toHaveBeenCalledWith("/pipeline/authoring/s1/facts/paired/history");
});

function selection(value: boolean, current = true) {
  return { seq: 1, value, origin: "person_said", selected: true, current,
    actor_kind: "person", who: "ana", action: "select", revision_id: "r1", at: "2026-10-11T10:00:00Z" };
}

it("refreshes an expanded history when a correction changes the revision", async () => {
  vi.mocked(get).mockReset().mockResolvedValue({ entries: [selection(false)] });
  const { rerender } = render(<FactHistory sessionId="s1" subject="paired" revision={1} />);
  const details = screen.getByText("History of paired").closest("details")!;
  details.open = true; fireEvent(details, new Event("toggle"));
  expect(await screen.findByText(/no · you said · current answer/)).toBeInTheDocument();
  vi.mocked(get).mockResolvedValue({ entries: [selection(false, false), { ...selection(true), revision_id: "r2" }] });
  rerender(<FactHistory sessionId="s1" subject="paired" revision={2} />);
  expect(await screen.findByText(/yes · you said · current answer/)).toBeInTheDocument();
  expect(screen.getByText(/no · you said · previous answer/)).toBeInTheDocument();
  expect(details.open).toBe(true);
});

it("discards a slower response for the previous revision", async () => {
  let previous!: (value: unknown) => void;
  const pending = new Promise(resolve => { previous = resolve; });
  vi.mocked(get).mockReset().mockReturnValue(pending);
  const { rerender } = render(<FactHistory sessionId="s1" subject="paired" revision={1} />);
  const details = screen.getByText("History of paired").closest("details")!;
  details.open = true; fireEvent(details, new Event("toggle"));
  vi.mocked(get).mockResolvedValue({ entries: [selection(true)] });
  rerender(<FactHistory sessionId="s1" subject="paired" revision={2} />);
  expect(await screen.findByText(/yes · you said · current answer/)).toBeInTheDocument();
  await act(async () => previous({ entries: [selection(false)] }));
  expect(screen.getByText(/yes · you said · current answer/)).toBeInTheDocument();
  expect(screen.queryByText(/no · you said · current answer/)).toBeNull();
});

it("loads the new subject when an expanded history changes identity at the same revision", async () => {
  vi.mocked(get).mockReset().mockResolvedValue({ entries: [selection(false)] });
  const { rerender } = render(<FactHistory sessionId="s1" subject="paired" revision={1} />);
  const details = screen.getByText("History of paired").closest("details")!;
  details.open = true; fireEvent(details, new Event("toggle"));
  expect(await screen.findByText(/no · you said · current answer/)).toBeInTheDocument();
  vi.mocked(get).mockResolvedValue({ entries: [selection(true)] });
  rerender(<FactHistory sessionId="s2" subject="stranded" revision={1} />);
  expect(await screen.findByText(/yes · you said · current answer/)).toBeInTheDocument();
  expect(get).toHaveBeenLastCalledWith("/pipeline/authoring/s2/facts/stranded/history");
});
