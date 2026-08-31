import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** **The screen now edits a GRAPH**, so the fixture needs steps rather than only a layout.
 *
 * Plan 3C's canvas took a resolved pipeline and drew it; a builder takes a graph you drew and
 * asks the server to lay it out. An empty fixture used to be enough because nothing depended on
 * there being a graph — now an empty one legitimately renders a blank canvas, which is where a
 * builder starts and is not what these tests are about.
 */
const PIPELINE = {
  steps: [
    { id: "star_align", contract_id: "nf-core/star/align@1.11.0", process: "STAR_ALIGN",
      tier: 4, reason: "", ports: [], settings: [] },
    { id: "samtools_sort", contract_id: "nf-core/samtools/sort@1.21.0", process: "SAMTOOLS_SORT",
      tier: 4, reason: "", ports: [], settings: [] },
  ],
  layout: {
    nodes: [
      { id: "star_align", rank: 0, order: 0, x: 0, y: 0, width: 180, height: 64, tier: 4 },
      { id: "samtools_sort", rank: 1, order: 0, x: 0, y: 128, width: 180, height: 64, tier: 4 },
    ],
    wires: [
      // `points` must be a real elbow: `Wires.d()` reads points[0] and the last one, so an
      // empty list throws inside the render rather than drawing nothing.
      { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam",
        type_id: "alignment.bam",
        points: [{ x: 90, y: 64 }, { x: 90, y: 96 }, { x: 90, y: 128 }],
        label_at: { x: 90, y: 96 } },
    ],
    width: 401,
    height: 462,
  },
  provenance: { "2": 4, "3": 1 },
  settled_share: 0.8,
  needs_review: [],
};

/** A value nobody has answered: tier 4, no value, and the reason the resolver gives. */
const open = (name: string) => ({
  name, value: null, via: "ext", tier: 4, reason: "no rule matched",
  axis_reason: "", premise: [], because: "",
});

const MODULES = [
  { contract_id: "nf-core/star/align@1.11.0", tool: "star/align", process: "STAR_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "x" },
];

const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 2, name: "Convention", group: "Standard practice", what: "", colour: "pea-soft" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "undecided" },
];

