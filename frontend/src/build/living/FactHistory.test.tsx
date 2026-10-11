import { fireEvent, render, screen } from "@testing-library/react";
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
