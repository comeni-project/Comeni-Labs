import type { ContractField, FilePane } from "../../api/registry";

/** The candidate's files and fields, each line carrying where it came from.
 *
 * **The gutter is the point of this pane, not decoration** — §8.5 asks for `SOURCE`, `DERIVED`,
 * `AI` and `HUMAN` labels with *colour secondary*. A reviewer scanning an nf-core module should
 * see an unbroken column of one letter; a block of a different one is then loud without anybody
 * having been told what to look for. The letter carries it and the colour agrees.
 *
 * **`main.nf` is shown as copied or as authored, and that is a rule being checked.** A source
 * that ships Nextflow gets a contract bound to its process and nothing downstream may author
 * one — so an authored `main.nf` beside a source that shipped one is the rule broken, and the
 * only way to see it is for the pane to say which it is.
 */

const ORIGIN: Record<string, { tone: string; letter: string; word: string }> = {
  derived: { tone: "var(--rail)", letter: "S", word: "read from the source" },
  model: { tone: "var(--link)", letter: "A", word: "proposed by the model" },
  human: { tone: "var(--measured)", letter: "H", word: "answered by a person" },
  resolver: { tone: "var(--pea)", letter: "D", word: "derived by the forge" },
  goal: { tone: "var(--pea)", letter: "D", word: "derived by the forge" },
  measured: { tone: "var(--pea)", letter: "D", word: "derived by the forge" },
};

export function OriginKey() {
  const seen = new Set<string>();
  return (
    <div className="flex flex-wrap gap-5 py-4">
      {Object.values(ORIGIN)
        .filter((origin) => !seen.has(origin.letter) && seen.add(origin.letter))
        .map((origin) => (
          <span key={origin.letter} className="flex items-center gap-[7px] text-secondary text-ink-3">
            <span
              aria-hidden="true"
              className="w-[3px] h-[13px]"
              style={{ background: origin.tone }}
            />
            <span className="font-data text-[9.5px]" style={{ color: origin.tone }}>
              {origin.letter}
            </span>
            {origin.word}
          </span>
        ))}
    </div>
  );
}

/** The contract, as the lines it will be written as, with each field's origin in the gutter.
 *
 * **Assembled from the fields rather than from a rendered file.** The server holds the contract
 * as `field -> FilledValue`, and asking it to also serialise a YAML document would be a second
 * spelling of `contract_from` that could disagree with the one `land.py` writes.
 */
export function ContractPane({
  fields,
  selected,
  onSelect,
}: {
  fields: ContractField[];
  selected: string;
  onSelect: (holeId: string) => void;
}) {
  return (
    <div className="border border-line bg-surface rounded-[var(--r)] min-w-0">
      <div className="flex items-baseline justify-between px-3.5 py-3 border-b border-line">
        <span className="font-data text-[11.5px] text-ink">contract.yml</span>
        <span className="font-data text-label text-ink-3">
          {fields.length} field{fields.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="overflow-x-auto py-2.5">
        <div className="min-w-[440px]">
          {fields.map((field, i) => {
            const origin = ORIGIN[field.how] ?? ORIGIN.derived;
            const target = field.hole_id || field.field;
            return (
              <button
                key={field.field}
                type="button"
                onClick={() => onSelect(target)}
                aria-pressed={selected === target}
                title={`${origin.word} — ${field.why}`}
                className={`lift flex items-baseline w-full text-left ${
                  selected === target ? "bg-surface-2" : ""
                }`}
              >
                <span className="font-data text-[9.5px] text-ink-3 flex-[0_0_30px] text-right pr-[9px]">
                  {i + 1}
                </span>
                <span
                  aria-hidden="true"
                  className="flex-[0_0_3px] self-stretch"
                  style={{ background: origin.tone }}
                />
                <span
                  className="font-data text-[9px] flex-[0_0_20px] text-center"
                  style={{ color: origin.tone }}
                >
                  {origin.letter}
                </span>
                <span className="font-data text-[11px] whitespace-pre text-ink">
                  {field.field}: {field.value}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function CodePane({ file }: { file: FilePane }) {
  const lines = file.text.split("\n");
  const tone = file.authored ? ORIGIN.model : ORIGIN.derived;
  return (
    <div className="border border-line bg-surface rounded-[var(--r)] min-w-0">
      <div className="flex items-baseline justify-between px-3.5 py-3 border-b border-line">
        <span className="font-data text-[11.5px] text-ink">{file.path}</span>
        <span className="font-data text-label text-ink-3">
          {lines.length} lines · {file.authored ? "written by the forge" : "copied unchanged"}
        </span>
      </div>
      <div className="overflow-x-auto py-2.5">
        <div className="min-w-[440px]">
          {lines.map((line, i) => (
            <div key={`${i}-${line}`} className="flex items-baseline">
              <span className="font-data text-[9.5px] text-ink-3 flex-[0_0_30px] text-right pr-[9px]">
                {i + 1}
              </span>
              <span
                aria-hidden="true"
                className="flex-[0_0_3px] self-stretch min-h-[18px]"
                style={{ background: tone.tone }}
              />
              <span
                className="font-data text-[9px] flex-[0_0_20px] text-center"
                style={{ color: tone.tone }}
              >
                {tone.letter}
              </span>
              <span className="font-data text-[11px] whitespace-pre text-ink">{line || " "}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
