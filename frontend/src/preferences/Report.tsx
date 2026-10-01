/** A value the server reports (spec §6, §7). A list of records is a table, with the records'
 *  own keys as headers; anything else is text. Knows no particular report. */
export function Report({ value }: { value: unknown }) {
  if (Array.isArray(value) && value.length && value.every((r) => r && typeof r === "object")) {
    const rows = value as Record<string, unknown>[];
    const columns = Object.keys(rows[0]);
    return (
      <table className="text-secondary border-collapse">
        <thead>
          <tr>{columns.map((c) => <th key={c} className="text-left text-ink-3 pr-4 font-normal">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>{columns.map((c) => <td key={c} className="pr-4 text-ink">{String(row[c] ?? "—")}</td>)}</tr>
          ))}
        </tbody>
      </table>
    );
  }
  return <span className="font-data text-secondary text-ink-2">{value == null ? "—" : String(value)}</span>;
}
