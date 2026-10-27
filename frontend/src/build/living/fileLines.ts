/** One line of `pipeline.yml`, as the setting it belongs to. */
export type LineRef = { step: string; setting: string; head: boolean };

/** **Which setting each line of the file is** (one builder plan 5): read from the file's own
 *  layout, never by parsing it into something else. A step opens at `- id:`; its settings are the
 *  `  - name:` items under `  settings:`, each running until the next item or the next key at the
 *  step's own depth. The text stays the server's; this only says where each line belongs. */
export function fileLines(text: string): (LineRef | null)[] {
  let step: string | null = null;
  let inSettings = false;
  let setting: string | null = null;
  return text.split("\n").map((line) => {
    const indent = line.length - line.trimStart().length;
    const id = /^- id: (\S+)/.exec(line);
    if (id) {
      step = id[1];
      inSettings = false;
      setting = null;
      return null;
    }
    if (indent === 0 && line.trim() !== "") {
      step = null;
      inSettings = false;
      setting = null;
      return null;
    }
    if (step && indent === 2 && /^ {2}settings:\s*$/.test(line)) {
      inSettings = true;
      setting = null;
      return null;
    }
    const item = /^ {2}- name: (\S+)/.exec(line);
    if (step && inSettings && item) {
      setting = item[1];
      return { step, setting, head: true };
    }
    if (step && inSettings && setting && indent >= 4) return { step, setting, head: false };
    if (indent <= 2) {
      inSettings = false;
      setting = null;
    }
    return null;
  });
}
