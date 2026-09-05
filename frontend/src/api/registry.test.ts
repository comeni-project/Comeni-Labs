import { describe, expect, it } from "vitest";

import { isMoving, MOVING, type AdaptationState } from "./registry";

/** What polls, and — the half that matters — what stops.
 *
 * **§7 asks for two-second polling on active states and nothing on terminal ones.** The stop is
 * the requirement with teeth: a `published` adaptation is never going to change again, and a
 * page that keeps asking keeps a worker answering *still published* for as long as the tab is
 * open. The interval itself is visible in the hook; whether it stops is a predicate, and this
 * is where the predicate is held.
 */

const EVERY: AdaptationState[] = [
  "scaffolding",
  "queued",
  "generating",
  "validating",
  "review",
  "changes_requested",
  "publishing",
  "published",
  "failed",
  "archived",
];

describe("what a page polls for", () => {
  it("polls exactly the states something is holding or about to hold", () => {
    // **`review` and `changes_requested` are deliberately absent**, and they are the ones a
    // careless reading adds: they are not finished, but they are waiting on a *person*, and
    // refetching them every two seconds asks a question whose answer cannot change without the
    // viewer doing something on this very screen.
    expect(MOVING).toEqual(["scaffolding", "queued", "generating", "validating", "publishing"]);
  });

  it("stops on everything a worker will not move", () => {
    const still = EVERY.filter((state) => !isMoving(state));
    expect(still).toEqual(["review", "changes_requested", "published", "failed", "archived"]);
  });

  it("covers every state the workflow has", () => {
    // A state added to the workflow and not to either list here would fall through to *not
    // moving*, which fails silently: the page simply stops updating and nobody sees an error.
    expect(new Set([...MOVING, ...EVERY.filter((s) => !isMoving(s))])).toEqual(new Set(EVERY));
  });

  it("treats an unknown adaptation as not moving", () => {
    // `undefined` is what a detail query has before its first answer. Polling it would be
    // polling for a row nobody has asked for yet.
    expect(isMoving(undefined)).toBe(false);
  });
});
