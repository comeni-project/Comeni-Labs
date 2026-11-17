/** Where a value came from (#511): every value shows it, and an AI choice stays marked AI until a
 *  person confirms it. The words and colours are the board's (`Build.dc.html`, `.by-*`). */
export type Source = "measured" | "rule" | "default" | "you" | "ai" | "not_set";

const LOOK: Record<Source, { word: string; className: string }> = {
  measured: { word: "MEASURED", className: "text-measured-ink bg-measured-soft" },
  rule: { word: "RULE", className: "text-now-ink bg-now-soft" },
  default: { word: "DEFAULT", className: "text-now-ink bg-now-soft" },
  you: { word: "YOU", className: "text-done-ink bg-done-soft" },
  ai: { word: "AI", className: "text-ai bg-ai-soft" },
  not_set: { word: "NOT SET", className: "text-needs-you-ink bg-needs-you-soft" },
};

export function SourceTag({ source }: { source: Source }) {
  const { word, className } = LOOK[source];
  return (
    <span data-source={source}
          className={`inline-flex items-center shrink-0 text-[10.5px] font-bold tracking-[.04em] leading-none
                      rounded-xs px-[6px] py-[3px] ${className}`}>
      {word}
    </span>
  );
}
