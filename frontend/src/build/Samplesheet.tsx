/** A samplesheet, composed row by row. Plan 5B §5.3.
 *
 * ═══ WHY THIS EXISTS AND A PATH BOX DOES NOT ══════════════════════════════════════════════
 *
 * **`params.input` is one null whether it is a glob or a CSV path.** Two same-type channels
 * work with no help at all — `params.gtf` and `params.gtf_2` are two nulls and the form asks for
 * two files — but a samplesheet is one null that means something else, so without the artifact
 * saying `input_form: samplesheet` the form asks the same question either way. Somebody answers
 * with a fastq glob, the run fails inside Nextflow minutes later, and the one place that could
 * have said so is the form that asked.
 *
 * ═══ MENDEL NEVER SEES ANY OF THIS ════════════════════════════════════════════════════════
 *
 * Invariant 15: Mendel emits a pipeline that *references* `params.input` and never receives one.
 * These rows go to **Wiener**, which writes them as a CSV into the run's workdir — transient,
 * deleted with the run, and never a table (`docs/design/wiener.md` §7.1).
 *
 * ═══ A PATH IS STILL ACCEPTED ═════════════════════════════════════════════════════════════
 *
 * A laboratory that already has a samplesheet gives its path, and Wiener passes a string through
 * untouched. This editor is a convenience over that, not a gate in front of it — which is why
 * the toggle is here rather than a decision the page makes for somebody.
 */

export type Row = Record<string, string>;

/** The identifier every row carries. **Not one of the artifact's columns** — those are the
 *  *file* columns each sample supplies, and this is what ties them together. */
export const SAMPLE = "sample";

export function Samplesheet({ columns, rows, onChange }: {
  columns: string[];
  rows: Row[];
  onChange: (rows: Row[]) => void;
}) {
  const headers = [SAMPLE, ...columns];

  const set = (index: number, column: string, value: string) =>
    onChange(rows.map((row, n) => (n === index ? { ...row, [column]: value } : row)));

  return (
    <div className="flex flex-col gap-2" data-testid="samplesheet">
      <p className="text-secondary text-ink-3">
        One row per sample. The columns are this pipeline's per-sample inputs, and a row is
        what ties a sample's reads to <b className="font-normal text-ink-2">its own</b> annotation
        — which two separate globs cannot do.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {headers.map((column) => (
                <th
                  key={column}
                  className="text-left font-data text-label uppercase tracking-[.13em]
                             text-ink-3 pb-1 pr-3 font-normal"
                >
                  {column}
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} data-testid="samplesheet-row">
                {headers.map((column) => (
                  <td key={column} className="pr-3 pb-1">
                    <input
                      aria-label={`${column} for row ${index + 1}`}
                      value={row[column] ?? ""}
                      onChange={(event) => set(index, column, event.target.value)}
                      placeholder={column === SAMPLE ? "a name you choose" : "a path"}
                      className="w-full px-2 py-1 bg-surface border border-line rounded-r
                                 font-data text-body text-ink"
                    />
                  </td>
                ))}
                <td className="pb-1">
                  {/* Removing the last row would leave a table with a header and nothing to
                      fill, which reads as broken rather than as empty. */}
                  <button
                    type="button"
                    data-testid="drop-row"
                    disabled={rows.length === 1}
                    onClick={() => onChange(rows.filter((_, n) => n !== index))}
                    className="px-2 py-1 text-label text-ink-3 bg-transparent border-0
                               cursor-pointer disabled:opacity-40"
                    title={rows.length === 1 ? "a samplesheet needs at least one row" : "remove"}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        data-testid="add-row"
        onClick={() => onChange([...rows, Object.fromEntries(headers.map((c) => [c, ""]))])}
        className="self-start px-3 py-1 border border-line-2 bg-transparent text-body
                   text-ink-2 cursor-pointer lift"
      >
        + sample
      </button>
    </div>
  );
}

/** Which rows are not yet usable — **named, not counted.**
 *
 * A count tells somebody there is a problem; a name tells them where. Same argument
 * `useSubmit.unfilled` makes about the start button: a refusal a disabled control could have
 * explained is a round trip a person had to make to learn what the page already knew.
 */
export function incomplete(rows: Row[], columns: string[]): string[] {
  return rows.flatMap((row, index) => {
    const missing = [SAMPLE, ...columns].filter((column) => !(row[column] ?? "").trim());
    return missing.length ? [`row ${index + 1}: ${missing.join(", ")}`] : [];
  });
}