function at(body: unknown = PIPELINE) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        // **One stub, two shapes.** `/pipeline/modules` answers a list and `/pipeline/example`
        // an object; a stub returning the same body for every URL made the picker iterate a
        // pipeline and crash the whole tree, which surfaced as *no rail* rather than as
        // anything about modules.
        json: async () => (String(url).includes("/tiers")
            ? TIERS
            : String(url).includes("/modules")
              ? MODULES
              : body),
      }),
    ),
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/build"] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the builder shell", () => {
  it("is TWO columns — the canvas and the rail", async () => {
    // **Three became two**, and it was the left column that went. `impl-settled`: *the left
    // steps list is deleted on purpose. It duplicated the canvas.* Its other tab — the module
    // palette — is the browse overlay now, which is a better answer to *what could I add* and
    // does not charge a permanent column for a monthly question.
    at();
    await waitFor(() => expect(screen.getByTestId("builder")).toBeTruthy());
    expect(screen.queryByTestId("modules")).toBeNull();
    expect(screen.getByTestId("canvas")).toBeTruthy();
    expect(screen.getByTestId("rail")).toBeTruthy();
  });

  it("resizes the rail only within the range the design gives it", async () => {
    // `dashboard.md` §4 — 280–560 for the rail. The numbers are the design's, and a panel
    // draggable to 40px is a panel draggable into uselessness.
    //
    // **The left half of this test went with the left column.** It checked 190–430 on a panel
    // that no longer exists; the rule it was protecting is unchanged and is asserted here on
    // the panel that remains.
    at();
    const rail = await screen.findByTestId("rail");
    fireEvent.pointerDown(screen.getByTestId("resize-right"), { clientX: 900 });
    fireEvent.pointerMove(window, { clientX: 2000 });
    expect(parseInt(rail.style.width, 10)).toBeGreaterThanOrEqual(280);
    fireEvent.pointerMove(window, { clientX: 0 });
    expect(parseInt(rail.style.width, 10)).toBeLessThanOrEqual(560);
    fireEvent.pointerUp(window);
  });

  it("collapses to a rail that still says what is blocking the run", async () => {
    // **The rule this test exists for** — `dashboard.md` §4: the collapsed right rail keeps its
    // undecided count on the stub, because hiding the panel must never hide what is blocking
    // your run.
    //
    // **What the number MEANS changed in phase 6, and the rule did not.** It was
    // `needs_review.length` — a list of STEP ids — under a label reading `n values need you`.
    // On the spine both are 5, so the mislabel was invisible; what gave it away is that
    // answering a value never moved it, because a step with one open value keeps its id
    // whatever you do to the value. It counts tier-4 SETTINGS now, so the fixture carries two.
    at({
      ...PIPELINE,
      steps: [
        { ...PIPELINE.steps[0], settings: [open("seq_platform"), open("read_group")] },
        PIPELINE.steps[1],
      ],
      needs_review: ["star_align", "samtools_sort"],
    });
    const collapse = await screen.findByTestId("collapse-right");
    fireEvent.click(collapse);
    const rail = screen.getByTestId("rail");
    expect(rail.dataset.collapsed).toBe("true");
    expect(rail.textContent).toContain("2");
  });

  it("zooms toward the cursor, clamped to the design's range", async () => {
    at();
    const canvas = await screen.findByTestId("canvas");
    for (let i = 0; i < 60; i++) {
      fireEvent.wheel(canvas, { deltaY: -100, clientX: 10, clientY: 10 });
    }
    expect(Number(screen.getByTestId("zoom").dataset.k)).toBeLessThanOrEqual(2.2);
    for (let i = 0; i < 200; i++) {
      fireEvent.wheel(canvas, { deltaY: 100, clientX: 10, clientY: 10 });
    }
    expect(Number(screen.getByTestId("zoom").dataset.k)).toBeGreaterThanOrEqual(0.3);
  });

  it("resets to where it started", async () => {
    at();
    const canvas = await screen.findByTestId("canvas");
    fireEvent.wheel(canvas, { deltaY: -400, clientX: 10, clientY: 10 });
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(Number(screen.getByTestId("zoom").dataset.k)).toBe(1);
  });

  it("gives the canvas a track to grow into", async () => {
    // **A weak guard for a defect no test here can see.** The canvas sits in a flex column under
    // the provenance bar and everything inside it is absolutely positioned, so without `flex-1`
    // it sizes to its content — nothing — and the graph renders into a zero-height box. The bar
    // showed, the nodes did not, and every test in this file still passed: **jsdom has no layout
    // engine**, so height is not a thing it can be wrong about.
    //
    // Asserting a class name is testing a CSS string and it is worth exactly what that is worth.
    // It is here because it names the failure, so a refactor that drops the class has something
    // to trip over. The mechanism that actually caught this was a person opening the page, which
    // is what checkpoint 2 is for.
    at();
    const canvas = await screen.findByTestId("canvas");
    expect(canvas.className).toContain("flex-1");
    expect(canvas.className).toContain("min-h-0");
  });

  it("draws no nodes, because phase 3 has none to draw", async () => {
    // Named rather than left implicit: an empty canvas at this checkpoint is the deliverable,
    // not a bug, and the next phase is what fills it.
    at();
    await screen.findByTestId("canvas");
    expect(screen.queryAllByTestId("node")).toHaveLength(0);
  });
});

describe("interacting without the server in the way", () => {
  it("right-click opens a menu with delete on it", async () => {
    at();
    const node = (await screen.findAllByTestId("node"))[0];
    fireEvent.contextMenu(node);
    expect(screen.getByTestId("node-menu")).toBeInTheDocument();
    expect(screen.getByTestId("menu-delete")).toBeInTheDocument();
    expect(screen.getByTestId("menu-settings")).toBeInTheDocument();
  });

  it("clicking anywhere dismisses the menu", async () => {
    at();
    fireEvent.contextMenu((await screen.findAllByTestId("node"))[0]);
    fireEvent.click(screen.getByTestId("menu-catcher"));
    expect(screen.queryByTestId("node-menu")).toBeNull();
  });

  it("deleting from the menu removes the step", async () => {
    at();
    const before = (await screen.findAllByTestId("node")).length;
    fireEvent.contextMenu((await screen.findAllByTestId("node"))[0]);
    fireEvent.click(screen.getByTestId("menu-delete"));
    await waitFor(() =>
      expect(screen.getAllByTestId("node").length).toBe(before - 1),
    );
  });

  it("Delete removes the selected step", async () => {
    at();
    const nodes = await screen.findAllByTestId("node");
    fireEvent.click(nodes[0]);
    fireEvent.keyDown(window, { key: "Delete" });
    await waitFor(() => expect(screen.getAllByTestId("node").length).toBe(nodes.length - 1));
  });

  it("Delete does nothing while a field has focus", async () => {
    // Or typing a value into the settings card would delete the step you are configuring.
    at();
    const nodes = await screen.findAllByTestId("node");
    fireEvent.click(nodes[0]);
    const field = document.createElement("input");
    document.body.appendChild(field);
    field.focus();
    fireEvent.keyDown(field, { key: "Delete" });
    expect(screen.getAllByTestId("node").length).toBe(nodes.length);
    field.remove();
  });

  it("does not let a drag select the text it passes over", async () => {
    // A pointer drag over labels is a selection gesture to the browser: every label highlights
    // blue as the box moves, and the highlight survives the drop.
    at();
    await screen.findAllByTestId("node");
    expect(screen.getByTestId("canvas").className).toContain("select-none");
  });
});

