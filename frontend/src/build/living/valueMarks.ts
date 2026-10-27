import { open, optionalOpen, type Answered } from "../useBuilder";

type Tiers = { name: (tier: number) => string; group: (tier: number) => string };

/** **The mark on a value**: how it was decided, in served tier words, coloured by meaning.
 *  A rule's value is named by its evidence, never its tier (issue 397, as issue 268): *measured*
 *  only when what it read was measured. */
export function markOf(setting: Answered, tiers: Tiers): { words: string; tone: "measured" | "open" | "yours" | "plain" } {
  if (open(setting)) return { words: "needs you", tone: "open" };
  if (optionalOpen(setting)) return { words: "optional", tone: "plain" };
  if (setting.answered) return { words: "your answer", tone: "yours" };
  if (setting.tier !== 3) return { words: tiers.name(setting.tier).toLowerCase(), tone: "plain" };
  if (setting.evidence === "measured") return { words: tiers.name(3).toLowerCase(), tone: "measured" };
  if (setting.evidence === "read_by_ai") return { words: "read by AI", tone: "plain" };
  return { words: tiers.group(3).toLowerCase(), tone: "plain" };
}

/** Each tone's colours: measured and open each spend their one colour; the rest spend none. */
export const MARK_STYLE: Record<ReturnType<typeof markOf>["tone"], React.CSSProperties> = {
  measured: { background: "var(--measured-soft)", color: "var(--measured-ink)" },
  open: { background: "var(--needs-you-soft)", color: "var(--needs-you-ink)" },
  yours: { background: "var(--now-soft)", color: "var(--now-ink)" },
  plain: { border: "1px solid var(--line-2)", color: "var(--ink-2)" },
};
