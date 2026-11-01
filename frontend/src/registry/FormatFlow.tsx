import { useState } from "react";

import { ribbons, SHOWN, sideRows, ROW, type FlowRow } from "./flowRows";
import type { CataloguePage } from "./useCatalogue";
import { useFilters, useFlow } from "./useCatalogue";

const WORDS: Record<string, string> = {
  fastq: "reads", fasta: "sequence", bam: "alignments", cram: "alignments", vcf: "variants",
  bed: "regions", gff: "annotation", table: "tsv, csv", report: "html, pdf",
};

function Side({ label, total, rows, picked, query, onQuery, onPick }: {
  label: string; total: number; rows: FlowRow[]; picked: string | null;
  query: string; onQuery: (q: string) => void; onPick: (format: string) => void;
}) {
  return (
    <div className="flex flex-col gap-[2px] min-w-0">
      <input type="search" aria-label={`Find a format it ${label.toLowerCase()}`} value={query} autoComplete="off"
             placeholder={`${label}: find among ${total.toLocaleString("en")}`}
             onChange={(event) => onQuery(event.target.value)} className="facet-find" />
      {rows.map((row) => (
        <button key={row.format} type="button" className="bar h-[28px]" aria-pressed={row.format === picked}
                onClick={() => onPick(row.format)}>
          <span className="bar-fill" style={{ width: `${row.share * 100}%` }} />
          <span className="bar-label"><span className="font-data">{row.format}</span>{" "}
            <span className="text-[11.5px] text-ink-3">{WORDS[row.format] ?? ""}</span></span>
          <span className="bar-count">{row.count.toLocaleString("en")}</span>
        </button>
      ))}
      {rows.length === 0 && <p className="m-0 px-2 py-[6px] text-[12.5px] text-ink-3">No format matches.</p>}
    </div>
  );
}

/** How file formats connect. There are hundreds, so this shows the strongest and a search on each
 *  side reaches the rest. Picking a format follows it, and each side narrows the other. */
export function FormatFlow({ page, total }: { page: CataloguePage; total: number }) {
  const filters = useFilters();
  const [findReads, setFindReads] = useState("");
  const [findMakes, setFindMakes] = useState("");
  const reads = filters.reads[0] ?? null;
  const makes = filters.makes[0] ?? null;
  const left = sideRows(page.counts.reads, findReads, reads, page.aliases);
  const right = sideRows(page.counts.makes, findMakes, makes, page.aliases);
  const names = (rows: FlowRow[]) => rows.map((r) => r.format);
  const links = useFlow(names(left), names(right)).data ?? [];
  const drawn = ribbons(links, names(left), names(right), reads, makes);
  const hint = reads && makes ? `${total.toLocaleString("en")} modules read ${reads} and make ${makes}.`
    : reads ? `What ${reads} turns into. Pick a format on the right to narrow down.`
      : makes ? `What ${makes} comes from. Pick a format on the left to narrow down.`
        : "Pick a format to follow it, or search each side for the rest.";

  return (
    <section aria-labelledby="flow-title" className="bg-surface border border-line rounded-panel px-[16px] py-[12px] flex flex-col gap-2">
      <div className="flex flex-wrap justify-between items-baseline gap-x-[14px]">
        <h2 id="flow-title" className="m-0 text-[15px] font-semibold">How file formats connect</h2>
        <span aria-live="polite" className="text-[12.5px] text-ink-2">{hint}</span>
      </div>
      <div className="format-flow">
        <Side label="Reads" total={Object.keys(page.counts.reads).length} rows={left} picked={reads} query={findReads}
              onQuery={setFindReads} onPick={(f) => filters.set("reads", f === reads ? [] : [f])} />
        <svg aria-hidden="true" className="ribbons" viewBox={`0 0 100 ${SHOWN * ROW}`} preserveAspectRatio="none">
          {drawn.map((r) => (
            <path key={r.key} d={r.d} strokeWidth={r.width} vectorEffect="non-scaling-stroke"
                  data-lit={r.lit} />
          ))}
        </svg>
        <Side label="Makes" total={Object.keys(page.counts.makes).length} rows={right} picked={makes} query={findMakes}
              onQuery={setFindMakes} onPick={(f) => filters.set("makes", f === makes ? [] : [f])} />
      </div>
    </section>
  );
}
