import { toneOf } from "./families";
import { ribbons, SHOWN, sideRows, ROW, type FlowRow } from "./flowRows";
import type { CataloguePage } from "./useCatalogue";
import { useFilters, useFlow } from "./useCatalogue";

export const FORMAT_WORDS: Record<string, string> = {
  fastq: "reads", fasta: "sequence", bam: "alignments", cram: "alignments", vcf: "variants",
  bed: "regions", gff: "annotation", table: "tsv, csv", report: "html, pdf", txt: "text", json: "data",
};

function Side({ label, rows, picked, align, onPick }: {
  label: string; rows: FlowRow[]; picked: string | null; align: "left" | "right"; onPick: (format: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[2px] min-w-0">
      <span className={`px-2 pb-1 text-[11.5px] font-semibold text-ink-3 ${align === "right" ? "text-right" : ""}`}>{label}</span>
      {rows.map((row) => {
        const tone = toneOf(row.format);
        return (
          <button key={row.format} type="button" className="bar h-[28px]" aria-pressed={row.format === picked}
                  onClick={() => onPick(row.format)}>
            <span className="bar-fill" style={{ width: `${row.share * 100}%`, background: tone.soft }} />
            <span className="bar-label"><span className="font-data font-semibold">{row.format}</span>{" "}
              <span className="text-[11.5px] text-ink-3">{FORMAT_WORDS[row.format] ?? ""}</span></span>
            <span className="bar-count">{row.count.toLocaleString("en")}</span>
          </button>
        );
      })}
    </div>
  );
}

/** **How file formats connect** (board "7 · Registry"): the strongest formats each tools take
 *  (left) and make (right), coloured by family, each band the tools between two. Picking a format
 *  lights its bands and filters the list to tools that take or make it. */
export function FormatFlow({ page }: { page: CataloguePage; total: number }) {
  const filters = useFilters();
  const reads = filters.reads[0] ?? null;
  const makes = filters.makes[0] ?? null;
  const left = sideRows(page.counts.reads, "", reads, page.aliases);
  const right = sideRows(page.counts.makes, "", makes, page.aliases);
  const names = (rows: FlowRow[]) => rows.map((r) => r.format);
  const links = useFlow(names(left), names(right)).data ?? [];
  const drawn = ribbons(links, names(left), names(right), reads, makes);
  const rows = Math.max(1, left.length, right.length);

  return (
    <section aria-labelledby="flow-title" className="reg-formats bg-surface border border-line rounded-panel px-5 pt-4 pb-3 flex flex-col gap-1">
      <div className="flex flex-wrap items-baseline gap-x-[10px] gap-y-1 min-h-[26px]">
        <h2 id="flow-title" className="m-0 text-[15px] font-semibold">How file formats connect</h2>
        <span className="text-[12.5px] text-ink-3">Each band is the tools that take the left format and make the right one. Pick a format to see its tools.</span>
        {(reads || makes) && (
          <button type="button" onClick={() => filters.change((next) => { next.delete("reads"); next.delete("makes"); })}
                  className="ml-auto h-[26px] px-[10px] rounded-full border border-now-line bg-now-soft text-[12px] font-semibold text-now-ink cursor-pointer">
            {[reads, makes].filter(Boolean).join(" → ")} ×
          </button>
        )}
      </div>
      <div className="format-flow">
        <Side label="Takes" rows={left} picked={reads} align="left" onPick={(f) => filters.set("reads", f === reads ? [] : [f])} />
        <svg aria-hidden="true" className="ribbons" viewBox={`0 0 100 ${rows * ROW}`} preserveAspectRatio="none"
             style={{ height: `${(210 / SHOWN) * rows}px`, marginTop: 24 }}>
          {drawn.map((r) => (
            <path key={r.key} d={r.d} strokeWidth={r.width} vectorEffect="non-scaling-stroke"
                  data-lit={r.lit} style={{ stroke: toneOf(r.key.split(">")[0]).line }} />
          ))}
        </svg>
        <Side label="Makes" rows={right} picked={makes} align="right" onPick={(f) => filters.set("makes", f === makes ? [] : [f])} />
      </div>
    </section>
  );
}
