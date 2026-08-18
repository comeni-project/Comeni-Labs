/** Loading, empty and failed — three components, so no route invents its own.
 *
 * The empty state is CONTENT rather than an apology: it says what to do next.
 */
export function Loading({ what }: { what: string }) {
  return <p className="p-6 text-ink-3 text-body">Reading {what}…</p>;
}

export function Empty({ title, next }: { title: string; next?: string }) {
  return (
    <div className="p-6">
      <p className="text-body text-ink">{title}</p>
      {next && <p className="text-secondary text-ink-3 mt-1">{next}</p>}
    </div>
  );
}

export function Failed({ error }: { error: unknown }) {
  return (
    <div className="p-6">
      <p className="text-body text-fault">{String(error)}</p>
    </div>
  );
}
