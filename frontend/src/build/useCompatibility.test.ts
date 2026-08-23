import { describe, expect, it } from "vitest";

import { accepts } from "./useCompatibility";

const STAR = "nf-core/star/align@1.11.0";
const SORT = "nf-core/samtools/sort@1.21.0";
const COUNTS = "nf-core/subread/featurecounts@2.0.6";

/** Real shape, real values — taken from `GET /api/pipeline/compatibility` on the shipped
 * registry rather than invented, so a change to the encoding fails here too. */
const INDEX = {
  emits: {
    [`${STAR}#bam`]: "alignment.bam",
    [`${SORT}#bam`]: "alignment.bam[coordinate_sorted]",
  },
  requires: {
    [`${COUNTS}#bam`]: ["alignment.bam[coordinate_sorted]"],
    [`${SORT}#bam`]: ["alignment.bam"],
    [`${STAR}#reads`]: ["fastq.reads[trimmed]", "fastq.reads"],
  },
  satisfies: {
    "alignment.bam": ["alignment.bam"],
    "alignment.bam[coordinate_sorted]": ["alignment.bam", "alignment.bam[coordinate_sorted]"],
    "fastq.reads": ["fastq.reads"],
  },
};

describe("colouring a wire during a drag", () => {
  it("refuses an unsorted bam into featureCounts", () => {
    expect(accepts(INDEX, `${STAR}#bam`, `${COUNTS}#bam`)).toBe("no");
  });

  it("accepts a sorted one", () => {
    expect(accepts(INDEX, `${SORT}#bam`, `${COUNTS}#bam`)).toBe("yes");
  });

  it("accepts an unsorted bam into the sorter", () => {
    expect(accepts(INDEX, `${STAR}#bam`, `${SORT}#bam`)).toBe("yes");
  });

  it("says no rather than throwing on a port it has never heard of", () => {
    // A draft can name a contract the registry no longer has. The canvas must grey the port,
    // not crash mid-drag.
    expect(accepts(INDEX, "nf-core/nothing@1.0.0#x", `${SORT}#bam`)).toBe("no");
    expect(accepts(INDEX, `${SORT}#bam`, "nf-core/nothing@1.0.0#x")).toBe("no");
  });

  it("marks a match on a non-first alternative as unconventional", () => {
    // `star/align.reads` conventionally wants trimmed reads and structurally accepts any.
    // Untrimmed is legal and amber, which is MD0507 seen before the server says it.
    expect(accepts(INDEX, "any#reads", `${STAR}#reads`)).toBe("no"); // unknown source
    const withRaw = { ...INDEX, emits: { ...INDEX.emits, "trim#reads": "fastq.reads" } };
    expect(accepts(withRaw, "trim#reads", `${STAR}#reads`)).toBe("conventional-no");
  });

  it("is a lookup, never a parse", () => {
    // The guarantee this file exists for. If `accepts` ever takes a signature APART — splits
    // it, slices the state list out of the brackets, compares type ids — the rule that decides
    // whether a BAM can feed featureCounts lives in two places, and the second one is invisible
    // to the agreement test that holds the index to the verb.
    //
    // Indexing a record IS the lookup, so `index.emits[key]` is the point rather than a smell.
    // What is checked is string surgery on the signatures themselves.
    const source = accepts.toString();
    for (const smell of [/\.split\s*\(/, /\.slice\s*\(/, /\.substring\s*\(/,
                         /\.replace\s*\(/, /charAt/, /"\["/, /'\['/]) {
      expect(source).not.toMatch(smell);
    }
  });
});