describe("selection", () => {
  it("clicking empty canvas clears the selection", async () => {
    // A selection you cannot clear means the rail keeps showing a step you have stopped caring
    // about — and Delete stays armed on it.
    at();
    const nodes = await screen.findAllByTestId("node");
    fireEvent.click(nodes[0]);
    fireEvent.click(screen.getByTestId("canvas"));
    // Nothing is selected, so Delete must now do nothing.
    fireEvent.keyDown(window, { key: "Delete" });
    expect(screen.getAllByTestId("node").length).toBe(nodes.length);
  });

  it("clicking a node does not clear it", async () => {
    at();
    const nodes = await screen.findAllByTestId("node");
    fireEvent.click(nodes[0]);
    fireEvent.keyDown(window, { key: "Delete" });
    await waitFor(() => expect(screen.getAllByTestId("node").length).toBe(nodes.length - 1));
  });
});

describe("a value you type", () => {
  /** **The card is fed by the SERVER's echo and written to LOCAL state**, and those are two
   * stores. `drawn` is a query keyed on the debounced graph and carries
   * `placeholderData: (previous) => previous`, so what the field displays does not advance
   * between keystrokes — and every `onChange` therefore receives `"" + newChar`. Typing
   * `ILLUMINA` left `A`.
   *
   * **This test types the way a person does.** `Settings.test.tsx` fires ONE `change` carrying
   * the whole value, which never reads the displayed value and so passes on the broken code —
   * a green tick over an open hole, which is the W2 journal's own lesson about a guard that
   * proves nothing. `userEvent.type` sends one key at a time and reads the DOM between them.
   */
  it("accumulates instead of keeping only the last character", async () => {
    const user = userEvent.setup();
    at({
      ...PIPELINE,
      steps: [
        { ...PIPELINE.steps[0],
          settings: [{ name: "seq_platform", value: null, tier: 4, why: "", domain: null,
                       route: "ext", reason: "", axis_reason: "", because: "",
                       premise: [] }] },
        PIPELINE.steps[1],
      ],
    });

    // **By its label, not its testid.** `⋯` is on every node now — the artboard
    // puts it in each header — so the testid names several buttons and the label
    // names one. It is also what a person would click by.
    fireEvent.click(await screen.findByLabelText("settings for STAR_ALIGN"));
    const field = await screen.findByTestId("setting-field");

    await user.type(field, "ILLUMINA");

    expect((field as HTMLInputElement).value).toBe("ILLUMINA");
  });

  it("stops counting a value against you once you have answered it", async () => {
    // **The count moved for the first time in phase 6.** It was `needs_review.length` — a list
    // of STEP ids — under the label `n values need you`, so answering a value never changed it:
    // a step with one open value keeps its id whatever you do to the value. On the spine both
    // numbers are 5, which is why nothing on screen looked wrong.
    //
    // **The server is deliberately not part of this.** The mocked `draw` echoes the same
    // tier-4 setting back on every keystroke, so the only thing that can move this number is
    // the draft graph — which is the one place that knows a value is a PERSON's rather than
    // the resolver's tier-4 exit writing one and saying *selected the first of 1 candidates
    // without judgement*.
    const user = userEvent.setup();
    at({
      ...PIPELINE,
      steps: [
        { ...PIPELINE.steps[0], settings: [open("seq_platform"), open("read_group")] },
        PIPELINE.steps[1],
      ],
    });

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("2 values need you"),
    );

    fireEvent.click(await screen.findByLabelText("settings for STAR_ALIGN"));
    await user.type((await screen.findAllByTestId("setting-field"))[0], "ILLUMINA");

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("1 value needs you"),
    );

    // **The node says the same thing**, because invariant 6's four places have to agree. It
    // counted `tier === 4` and so read `2 need you` beside a card calling one of them *yours*.
    expect(screen.getAllByTestId("node")[0].textContent).toContain("1 need you");
  });
});
