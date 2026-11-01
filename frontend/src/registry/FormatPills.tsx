const MANY = 3;
const KNOWN = ["fastq", "fasta", "bam", "cram", "vcf", "bed", "gff", "table", "report"];

/** What a row names first: the formats a reader knows by name, then the odd ones, so a cut list
 *  keeps what matters. Outlined means only mentioned in a description, not declared. */
function pills(declared: string[], mentioned: string[]) {
  const rank = (format: string) => (KNOWN.includes(format) ? KNOWN.indexOf(format) : KNOWN.length);
  return [...declared.map((format) => ({ format, mention: false })),
          ...mentioned.map((format) => ({ format, mention: true }))]
    .sort((a, b) => rank(a.format) - rank(b.format));
}

export function FormatPills({ declared, mentioned, tone = "reads", all = false }: {
  declared: string[];
  mentioned: string[];
  tone?: "reads" | "makes";
  all?: boolean;
}) {
  const found = pills(declared, mentioned);
  if (found.length === 0) return <span className="text-[11.5px] text-ink-3 shrink-0">not stated</span>;
  const shown = all ? found : found.slice(0, MANY);
  return (
    <>
      {shown.map(({ format, mention }) => (
        <span key={format} className={`pill ${mention ? "pill-mention" : tone === "makes" ? "pill-makes" : ""}`}
              title={mention ? "Mentioned in its description, not declared" : undefined}>{format}</span>
      ))}
      {found.length > shown.length && <span className="pill pill-mention">+{found.length - shown.length}</span>}
    </>
  );
}
