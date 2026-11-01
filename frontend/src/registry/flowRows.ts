export type FlowRow = { format: string; count: number; share: number };
export type Link = { reads: string; makes: string; modules: number };
export type Ribbon = { key: string; d: string; width: number; lit: boolean };

export const SHOWN = 7;
export const ROW = 30;
const QUIET = new Set(["log", "yaml"]);
const AT_REST = 18;
const WIDEST = 15;

/** One side of the flow: the top formats, or what a search reaches. There can be hundreds, so a
 *  fixed list could never hold them; what is picked always stays on show. */
export function sideRows(tally: Record<string, number>, query: string, picked: string | null,
                         aliases: Record<string, string>): FlowRow[] {
  const q = query.trim().toLowerCase();
  const named = aliases[q] ?? q;
  const matches = (f: string) => !q || f.includes(q) || f === named;
  const names = Object.keys(tally).filter(matches).filter((f) => q || !QUIET.has(f))
    .sort((a, b) => tally[b] - tally[a] || a.localeCompare(b));
  const top = names.slice(0, SHOWN);
  if (picked && !q && !top.includes(picked)) top.splice(SHOWN - 1, 1, picked), top.unshift(top.pop()!);
  const most = Math.max(1, ...top.map((f) => tally[f] ?? 0));
  return top.map((format) => ({ format, count: tally[format] ?? 0, share: (tally[format] ?? 0) / most }));
}

/** The links as paths in a 100-wide box, one row to a format. Square root, so a link of ten is
 *  still seen beside one of hundreds. */
export function ribbons(links: Link[], left: string[], right: string[],
                        pickedLeft: string | null, pickedRight: string | null): Ribbon[] {
  const y = (list: string[], format: string) => list.indexOf(format) * ROW + 14;
  const picked = pickedLeft !== null || pickedRight !== null;
  const shown = links.filter((l) => left.includes(l.reads) && right.includes(l.makes))
    .filter((l) => !picked || l.reads === pickedLeft || l.makes === pickedRight)
    .sort((a, b) => b.modules - a.modules);
  const most = Math.max(1, ...shown.map((l) => l.modules));
  return (picked ? shown : shown.slice(0, AT_REST)).map((l) => {
    const a = y(left, l.reads);
    const b = y(right, l.makes);
    return { key: `${l.reads}>${l.makes}`, d: `M 0 ${a} C 50 ${a}, 50 ${b}, 100 ${b}`,
             width: Math.max(1, Math.sqrt(l.modules / most) * WIDEST), lit: picked };
  });
}
