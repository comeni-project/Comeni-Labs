import type { AuthoringSession, Step } from "../../api/types";

/** A static session carrying **every state the agent's thread can be in** — the page to look at
 * without a server, and what the browser check compares.
 *
 * The RNA-seq spine four steps in: a person's request, an answered turn with its working trail,
 * a question asked, a refusal, and a turn still working. Shaped by the generated types, so a
 * server change this page cannot draw fails `tsc` here as well as in the live path.
 */

const at = (minute: number) => `2026-09-13T10:${String(minute).padStart(2, "0")}:00+00:00`;

const INDEX = "nf-core/star/genomegenerate@2.7.11b";
const TRIM = "nf-core/trimgalore@2.3.0";
const ALIGN = "nf-core/star/align@2.7.11b";
const SORT = "nf-core/samtools/sort@1.24";

const tool = (seq: number, n: number, name: string, label: string, summary = "", ok = true) =>
  ({ id: `tool-${seq}-${n}`, kind: "tool", name, label, ok, summary });

export const FAKE_SESSION = {
  id: "fake",
  draft_id: "fake-draft",
  name: "rnaseq-counts",
  goal: null,
  facts: [],
  samples: [],
  inputs: [],
  fact_subjects: [],
  decision_revision: 3,
  projection_current: true,
  retired: false,
  usage: { input: 18200, output: 2100, cached: 0, calls: 6, in_flight: true },
  revision: 4,
  row_version: 9,
  model_configured: true,
  steps_total: 4,
  graph: {
    nodes: [
      { id: "star_genomegenerate", contract_id: INDEX, params: [] },
      { id: "trimgalore", contract_id: TRIM, params: [] },
      { id: "star_align", contract_id: ALIGN, params: [] },
      { id: "samtools_sort", contract_id: SORT, params: [] },
    ],
    edges: [
      { from_node: "trimgalore", from_port: "reads", to_node: "star_align", to_port: "reads" },
      { from_node: "star_genomegenerate", from_port: "index", to_node: "star_align", to_port: "index" },
      { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" },
    ],
  },
  placement: {
    star_genomegenerate: { x: 40, y: 40 },
    trimgalore: { x: 40, y: 210 },
    star_align: { x: 264, y: 125 },
    samtools_sort: { x: 488, y: 125 },
  },
  turns: [
    { seq: 0, role: "person", state: "answered", base_revision: 0, at: at(0), blocks: [],
      text: "I have 12 paired RNA-seq samples, a genome and its annotation. I want gene counts." },
    { seq: 1, role: "assistant", state: "answered", base_revision: 0, at: at(1), text: "",
      blocks: [
        tool(1, 0, "read_goal", "Read the goal", "nothing wanted yet"),
        tool(1, 1, "want", "Wanted counts.matrix"),
        tool(1, 2, "have", "Have fastq.reads, genome.fasta, annotation.gtf"),
        tool(1, 3, "tools_for", "Looked at the aligners for fastq.reads", "STAR, HISAT2"),
        tool(1, 4, "choose_tool", "Chose STAR for alignment"),
        tool(1, 5, "resolve", "Built the pipeline", "4 steps"),
        { id: "say-1-6", kind: "message", text: "I've set up a gene-counts pipeline: trim, build a STAR "
          + "index, align, then sort.\n\nI picked STAR over HISAT2 because your reads are 150 bp and "
          + "paired, where STAR's splice-aware alignment is the usual choice. It needs more memory — "
          + "about 32 GB for a human genome. If that's a problem, say so and I'll switch to HISAT2." },
        { id: "ask-1", kind: "ask", question_id: "q-strand", question: "Are the reads stranded?",
          shape: "options", options: ["reverse-stranded", "forward-stranded", "unstranded", "I don't know"],
          unit: "", type_id: null },
      ] },
    { seq: 2, role: "person", state: "answered", base_revision: 3, at: at(8), blocks: [],
      text: "Are the reads stranded? reverse-stranded" },
    { seq: 3, role: "assistant", state: "failed", base_revision: 3, at: at(9), text: "",
      blocks: [{ id: "failed-3", kind: "notice", notice: "refusal", code: "MA0002",
        text: "The AI did not answer in time." }] },
    { seq: 4, role: "person", state: "answered", base_revision: 4, at: at(13), blocks: [],
      text: "and what does the sorter do?" },
    { seq: 5, role: "assistant", state: "pending", base_revision: 4, at: at(13), text: "",
      blocks: [tool(5, 0, "read_step", "Read SAMTOOLS_SORT")] },
  ],
  working: true,
  ai_unreviewed: [{ node: "star_align", what: "chose nf-core/star/align@2.7.11b" }],
} as unknown as AuthoringSession;

const port = (name: string, type_id: string, side: "in" | "out", states: string[] = [], gathers = false) =>
  ({ name, type_id, side, met: true, states, gathers });

/** Ports for the fixture's steps, in the drawn view's shape. */
export const FAKE_STEPS = {
  star_genomegenerate: { id: "star_genomegenerate", process: "STAR_GENOMEGENERATE", contract_id: INDEX,
    tier: 2, runs: "once", reason: "", settings: [],
    ports: [port("fasta", "genome.fasta", "in"), port("gtf", "annotation.gtf", "in"),
      port("index", "genome.index.star", "out")] },
  trimgalore: { id: "trimgalore", process: "TRIMGALORE", contract_id: TRIM, tier: 2, runs: "per_item", reason: "",
    settings: [], ports: [port("reads", "fastq.reads", "in"),
      port("reads", "fastq.reads", "out", ["trimmed"])] },
  star_align: { id: "star_align", process: "STAR_ALIGN", contract_id: ALIGN, tier: 3, runs: "per_item", reason: "",
    settings: [
      { name: "sjdbOverhang", value: "150", via: "ext", tier: 3, reason: "Read length is 151 bp, measured from your files, minus one.",
        because: "", axis_reason: "", optional: false, evidence: "measured", premise: ["read_length = 151"] },
      { name: "outSAMtype", value: "BAM Unsorted", via: "ext", tier: 1, reason: "The next step sorts, so sorting here would be done twice.",
        because: "", axis_reason: "", optional: false, premise: [] },
      { name: "twopassMode", value: "None", via: "ext", tier: 2, reason: "nf-core's default for this module.",
        because: "", axis_reason: "", optional: false, premise: [] },
    ], ports: [port("reads", "fastq.reads", "in", ["trimmed"]),
      port("index", "genome.index.star", "in"), port("bam", "alignment.bam", "out")] },
  samtools_sort: { id: "samtools_sort", process: "SAMTOOLS_SORT", contract_id: SORT, tier: 2, runs: "per_item",
    reason: "", settings: [], ports: [port("bam", "alignment.bam", "in"),
      port("bam", "alignment.bam", "out", ["coordinate_sorted"])] },
} as unknown as Record<string, Step>;

/** A slice of the registry's vocabulary, so the fixture's goal card has something to add. */
export const FAKE_VOCABULARY: Record<string, string[]> = {
  "annotation.gtf": [],
  "counts.matrix": ["gene_level", "normalised", "transcript_level"],
  "fastq.reads": ["deduplicated", "subsampled", "trimmed"],
  "genome.fasta": [],
  "qc.report": ["aggregated"],
};

/** The fixture's entry channels, in the drawn view's shape. `reads` was measured at 12 samples. */
export const FAKE_CHANNELS = [
  { name: "reads", param: "input", type_id: "fastq.reads", grain: "sample", count: 12, states: [],
    ports: ["trimgalore.reads"] },
  { name: "fasta", param: "fasta", type_id: "genome.fasta", grain: "study", count: null, states: [],
    ports: ["star_genomegenerate.fasta"] },
  { name: "gtf", param: "gtf", type_id: "annotation.gtf", grain: "study", count: null, states: [],
    ports: ["star_genomegenerate.gtf"] },
] as unknown as import("../../api/schema").components["schemas"]["ChannelView"][];

/** 1→1, N→N and N→1, the three collection shapes, on one small graph — `LivingCollect`'s content. */
export const COLLECT_SESSION = {
  ...FAKE_SESSION,
  name: "rnaseq-counts",
  steps_total: 4,
  graph: {
    nodes: [
      { id: "star_align", contract_id: ALIGN, params: [] },
      { id: "trimgalore", contract_id: TRIM, params: [] },
      { id: "fastqc", contract_id: "nf-core/fastqc@0.12.1", params: [] },
      { id: "multiqc", contract_id: "nf-core/multiqc@1.35", params: [] },
    ],
    edges: [
      { from_node: "fastqc", from_port: "zip", to_node: "multiqc", to_port: "reports" },
    ],
  },
  placement: {
    star_align: { x: 420, y: 40 },
    trimgalore: { x: 420, y: 250 },
    fastqc: { x: 196, y: 470 },
    multiqc: { x: 420, y: 470 },
  },
  turns: [],
  working: false,
  ai_unreviewed: [],
} as unknown as AuthoringSession;

export const COLLECT_STEPS = {
  star_align: { id: "star_align", process: "STAR_ALIGN", contract_id: ALIGN, tier: 2, runs: "per_item",
    reason: "", settings: [], ports: [port("index", "genome.index.star", "in"),
      port("bam", "alignment.bam", "out")] },
  trimgalore: { id: "trimgalore", process: "TRIMGALORE", contract_id: TRIM, tier: 2, runs: "per_item",
    reason: "", settings: [], ports: [port("reads", "fastq.reads", "in"),
      port("reads", "fastq.reads", "out", ["trimmed"])] },
  fastqc: { id: "fastqc", process: "FASTQC", contract_id: "nf-core/fastqc@0.12.1", tier: 1, runs: "per_item",
    reason: "", settings: [], ports: [port("reads", "fastq.reads", "in"), port("zip", "qc.report", "out")] },
  multiqc: { id: "multiqc", process: "MULTIQC", contract_id: "nf-core/multiqc@1.35", tier: 2, runs: "once",
    reason: "", settings: [], ports: [port("reports", "qc.report", "in", [], true),
      port("report", "qc.report", "out", ["aggregated"])] },
} as unknown as Record<string, Step>;

export const COLLECT_CHANNELS = [
  { name: "reference", param: "index", type_id: "genome.index.star", grain: "study", count: null,
    states: [], ports: ["star_align.index"] },
  { name: "reads", param: "input", type_id: "fastq.reads", grain: "sample", count: 12,
    states: ["paired"], ports: ["trimgalore.reads"] },
] as unknown as import("../../api/schema").components["schemas"]["ChannelView"][];
