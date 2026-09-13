import type { AuthoringSession, Step } from "../../api/types";

/** A static session carrying **every block state** — Task 9's checkpoint, before any API.
 *
 * It is the RNA-seq spine four steps in, the aligner accepted, the sorter on offer, plus one of
 * each notice so a single page shows every state the log can be in. It is a fixture for looking
 * at the page, and it is shaped by the generated types, so a server change that this page cannot
 * draw fails `tsc` here as well as in the live path.
 */

const at = (minute: number) => `2026-09-13T10:${String(minute).padStart(2, "0")}:00+00:00`;

const INDEX = "nf-core/star/genomegenerate@1.11.0";
const TRIM = "nf-core/trimgalore@0.6.10";
const ALIGN = "nf-core/star/align@1.11.0";
const SORT = "nf-core/samtools/sort@1.21.0";

export const FAKE_SESSION = {
  id: "fake",
  draft_id: "fake-draft",
  name: "rnaseq-counts",
  mode: "build",
  phase: "building",
  failed_from: null,
  goal: null,
  revision: 4,
  row_version: 9,
  model_configured: true,
  steps_total: 5,
  graph: {
    nodes: [
      { id: "star_genomegenerate", contract_id: INDEX, params: [] },
      { id: "trimgalore", contract_id: TRIM, params: [] },
      { id: "star_align", contract_id: ALIGN, params: [] },
    ],
    edges: [
      { from_node: "trimgalore", from_port: "reads", to_node: "star_align", to_port: "reads" },
      { from_node: "star_genomegenerate", from_port: "index", to_node: "star_align", to_port: "index" },
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
        { kind: "goal_summary", id: "goal-1", goal: { have: [], want: ["counts.matrix"] },
          have: "paired RNA-seq reads, a genome and its annotation",
          do: "trim, align to the genome, sort and count reads per gene",
          get: "a gene-level counts matrix" },
        { kind: "question", id: "question-1-1", asks: "Are the reads stranded?",
          why_open: "featureCounts counts differently for each, and the goal did not say.",
          exhaustive: true,
          options: [
            { id: "q1_1", label: "reverse-stranded", recommended: true },
            { id: "q1_2", label: "forward-stranded", recommended: false },
            { id: "q1_3", label: "unstranded", recommended: false },
          ] },
      ] },
    { seq: 2, role: "person", state: "answered", base_revision: 3, at: at(8), blocks: [],
      text: "why STAR and not HISAT2?" },
    { seq: 3, role: "assistant", state: "answered", base_revision: 3, at: at(9), text: "",
      blocks: [
        { kind: "narrative", id: "reply-3", refers_to: ["star_align"],
          text: "STAR is here because the reads are 150bp and paired, which is what the rule for " +
            "splice-aware alignment reads. HISAT2 is the other aligner on offer." },
        { kind: "receipt", id: "receipt-3", summary: "you moved STAR_ALIGN on the canvas",
          revision: 3, by: "person" },
        { kind: "setting_request", id: "setting-3", node: "star_align", setting: "seq_platform",
          current: null, options: [], reason: "No rule settles the sequencing platform.",
          premise: "read_length is 150, measured" },
        { kind: "change_set", id: "change-3", summary: "Swap the aligner",
          adds: ["hisat2_align"], removes: ["star_align"], settings: ["seq_platform"] },
      ] },
    { seq: 4, role: "assistant", state: "answered", base_revision: 4, at: at(12), text: "",
      blocks: [
        { kind: "notice", id: "n-refusal", notice: "refusal", code: "MI0205",
          text: "The reply named an option nobody offered, so nothing was applied." },
        { kind: "notice", id: "n-stale", notice: "stale", code: "MI0206",
          text: "The registry moved while the step was open. A fresh proposal is waiting." },
        { kind: "notice", id: "n-validation", notice: "validation", code: null,
          text: "annotation.gtf is read by two steps and supplied once." },
        { kind: "notice", id: "n-complete", notice: "complete", code: null,
          text: "Every step the blueprint holds is in the draft." },
      ] },
    { seq: 5, role: "person", state: "answered", base_revision: 4, at: at(13), blocks: [],
      text: "and what does the sorter do?" },
    { seq: 6, role: "assistant", state: "pending", base_revision: 4, at: at(13), text: "",
      blocks: [] },
  ],
  history: [
    { id: "h-goal", kind: "goal", state: "accepted", by: "person", chosen_option: null,
      chosen_contract: null, at: at(2),
      block: { kind: "goal_summary", id: "goal-1", goal: { have: [], want: [] }, have: "", do: "",
        get: "a gene-level counts matrix" } },
    { id: "h-index", kind: "step", state: "accepted", by: "person", chosen_option: "keep",
      chosen_contract: INDEX, at: at(3),
      block: { kind: "step_proposal", id: "step-star_genomegenerate", node: "star_genomegenerate",
        contract: INDEX, produces: ["genome.index.star"], reason: "STAR needs an index.", tier: 2,
        alternatives: [] } },
    { id: "h-trim", kind: "step", state: "accepted", by: "person", chosen_option: "keep",
      chosen_contract: TRIM, at: at(4),
      block: { kind: "step_proposal", id: "step-trimgalore", node: "trimgalore", contract: TRIM,
        produces: ["fastq.reads"], reason: "STAR asks for trimmed reads.", tier: 2,
        alternatives: [] } },
    { id: "h-align", kind: "step", state: "accepted", by: "person", chosen_option: "keep",
      chosen_contract: ALIGN, at: at(5),
      block: { kind: "step_proposal", id: "step-star_align", node: "star_align", contract: ALIGN,
        produces: ["alignment.bam"], reason: "The rule for 150bp paired reads.", tier: 3,
        alternatives: [] } },
  ],
  pending_proposal: {
    id: "p-sort",
    kind: "step",
    draft_revision: 4,
    options: ["alt_1", "keep"],
    edges: [{ from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" }],
    block: { kind: "step_proposal", id: "step-samtools_sort", node: "samtools_sort", contract: SORT,
      produces: ["alignment.bam"], tier: 2,
      alternatives: [{ id: "alt_1", label: "SAMTOOLS_SORMADUP", recommended: false,
        note: "Sorts and marks duplicates in one pass. Adds a step you did not ask for." }],
      reason: "Nothing downstream reads an unsorted BAM. This is structural — there is no version " +
        "of your pipeline without a sort." },
  },
} as unknown as AuthoringSession;

const port = (name: string, type_id: string, side: "in" | "out", states: string[] = []) =>
  ({ name, type_id, side, met: true, states });

/** Ports for the fixture's steps, in the drawn view's shape. */
export const FAKE_STEPS = {
  star_genomegenerate: { id: "star_genomegenerate", process: "STAR_GENOMEGENERATE", contract_id: INDEX,
    tier: 2, reason: "", settings: [],
    ports: [port("fasta", "genome.fasta", "in"), port("gtf", "annotation.gtf", "in"),
      port("index", "genome.index.star", "out")] },
  trimgalore: { id: "trimgalore", process: "TRIMGALORE", contract_id: TRIM, tier: 2, reason: "",
    settings: [], ports: [port("reads", "fastq.reads", "in"),
      port("reads", "fastq.reads", "out", ["trimmed"])] },
  star_align: { id: "star_align", process: "STAR_ALIGN", contract_id: ALIGN, tier: 3, reason: "",
    settings: [{}, {}, {}], ports: [port("reads", "fastq.reads", "in", ["trimmed"]),
      port("index", "genome.index.star", "in"), port("bam", "alignment.bam", "out")] },
  samtools_sort: { id: "samtools_sort", process: "SAMTOOLS_SORT", contract_id: SORT, tier: 2,
    reason: "", settings: [], ports: [port("bam", "alignment.bam", "in"),
      port("bam", "alignment.bam", "out", ["coordinate_sorted"])] },
} as unknown as Record<string, Step>;
