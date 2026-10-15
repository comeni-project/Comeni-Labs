import type { AuthoringSession, Step } from "../../api/types";
import type { AlternativePreview } from "./useAlternativePreview";

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
  phase: "building",
  failed_from: null,
  goal: null,
  revision: 4,
  row_version: 9,
  model_configured: true,
  steps_total: 5,
  progress: { reviewed: 3, total: 5, active: { position: 4, total: 5, again: false } },
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
        { kind: "goal_summary", id: "goal-1",
          goal: { have: [{ type_id: "fastq.reads", states: [] }, { type_id: "genome.fasta", states: [] },
            { type_id: "annotation.gtf", states: [] }], want: ["counts.matrix"] },
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
    { id: "h-goal", kind: "goal", state: "accepted", by: "person", actor_kind: "person", chosen_option: null,
      chosen_contract: null, at: at(2),
      block: { kind: "goal_summary", id: "goal-1", goal: { have: [], want: [] }, have: "", do: "",
        get: "a gene-level counts matrix" } },
    { id: "h-index", envelope: { offer: "step", progress: { position: 1, total: 5, again: false } }, kind: "step", state: "accepted", by: "person", actor_kind: "person", chosen_option: "keep",
      chosen_contract: INDEX, at: at(3),
      block: { kind: "step_proposal", id: "step-star_genomegenerate", node: "star_genomegenerate",
        contract: INDEX, produces: ["genome.index.star"], reason: "STAR needs an index.", tier: 2,
        alternatives: [] } },
    { id: "h-trim", envelope: { offer: "step", progress: { position: 2, total: 5, again: false } }, kind: "step", state: "accepted", by: "person", actor_kind: "person", chosen_option: "keep",
      chosen_contract: TRIM, at: at(4),
      block: { kind: "step_proposal", id: "step-trimgalore", node: "trimgalore", contract: TRIM,
        produces: ["fastq.reads"], reason: "STAR asks for trimmed reads.", tier: 2,
        alternatives: [] } },
    { id: "h-align", envelope: { offer: "step", progress: { position: 3, total: 5, again: false } }, kind: "step", state: "accepted", by: "person", actor_kind: "person", chosen_option: "keep",
      chosen_contract: ALIGN, at: at(5),
      block: { kind: "step_proposal", id: "step-star_align", node: "star_align", contract: ALIGN,
        produces: ["alignment.bam"], reason: "The rule for 150bp paired reads.", tier: 3,
        alternatives: [] } },
  ],
  pending_proposal: {
    id: "p-sort",
    kind: "step",
    envelope: { offer: "step", preview_options: ["alt_1"] },
    draft_revision: 4,
    options: ["alt_1", "keep"],
    edges: [{ from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" }],
    block: { kind: "step_proposal", id: "step-samtools_sort", node: "samtools_sort", contract: SORT,
      consumes: ["alignment.bam"], produces: ["alignment.bam"], tier: 2,
      alternatives: [{ id: "alt_1", label: "SAMTOOLS_SORMADUP", recommended: false,
        note: "Sorts and marks duplicates in one pass. Adds a step you did not ask for." }],
      reason: "Nothing downstream reads an unsorted BAM. This is structural — there is no version " +
        "of your pipeline without a sort." },
  },
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
    settings: [{}, {}, {}], ports: [port("reads", "fastq.reads", "in", ["trimmed"]),
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
  { name: "reads", param: "input", type_id: "fastq.reads", scope: "sample", count: 12, states: [],
    ports: ["trimgalore.reads"] },
  { name: "fasta", param: "fasta", type_id: "genome.fasta", scope: "run", count: null, states: [],
    ports: ["star_genomegenerate.fasta"] },
  { name: "gtf", param: "gtf", type_id: "annotation.gtf", scope: "run", count: null, states: [],
    ports: ["star_genomegenerate.gtf"] },
] as unknown as import("../../api/schema").components["schemas"]["ChannelView"][];

/** 1→1, N→N and N→1, the three collection shapes, on one small graph — `LivingCollect`'s content. */
export const COLLECT_SESSION = {
  ...FAKE_SESSION,
  name: "rnaseq-counts",
  phase: "complete",
  steps_total: 4,
  progress: { reviewed: 4, total: 4, active: null },
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
  history: [],
  pending_proposal: null,
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
  { name: "reference", param: "index", type_id: "genome.index.star", scope: "run", count: null,
    states: [], ports: ["star_align.index"] },
  { name: "reads", param: "input", type_id: "fastq.reads", scope: "sample", count: 12,
    states: ["paired"], ports: ["trimgalore.reads"] },
] as unknown as import("../../api/schema").components["schemas"]["ChannelView"][];

/** Part F: asserted answers remain selected while a sample disagrees. */
export const CONFLICT_SESSION = {
  ...FAKE_SESSION,
  turns: FAKE_SESSION.turns.filter(turn => turn.seq <= 1).map(turn => ({ ...turn,
    blocks: turn.blocks.filter(block => block.kind === "goal_summary") })),
  phase: "building", decision_revision: 2, projection_current: false, ownership: "authored",
  facts: [{ kind: "measurement", subject: "paired", value: false, source: "person_said", states: [], pieces: [] }],
  inputs: [{ key: "fastq.reads", type_id: "fastq.reads", present: true, origin: "person_said", states: [] }],
  pending_proposal: {
    id: "disagree-paired", kind: "disagreement", draft_revision: 4, edges: [],
    options: ["keep_current", "use_measurement", "correct", "unknown"],
    envelope: {
      offer: "disagreement", context: { draft_revision: 4, decision_revision: 2, session_version: 3, registry: "fixture" },
      subject: "paired", observation_id: "observation-paired", current_revision_id: "selected-paired",
      current_value: false, current_origin: "person_said", observed_value: true, observed_origin: "measured", continuation: "build",
      options: { keep_current: "Keep no (you said)", use_measurement: "Use yes (measured)", correct: "Use another answer", unknown: "Return to unknown" },
      block: { kind: "question", id: "disagreement-3", asks: "For paired, your answer is no (you said), but this sample says yes (measured). Which should we use?",
        why_open: "Evidence never replaces your selected answer automatically.", exhaustive: true, phrasing: "none",
        options: [ { id: "keep_current", recommended: false, label: "Keep no (you said)" }, { id: "use_measurement", recommended: false, label: "Use yes (measured)" },
          { id: "correct", recommended: false, label: "Use another answer" }, { id: "unknown", recommended: false, label: "Return to unknown" } ] },
    },
    block: { kind: "question", id: "disagreement-3", asks: "For paired, your answer is no (you said), but this sample says yes (measured). Which should we use?",
      why_open: "Evidence never replaces your selected answer automatically.", exhaustive: true, phrasing: "none",
      options: [ { id: "keep_current", recommended: false, label: "Keep no (you said)" }, { id: "use_measurement", recommended: false, label: "Use yes (measured)" },
        { id: "correct", recommended: false, label: "Use another answer" }, { id: "unknown", recommended: false, label: "Return to unknown" } ] },
  },
} as AuthoringSession;

const SORMADUP = "nf-core/samtools/sormadup@1.21.0";

/** The sorter's one alternative as its **complete saved preview**: the whole pipeline it gives,
 *  read the way a live session reads one, so the fixtures exercise the same preview canvas. */
export function fakePreview(session: AuthoringSession, option: string): AlternativePreview {
  const context = session.canvas?.context ?? { draft_revision: session.revision, decision_revision: 0,
                                               session_version: session.row_version ?? 0, registry: "fixture" };
  const kept = ["star_genomegenerate", "trimgalore", "star_align"];
  return {
    option_id: option,
    contract: SORMADUP,
    observed_context: context,
    frame: {
      context, proposal_id: session.pending_proposal?.id ?? null, current: true,
      graph: {
        nodes: [...kept.map((id) => ({ id, contract_id: FAKE_STEPS[id].contract_id, params: [] })),
                { id: "samtools_sormadup", contract_id: SORMADUP, params: [] }],
        edges: [
          { from_node: "trimgalore", from_port: "reads", to_node: "star_align", to_port: "reads" },
          { from_node: "star_genomegenerate", from_port: "index", to_node: "star_align", to_port: "index" },
          { from_node: "star_align", from_port: "bam", to_node: "samtools_sormadup", to_port: "bam" },
        ],
      },
      steps: [...kept.map((id) => FAKE_STEPS[id]),
        { id: "samtools_sormadup", process: "SAMTOOLS_SORMADUP", contract_id: SORMADUP, tier: 2,
          runs: "per_item", reason: "", settings: [],
          ports: [port("bam", "alignment.bam", "in"),
                  port("bam", "alignment.bam", "out", ["coordinate_sorted", "duplicates_marked"])] },
      ] as unknown as AlternativePreview["frame"]["steps"],
      channels: FAKE_CHANNELS,
      placement: { ...FAKE_SESSION.placement, samtools_sormadup: FAKE_SESSION.placement.samtools_sort },
    },
  };
}

/** A fixture's preview reader: the option is the path's last segment, before its query. */
export const readFakePreview = (session: AuthoringSession) => (path: string) =>
  Promise.resolve(fakePreview(session, path.split("?")[0].split("/").pop() ?? ""));
