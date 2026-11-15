/** A run of lines in `pipeline.yml` that can be folded to one summary (#499). Lines are 0-based;
 *  `start` is the key's own line, which stays drawn with the summary after it. */
export type Fold = {
  start: number;
  end: number;
  key: string;
  /** The step the fold is in, or `null` for a top-level section. */
  step: string | null;
  summary: string;
  /** Whether it is folded to begin with: a step's module, why and inputs are. */
  folded: boolean;
};

/** A step's own keys stay open only for its settings: everything else is provenance a reader
 *  opens when they want it (#499). */
const OPEN_STEP_KEYS = new Set(["settings"]);

const indentOf = (line: string) => line.length - line.trimStart().length;
const valueOf = (lines: string[], from: number, to: number, key: string) => {
  for (let i = from; i <= to; i += 1) {
    const found = new RegExp(`^\\s*-?\\s*${key}:\\s*(.+)$`).exec(lines[i]);
    if (found) return found[1].replace(/^'/, "").replace(/'$/, "").replace(/''/g, "'");
  }
  return null;
};

/** **What folds, read from the file's own layout** (as `fileLines` reads settings): each
 *  top-level section with content, and each step's keys but its settings. The text stays
 *  the server's; this only says which lines go together and what one line says for them. */
export function folds(text: string): Fold[] {
  const lines = text.split("\n");
  const found: Fold[] = [];
  const blockEnd = (start: number, depth: number) => {
    let end = start;
    for (let i = start + 1; i < lines.length; i += 1) {
      if (lines[i].trim() === "") continue;
      const indent = indentOf(lines[i]);
      // A list item at the key's own depth still belongs to it (`  - port: reads` under `  inputs:`).
      if (indent < depth || (indent === depth && !/^\s*- /.test(lines[i]))) break;
      if (depth === 0 && indent === 0 && !/^- /.test(lines[i])) break;
      end = i;
    }
    return end;
  };

  let step: string | null = null;
  lines.forEach((line, i) => {
    const top = /^([a-z_]+):\s*$/.exec(line);
    if (top) {
      step = null;
      const end = blockEnd(i, 0);
      if (end > i) found.push({ start: i, end, key: top[1], step: null, summary: `{ ${end - i} lines }`, folded: false });
      return;
    }
    const id = /^- id: (\S+)/.exec(line);
    if (id) { step = id[1]; return; }
    const key = /^ {2}([a-z_]+):\s*$/.exec(line);
    if (step && key && !OPEN_STEP_KEYS.has(key[1])) {
      const end = blockEnd(i, 2);
      if (end <= i) return;
      const count = `${end - i + 1} lines`;
      let words: string;
      if (key[1] === "module") words = valueOf(lines, i, end, "contract_id") ?? "module";
      else if (key[1] === "why") {
        const tier = valueOf(lines, i, end, "tier");
        const reason = valueOf(lines, i, end, "reason");
        words = [tier && `tier ${tier}`, reason && (reason.length > 48 ? `${reason.slice(0, 47)}…` : reason)]
          .filter(Boolean).join(" · ");
      } else if (key[1] !== "inputs") {
        words = "";
      } else {
        const wired = [];
        for (let j = i; j <= end; j += 1) {
          const port = /^\s*- port:\s*(\S+)/.exec(lines[j]);
          if (!port) continue;
          // Fed by a step (`source: step.port`) or by one of the run's inputs (`channel: name`).
          const around = Math.min(end, j + 4);
          const source = valueOf(lines, j + 1, around, "source");
          const channel = valueOf(lines, j + 1, around, "channel");
          wired.push(source && source !== "null" ? `${port[1]} ← ${source.split(".")[0]}`
            : channel && channel !== "null" ? `${port[1]} ← channel ${channel}` : port[1]);
        }
        words = wired.slice(0, 3).join(" · ");
      }
      found.push({ start: i, end, key: key[1], step, summary: `{ ${words ? `${words} · ` : ""}${count} }`, folded: true });
    }
  });
  return found;
}
