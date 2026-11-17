/** **A format's family colour** (board 2026-11-15, #511): reads, sequence, alignments, variants,
 *  regions and reports each have a colour, so a format reads the same in the flow, the list and a
 *  tool's card. Tables, text and anything else stay neutral. Tokens only. */
const FAMILY: Record<string, string> = {
  fastq: "done", fq: "done",
  fasta: "measured", fa: "measured", fna: "measured", fai: "measured", gzi: "measured",
  bam: "now", cram: "now", sam: "now", bai: "now", crai: "now",
  vcf: "ai", bcf: "ai",
  bed: "regions", gff: "regions", gtf: "regions",
  report: "report", html: "report", pdf: "report",
};

export type Tone = { line: string; soft: string; ink: string };

export function toneOf(format: string): Tone {
  const family = FAMILY[format.toLowerCase()];
  if (!family) return { line: "var(--ink-3)", soft: "var(--hover-strong)", ink: "var(--ink-2)" };
  // `--ai`, `--regions` and `--report` have no `-ink`: the colour itself reads on its soft tint.
  const ink = family === "done" || family === "measured" || family === "now" ? `var(--${family}-ink)` : `var(--${family})`;
  return { line: `var(--${family})`, soft: `var(--${family}-soft)`, ink };
}
