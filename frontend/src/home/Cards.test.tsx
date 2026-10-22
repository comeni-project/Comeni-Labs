import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";
import { NeedsYouCard, ResultsCard, RunningCard, WentWrongCard } from "./Cards";

type DraftRow = components["schemas"]["DraftRow"];
type RunRow = wiener["schemas"]["RunRow"];

/** Home's cards (#378): each says one thing, and is not drawn when it has nothing to say. */

const draft = (id: string, name: string, open: DraftRow["open_values"], unnamed = 0) =>
  ({ id, name, who: "", updated_at: "2026-10-20T10:00:00Z", steps: 4, makes: [], kept: true,
     changed_since_kept: false, digest: `sha256:${id}`, provenance: null, open_values: open,
     open_not_named: unnamed }) as DraftRow;

const run = (id: string, phase: string, ended: string | null, digest = "sha256:a1") =>
  ({ id, phase, executor: "local", name: "", submitted_by: "someone", submitted_at: "2026-10-20T09:00:00Z",
     ended_at: ended, tasks_done: 3, tasks_seen: 12, pipeline_digest: digest }) as RunRow;

const named = new Map([["sha256:a1", "rnaseq-counts"]]);
const draw = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("Needs you", () => {
  it("names each pipeline's waiting settings, with a way to answer them", () => {
    draw(<NeedsYouCard drafts={[
      draft("a1", "atac-peaks", [{ step: "macs2", setting: "fragment_size" }, { step: "x", setting: "strandedness" }]),
      { ...draft("b2", "16s-profile", [], 2), session: "s2" },
      draft("c3", "settled", []),
    ]} />);
    const card = screen.getByRole("region", { name: "Needs you" });
    const rows = within(card).getAllByRole("listitem");
    expect(rows.length).toBe(2);
    expect(rows[0]).toHaveTextContent("atac-peaks");
    expect(rows[0]).toHaveTextContent("fragment_size, strandedness");
    expect(within(rows[0]).getByRole("link", { name: "Answer" })).toHaveAttribute("href", "/build?draft=a1");
    expect(within(rows[1]).getByRole("link", { name: "Answer" })).toHaveAttribute("href", "/build?session=s2");
    expect(rows[1]).toHaveTextContent("2 values");
    expect(card).toHaveTextContent("No rule could settle these, so nothing runs until someone answers.");
  });

  it("is not drawn when nothing waits", () => {
    draw(<NeedsYouCard drafts={[draft("c3", "settled", [])]} />);
    expect(screen.queryByRole("region", { name: "Needs you" })).toBeNull();
  });
});

describe("Went wrong", () => {
  it("shows the three most recent failed runs, newest first, each openable", () => {
    draw(<WentWrongCard named={named} runs={[
      run("f1", "failed", "2026-10-20T10:01:00Z"), run("ok", "succeeded", "2026-10-20T10:05:00Z"),
      run("f2", "failed", "2026-10-20T10:04:00Z"), run("f3", "failed", "2026-10-20T10:03:00Z"),
      run("f4", "failed", "2026-10-20T10:02:00Z"),
    ]} />);
    const links = within(screen.getByRole("region", { name: "Went wrong" })).getAllByRole("link", { name: /Open the run/ });
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/runs/f2", "/runs/f3", "/runs/f4"]);
  });

  it("is not drawn when nothing failed", () => {
    draw(<WentWrongCard named={named} runs={[run("ok", "succeeded", "2026-10-20T10:05:00Z")]} />);
    expect(screen.queryByRole("region", { name: "Went wrong" })).toBeNull();
  });
});

describe("Results ready", () => {
  it("shows the three most recent succeeded runs by their pipeline's name", () => {
    draw(<ResultsCard named={named} runs={[
      run("s1", "succeeded", "2026-10-19T10:00:00Z"), run("s2", "succeeded", "2026-10-20T10:00:00Z"),
      run("x", "failed", "2026-10-20T11:00:00Z"), run("s3", "succeeded", "2026-10-18T10:00:00Z"),
      run("s4", "succeeded", "2026-10-17T10:00:00Z"),
    ]} />);
    const links = within(screen.getByRole("list")).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/runs/s2", "/runs/s1", "/runs/s3"]);
    expect(links[0]).toHaveTextContent("rnaseq-counts");
  });

  it("is not drawn before anything has finished", () => {
    draw(<ResultsCard named={named} runs={[run("r", "running", null)]} />);
    expect(screen.queryByRole("region", { name: "Results ready" })).toBeNull();
  });
});

describe("Running now", () => {
  it("names the run by its pipeline and counts its tasks, and never says who started it", () => {
    draw(<RunningCard named={named} runs={[run("r1", "running", null)]} />);
    const card = screen.getByRole("region", { name: "Running now" });
    expect(card).toHaveTextContent("rnaseq-counts");
    expect(card).toHaveTextContent("3 of 12 tasks");
    expect(card).not.toHaveTextContent("someone");
    expect(within(card).getByRole("link")).toHaveAttribute("href", "/runs/r1");
  });

  it("is not drawn when nothing runs", () => {
    draw(<RunningCard named={named} runs={[]} />);
    expect(screen.queryByRole("region", { name: "Running now" })).toBeNull();
  });
});
