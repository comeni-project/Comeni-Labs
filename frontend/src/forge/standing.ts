/** Where a tool stands, as one scale.
 *
 * **Extracted so the board and the rows cannot drift apart.** The board draws one cell per landed
 * contract and each row draws one mark; if those were two colour maps, the day somebody changed
 * `unverifiable` in one place the page would say two things about one fact. That is the same
 * failure spec §1.3 removed at the level of whole screens.
 *
 * The colours are the ones the tiers already carry — coral for something that was true and is
 * not, amber for a premise nothing checked, pea for settled. Nothing new was added.
 */
export type Standing = "drifted" | "unverifiable" | "matching" | "drafted" | "undrafted";

export const STANDING: Record<Standing, { mark: string; cell: string; title: string }> = {
  drifted: {
    mark: "bg-[var(--undecided)]",
    cell: "bg-[var(--undecided)]",
    title: "landed, and no longer agrees with its source",
  },
  unverifiable: {
    mark: "bg-transparent border border-[var(--measured)]",
    cell: "bg-[var(--measured-soft)] border border-[var(--measured)]",
    title: "landed, and no source can re-read it",
  },
  matching: {
    mark: "bg-pea",
    cell: "bg-pea",
    title: "landed, and agrees with its source",
  },
  drafted: {
    mark: "bg-transparent border border-pea",
    cell: "bg-transparent border border-pea",
    title: "somebody is drafting it",
  },
  undrafted: {
    mark: "bg-transparent border border-line-2",
    cell: "bg-transparent border border-line-2",
    title: "nobody has drafted it",
  },
};
