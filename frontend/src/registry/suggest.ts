export type Pick = { reads?: string; makes?: string; topic?: string; suite?: string; module?: string };
export type Suggestion = { kind: string; label: string; sub: string; n: number | null; pick: Pick };
export type SuggestionGroup = { title: string; items: Suggestion[] };
type Tallies = { reads: Record<string, number>; makes: Record<string, number>;
                 topics: Record<string, number>; suites: Record<string, number> };

const COMMON = ["fastq", "fasta", "bam"];
const RARE = 5;
const CONVERSION = /^([\w.]+)\s*(?:to|->|→|>)\s*([\w.]+)$/;

function byCount(tally: Record<string, number>): string[] {
  return Object.keys(tally).sort((a, b) => tally[b] - tally[a] || a.localeCompare(b));
}

/** What a person might mean by what they have typed, from the counts the page already holds.
 *  `bam to vcf` is a conversion; `fa` is `fasta`; a format used by almost nothing is noise. */
export function suggest(typed: string, counts: Tallies, aliases: Record<string, string>,
                        rows: { path: string; description?: string | null }[]): SuggestionGroup[] {
  const q = typed.trim().toLowerCase();
  const named = (format: string) => aliases[format] ?? format;
  const groups: SuggestionGroup[] = [];

  const conversion = q.match(CONVERSION);
  if (conversion) {
    const reads = named(conversion[1]);
    const makes = named(conversion[2]);
    groups.push({ title: "That conversion", items: [{
      kind: "", label: `${reads} → ${makes}`, sub: `read ${reads}, make ${makes}`, n: null,
      pick: { reads, makes } }] });
    return groups;
  }

  const seen = new Set([...Object.keys(counts.reads), ...Object.keys(counts.makes)]);
  const hits = (q ? [...seen].filter((f) =>
    f === q || f === named(q) || (f.includes(q) && (counts.reads[f] ?? 0) + (counts.makes[f] ?? 0) >= RARE))
    : COMMON.filter((f) => seen.has(f)))
    .sort((a, b) => (counts.reads[b] ?? 0) + (counts.makes[b] ?? 0) - (counts.reads[a] ?? 0) - (counts.makes[a] ?? 0))
    .slice(0, 3);
  const formats = hits.flatMap((format) => {
    const also = Object.keys(aliases).filter((a) => aliases[a] === format).join(", ");
    const sub = also ? `also ${also}` : "";
    const sides: Suggestion[] = [];
    if (counts.reads[format]) sides.push({ kind: "reads", label: format, sub, n: counts.reads[format], pick: { reads: format } });
    if (counts.makes[format]) sides.push({ kind: "makes", label: format, sub, n: counts.makes[format], pick: { makes: format } });
    return sides;
  });
  if (formats.length) groups.push({ title: "File formats", items: formats });

  const topics = byCount(counts.topics).filter((t) => t.includes(q)).slice(0, 3)
    .map((topic) => ({ kind: "", label: topic, sub: "", n: counts.topics[topic], pick: { topic } }));
  if (topics.length) groups.push({ title: "Topics", items: topics });

  if (q) {
    const suites = byCount(counts.suites).filter((s) => s.includes(q) && counts.suites[s] > 1).slice(0, 3)
      .map((suite) => ({ kind: "", label: suite, sub: "suite", n: counts.suites[suite], pick: { suite } }));
    if (suites.length) groups.push({ title: "Tool suites", items: suites });
    const modules = rows.filter((r) => `${r.path} ${r.description ?? ""}`.toLowerCase().includes(q)).slice(0, 4)
      .map((r) => ({ kind: "", label: r.path, sub: r.description ?? "", n: null, pick: { module: r.path } }));
    if (modules.length) groups.push({ title: "Modules", items: modules });
  }
  return groups;
}
