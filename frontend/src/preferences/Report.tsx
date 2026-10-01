/** A value the server reports (spec §6, §7), drawn as the overlay's design draws it.
 *
 * **A list of records is a stacked list**: each record's first field as its line, the rest on a
 * quiet line under it — *Talking with you* over *stays on this machine · Local Ollama*. Anything
 * else is text. Knows no particular report.
 */
export function Report({ value }: { value: unknown }) {
  if (Array.isArray(value) && value.length && value.every((r) => r && typeof r === "object")) {
    const rows = value as Record<string, unknown>[];
    return (
      <ul className="m-0 p-0 list-none">
        {rows.map((row, i) => {
          const [first, ...rest] = Object.values(row);
          return (
            <li key={i} className="flex flex-col gap-[4px] py-[10px] border-t border-line-soft first:border-t-0">
              <span className="text-body text-ink">{String(first ?? "—")}</span>
              <span className="text-secondary text-ink-3">
                {rest.filter((v) => v !== null && v !== "").map(String).join(" · ")}
              </span>
            </li>
          );
        })}
      </ul>
    );
  }
  if (Array.isArray(value)) {
    return <span className="font-data text-secondary text-ink-2">{value.map(String).join(" · ") || "—"}</span>;
  }
  return <span className="font-data text-secondary text-ink-2">{value == null ? "—" : String(value)}</span>;
}
