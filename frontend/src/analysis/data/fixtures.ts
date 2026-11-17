import type { AnalysisData } from "./types";

/** A small analysis, as `readAnalysisData` answers it: two paired samples and one without its mate. */
export function analysis(overrides: Partial<AnalysisData> = {}): AnalysisData {
  return {
    draft_id: "d1",
    folders: ["/data/liver"],
    scan: { state: "done", done: 5, total: 5, error: null, examples: [] },
    samples: [
      { name: "L01", files: ["/data/liver/L01_R1.fq.gz", "/data/liver/L01_R2.fq.gz"], outcome: "measured",
        type_id: "fastq.reads", left_out: false,
        facts: [{ measurement: "read_length", value: 101, coverage: "head", pieces: [] }] },
      { name: "L02", files: ["/data/liver/L02_R1.fq.gz", "/data/liver/L02_R2.fq.gz"], outcome: "measured",
        type_id: "fastq.reads", left_out: false,
        facts: [{ measurement: "read_length", value: 50, coverage: "head", pieces: [] }] },
    ],
    files: 5,
    revision: 1,
    rule: { pattern: null, origin: "rule", confirmed: false, reason: null },
    rule_result: { samples: 2, unfit: 0, examples: [] },
    checks: [{ sample: "L17_R1", kind: "missing_mate", detail: "L17_R1.fq.gz has no mate; L17_2.fq.gz looks like it",
               fixes: [{ kind: "use_file", sample: "L17_R1", file: "L17_2.fq.gz", by: "you", reason: null },
                       { kind: "leave_out", sample: "L17_R1", file: null, by: "you", reason: null }] }],
    fixes: [],
    references: [],
    columns: {},
    summary: {
      tiles: [{ label: "Samples", value: "2", hint: null }, { label: "Kinds of data", value: "1", hint: null },
              { label: "Size on disk", value: "4.2 GB", hint: null }, { label: "Files", value: "5", hint: null }],
      compare_by: [{ measurement: "read_length", label: "Read length", unit: "bp",
                     values: [{ sample: "L01", value: 101 }, { sample: "L02", value: 50 }], median: 75.5 }],
      measured: [{ measurement: "paired", label: "Paired", value: true, origin: "measured" },
                 { measurement: "read_length", label: "Read length", value: null, origin: "varies" }],
    },
    ...overrides,
  } as AnalysisData;
}
