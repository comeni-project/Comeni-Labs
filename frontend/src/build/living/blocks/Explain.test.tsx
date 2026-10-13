import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { Explanation } from "../../../api/types";
import { storageName } from "../../../preferences/useBrowserSetting";
import { Explain, uploadHeadline } from "./Explain";

/** Part I.1: what a question is about (curated) and why it is asked (engine). */

const GTF: Explanation = {
  name: "gene annotation (GTF)",
  what: "A table of where each gene and its exons lie on the genome.",
  needed: [{ text: "STAR", detail: "Aligns reads." }, { text: "featureCounts", detail: null }],
  reads: "steps", settles: [], read_by: "ai",
};

describe("what a question is about", () => {
  beforeEach(() => localStorage.clear());

  it("is open by default, with the curated and engine halves marked", () => {
    render(<Explain explanation={GTF} />);
    expect(screen.getByText(/A table of where each gene/)).toBeVisible();
    expect(screen.getByText("curated")).toBeInTheDocument();
    expect(screen.getByText("engine")).toBeInTheDocument();
    expect(screen.getByText("STAR")).toBeInTheDocument();
  });

  it("starts collapsed when the setting says so, and still opens by hand", () => {
    localStorage.setItem(storageName("building.explain"), "collapsed");
    render(<Explain explanation={GTF} />);
    expect(screen.queryByText(/A table of where each gene/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /What is this/ }));
    expect(screen.getByText(/A table of where each gene/)).toBeVisible();
  });

  it("opens when the browser refuses storage (Review Focus 4)", () => {
    const real = Storage.prototype.getItem;
    Storage.prototype.getItem = () => { throw new Error("refused"); };
    try {
      render(<Explain explanation={GTF} />);
      expect(screen.getByText(/A table of where each gene/)).toBeVisible();
    } finally {
      Storage.prototype.getItem = real;
    }
  });

  it("draws only the engine half when the registry says nothing", () => {
    render(<Explain explanation={{ ...GTF, what: null }} />);
    expect(screen.queryByText("curated")).toBeNull();
    expect(screen.getByText("engine")).toBeInTheDocument();
  });

  it("draws nothing when there is nothing to say", () => {
    const { container } = render(
      <Explain explanation={{ ...GTF, what: null, needed: [], reads: null }} />);
    expect(container.textContent).toBe("");
  });

  it("names a rule and its citation for a measurement", () => {
    render(<Explain explanation={{ ...GTF, name: "Sequenced read length", reads: "rule",
      needed: [{ text: "read length determines which aligner is appropriate",
                 detail: "Dobin et al. 2013" }] }} />);
    expect(screen.getByText(/read length determines which aligner/)).toBeInTheDocument();
    expect(screen.getByText(/Dobin et al. 2013/)).toBeInTheDocument();
  });
});

describe("the upload headline", () => {
  it("names what a measured sample settles", () => {
    expect(uploadHeadline({ ...GTF, read_by: "inspector",
      settles: ["whether the library was sequenced paired-end", "sequenced read length"] }))
      .toBe("Have a sample to hand? Upload it and we'll measure the rest: whether the library "
        + "was sequenced paired-end, and sequenced read length. You won't need to answer those "
        + "yourself.");
  });
  it("promises nothing when nothing is left to settle (Review Focus 3)", () => {
    expect(uploadHeadline({ ...GTF, read_by: "inspector", settles: [] }))
      .toBe("Have a sample to hand? Upload it and we'll measure it.");
  });
  it("says the AI reads it, and says nothing about bytes", () => {
    const said = uploadHeadline({ ...GTF, read_by: "ai" })!;
    expect(said).toBe("Have a sample to hand? Upload it and the AI will read it for you. It "
      + "shows you what it found, and nothing is used until you've confirmed it.");
    expect(said).not.toMatch(/KB|MB|bytes/);
  });
  it("is absent when nothing would read a sample", () => {
    expect(uploadHeadline({ ...GTF, read_by: null })).toBeNull();
  });
});
