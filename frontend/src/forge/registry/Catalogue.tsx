import { useEffect, useState } from "react";
import { Link } from "react-router";

import {
  PER_PAGE,
  useCatalogue,
  useCatalogueItem,
  useStartAdaptation,
  type CatalogueItem,
  type CatalogueRow,
} from "../../api/registry";
import { useTitle } from "../../app/useTitle";
import { useUrlPatch, useUrlState } from "../../app/useUrlState";
import { Failed, Loading } from "../../ui/States";
import { LOOK, Mark, RegistrySection } from "./Status";

/** `/forge/catalogue` — every tool a source can read, and what we have done about each.
 *
 * **Search, filter and paging are all the server's.** Sixteen hundred rows is well past the
 * point where sending all of them to filter three is defensible, and a page that filtered
 * what it had already fetched would report *11 of 1,612* — the total describing the whole
 * catalogue and the rows describing one page of it.
 *
 * **Every control is a query parameter.** A curator who has found the four outdated pegi3s
 * tools can paste the URL; a filter held in `useState` is a view nobody else can be sent to.
 */

/** The status filters, in the order a tool passes through them.
 *
 * `adapted` sits at the end rather than beside `current` because it is the union of two of the
 * others — a person picking it means *the ones we have done*, and putting it mid-sequence would
 * read as a sixth exclusive state.
 */
const STATUSES: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "unadapted", label: "Not adapted" },
  { value: "in_progress", label: "In progress" },
  { value: "current", label: "Current" },
  { value: "outdated", label: "Outdated" },
  { value: "unsupported", label: "Unsupported" },
  { value: "adapted", label: "Adapted" },
];

/** How a freshness draws in a row: a shape, a word, and never colour alone. */
const FRESHNESS: Record<string, { shape: "done" | "open" | "review" | "run" | "fail"; label: string }> = {
  current: { shape: "done", label: "current" },
  outdated: { shape: "review", label: "outdated" },
  in_progress: { shape: "run", label: "in progress" },
  unadapted: { shape: "open", label: "not adapted" },
  unsupported: { shape: "fail", label: "unsupported" },
};

function Chip({ on, children, onClick }: { on: boolean; children: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`font-data text-label tracking-[.08em] uppercase px-3 py-1.5 border
                  rounded-[var(--r)] ${
                    on
                      ? "bg-surface-2 text-ink border-line-2"
                      : "bg-transparent text-ink-3 border-line hover:text-ink"
                  }`}
    >
      {children}
    </button>
  );
}

/** The row's own action, which is the whole point of the column.
 *
 * **Three outcomes, and each is a different verb.** A tool with no adaptation is started here;
 * one already moving is opened, never started again — `begin` refuses a second active
 * adaptation and a button that produced a refusal would be teaching the person that the page
 * is broken. An unsupported tool has no action at all, and says why instead.
 */
function Action({ row }: { row: CatalogueRow }) {
  const start = useStartAdaptation();
  const where = row.standing;

  if (!row.item.adaptable) {
    return (
      <span className="font-data text-label text-ink-3" title={row.item.unsupported_reason ?? ""}>
        no action
      </span>
    );
  }
  if (where.adaptation_id) {
    return (
      <Link
        to={`/forge/adaptations/${where.adaptation_id}`}
        className="font-data text-label tracking-[.08em] uppercase no-underline text-link
                   border border-line-2 rounded-[var(--r)] px-[11px] py-[5px] hover:bg-surface"
      >
        Open
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={() => start.mutate(row.item.id)}
      disabled={start.isPending}
      className="font-data text-label tracking-[.08em] uppercase border border-line-2
                 rounded-[var(--r)] px-[11px] py-[5px] bg-transparent text-ink
                 hover:bg-surface disabled:text-ink-3 disabled:cursor-not-allowed"
    >
      {start.isPending ? "Starting…" : "Adapt"}
    </button>
  );
}

/** The inspector — one tool in full, beside the table rather than instead of it.
 *
 * **It fetches by id rather than reading the selected row.** A URL carrying `?tool=` may be
 * opened on a page the tool is not on — a different filter, a different offset, a colleague's
 * link — and an inspector that could only describe a visible row would render nothing there.
 */
function Inspector({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, isPending, error } = useCatalogueItem(id);
  const start = useStartAdaptation();

  return (
    <aside className="settle border border-line bg-surface rounded-[var(--r)] shadow-e2 px-5 py-[18px]">
      {isPending && <Loading what="this tool" />}
      {error && <Failed error={error} padded={false} />}
      {data && <Detail item={data} onStart={() => start.mutate(data.id)} busy={start.isPending} />}
      {start.error && (
        <div className="pt-3">
          <Failed error={start.error} padded={false} />
        </div>
      )}
      <button
        type="button"
        onClick={onClose}
        className="font-data text-label tracking-[.08em] uppercase text-ink-3 hover:text-ink
                   bg-transparent border-0 px-0 pt-4 cursor-pointer"
      >
        Close
      </button>
    </aside>
  );
}

function Detail({
  item,
  onStart,
  busy,
}: {
  item: CatalogueItem;
  onStart: () => void;
  busy: boolean;
}) {
  return (
    <>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-object font-semibold">{item.display_name || item.ref}</span>
        <span className="font-data text-[10.5px] text-ink-3">{item.source}</span>
      </div>
      {item.summary && <p className="text-body text-ink-2 m-0 pt-[9px] pb-4">{item.summary}</p>}

      {/* **The container is quoted, digest and all.** A tag is a moving target and a digest is
          the thing a reproducible build pins, so showing the tag alone would be showing the
          half that can change under a landed contract. */}
      {item.container_refs.length > 0 && (
        <Section label="Container">
          {item.container_refs.map((ref) => (
            <div
              key={`${ref.registry}/${ref.repository}`}
              className="font-data text-[10.5px] text-ink-2 break-all"
            >
              {ref.registry}/{ref.repository}
              {ref.digest ? `@${ref.digest}` : ref.tag ? `:${ref.tag}` : ""}
              <span className="text-ink-3">
                {ref.platform ? ` · ${ref.platform}` : ""}
                {ref.digest ? " · pinned by digest" : " · tag only, not pinned"}
              </span>
            </div>
          ))}
        </Section>
      )}

      {(item.input_hints.length > 0 || item.output_hints.length > 0) && (
        <Section label="What the source says goes in and out">
          {/* **Hints, and the word is load-bearing** — a filename pattern is evidence and a
              channel name is not a semantic type. Naming them ports here would be asserting
              exactly what the scaffold's holes exist to ask a person about. */}
          <div className="text-body text-ink-2">
            {item.input_hints.join(", ") || "—"} → {item.output_hints.join(", ") || "—"}
          </div>
        </Section>
      )}

      {item.classifications.length > 0 && (
        <Section label="Categories">
          <div className="text-body text-ink-2">
            {item.classifications.map((c) => c.name || c.id).join(" · ")}
          </div>
        </Section>
      )}

      <Section label="Licence &amp; maintainers">
        <div className="text-body text-ink-2">
          {[item.licence.join(", "), item.maintainers.join(", ")].filter(Boolean).join(" · ") ||
            "not stated"}
        </div>
      </Section>

      {item.latest_version && (
        <Section label="Latest version">
          <div className="font-data text-[11px] text-ink-2">{item.latest_version}</div>
        </Section>
      )}

      {item.adaptable ? (
        <button
          type="button"
          onClick={onStart}
          disabled={busy}
          className="w-full mt-1 border border-pea text-pea bg-transparent text-[12px]
                     rounded-[var(--r)] px-3.5 py-[7px] hover:bg-pea-soft
                     disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {busy ? "Starting…" : "Adapt this tool"}
        </button>
      ) : (
        /* An unsupported tool stays visible and says what is missing — §7. Hiding it would
           make the catalogue's total disagree with what a person can see. */
        <p className="text-body text-measured m-0">{item.unsupported_reason}</p>
      )}
    </>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="pb-4">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-2">
        {label}
      </div>
      {children}
    </div>
  );
}

export function Catalogue() {
  useTitle("Catalogue");

  const [q] = useUrlState("q", "");
  const [source] = useUrlState("source", "");
  const [status] = useUrlState("status", "");
  const [page] = useUrlState("page", "1");
  const [selected, setSelected] = useUrlState("tool", "");

  // **Every filter change also resets the page, so it is ONE write.** Two `useUrlState`
  // setters called from one handler each build their copy from the same render's params, and
  // the second overwrites the first — the filter would apply and then be undone by the page
  // reset in the same click. `useUrlPatch` carries the argument.
  const patch = useUrlPatch();

  // **The box is local and the URL is debounced.** Typing writes a history entry per keystroke
  // otherwise, and `useUrlState` replaces rather than pushes precisely so the back button still
  // works — but a request per character is a request per character regardless.
  const [typed, setTyped] = useState(q);
  useEffect(() => setTyped(q), [q]);
  useEffect(() => {
    if (typed === q) return;
    const timer = setTimeout(() => patch({ q: typed, page: "" }), 250);
    return () => clearTimeout(timer);
  }, [typed, q, patch]);

  const offset = (Math.max(1, Number(page) || 1) - 1) * PER_PAGE;
  const { data, isPending, error, isPlaceholderData } = useCatalogue({
    q,
    source,
    status,
    adaptableOnly: false,
    offset,
  });

  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;
  const last = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <RegistrySection>
      <div className="gutter pb-10 overflow-y-auto">
        <div className="settle flex items-center gap-3.5 pt-[26px] pb-4">
          <input
            type="search"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Search name, description or keyword"
            aria-label="Search the catalogue"
            className="flex-1 border border-line-2 bg-surface text-ink text-body
                       rounded-[var(--r)] px-3.5 py-[9px] placeholder:text-ink-3
                       focus-visible:outline-none focus-visible:shadow-[var(--ring)]"
          />
          <span className="font-data text-[11px] text-ink-3 tnum">
            {total.toLocaleString()} tools
          </span>
        </div>

        <div className="flex flex-wrap gap-[9px] pb-5">
          {STATUSES.map((choice) => (
            <Chip
              key={choice.value || "all"}
              on={status === choice.value}
              onClick={() => patch({ status: choice.value, page: "" })}
            >
              {choice.label}
            </Chip>
          ))}
          {/* The source filter is a chip pair rather than a select, because there are two of
              them. It becomes a select when a third source lands, not before. */}
          {["nf-core", "pegi3s"].map((name) => (
            <Chip
              key={name}
              on={source === name}
              onClick={() => patch({ source: source === name ? "" : name, page: "" })}
            >
              {name}
            </Chip>
          ))}
        </div>

        {isPending && <Loading what="the catalogue" />}
        {error && <Failed error={error} />}

        {data && (
          <div
            className={
              selected
                ? "grid gap-[26px] items-start grid-cols-1 min-[1180px]:grid-cols-[minmax(0,1fr)_372px]"
                : ""
            }
          >
            <div>
              {rows.length === 0 ? (
                /* **An empty result says which filter emptied it.** "No tools" on a page with
                   four controls set is an answer nobody can act on. */
                <div className="border border-line bg-surface rounded-[var(--r)] p-6">
                  <p className="text-body text-ink m-0">Nothing matches.</p>
                  <p className="text-secondary text-ink-3 m-0 pt-1">
                    {[q && `search “${q}”`, source && `source ${source}`, status && `status ${status}`]
                      .filter(Boolean)
                      .join(", ") || "No source has been synced yet."}
                  </p>
                </div>
              ) : (
                <div className="tbl" style={{ opacity: isPlaceholderData ? 0.6 : 1 }}>
                  <table className="w-full border-collapse">
                    <thead>
                      <tr>
                        {["status", "tool / source", "what it does", "latest", "", ""].map(
                          (head, i) => (
                            <th
                              key={head || i}
                              className="font-data text-[9.5px] tracking-[.15em] uppercase
                                         text-ink-3 text-left font-normal pb-[9px]
                                         border-b border-line"
                            >
                              {head}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const look = FRESHNESS[row.standing.freshness] ?? FRESHNESS.unadapted;
                        const state = row.standing.adaptation_state;
                        return (
                          <tr
                            key={row.item.id}
                            onClick={() => setSelected(row.item.id)}
                            className={`lift cursor-pointer ${
                              selected === row.item.id ? "bg-surface" : ""
                            }`}
                          >
                            <td className="w-[112px] py-[11px] border-b border-line-soft align-top">
                              <span className="flex items-center gap-[7px]">
                                <Mark shape={look.shape} />
                                <span className="font-data text-label text-ink-3">
                                  {/* An in-progress tool says which stage it is at, because
                                      *in progress* covers five states and the reviewer's
                                      question is which one. */}
                                  {state ? LOOK[state].label : look.label}
                                </span>
                              </span>
                            </td>
                            <td className="w-[210px] py-[11px] border-b border-line-soft align-top">
                              <div className="text-body font-medium">
                                {row.item.display_name || row.item.ref}
                              </div>
                              <div className="font-data text-[10.5px] text-ink-3 pt-[3px]">
                                {row.item.source} · {row.item.ref}
                              </div>
                            </td>
                            <td
                              className="py-[11px] pr-6 border-b border-line-soft align-top
                                         text-body text-ink-2"
                            >
                              {row.item.summary || "—"}
                            </td>
                            <td
                              className="w-[132px] py-[11px] border-b border-line-soft align-top
                                         font-data text-[11px] text-ink-2"
                            >
                              {/* **A dash, never a version invented from a tag.** `latest` on a
                                  container is an alias, and writing it here would turn a
                                  pointer into a claim. */}
                              {row.item.latest_version ?? "—"}
                            </td>
                            <td
                              className="w-[150px] py-[11px] border-b border-line-soft align-top
                                         font-data text-[10.5px] text-ink-3"
                            >
                              {row.item.evidence.length > 0
                                ? row.item.evidence[0].locator
                                : "no evidence"}
                            </td>
                            <td
                              className="w-[92px] py-[11px] border-b border-line-soft align-top
                                         text-right"
                              onClick={(event) => event.stopPropagation()}
                            >
                              <Action row={row} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {total > PER_PAGE && (
                <div className="flex items-center justify-between pt-4">
                  <span className="font-data text-[10.5px] text-ink-3 tnum">
                    {offset + 1}–{Math.min(offset + rows.length, total)} of{" "}
                    {total.toLocaleString()}
                  </span>
                  <span className="flex gap-2">
                    <Pager
                      to={Math.max(1, Number(page) - 1)}
                      disabled={offset === 0}
                      onGo={(next) => patch({ page: next === 1 ? "" : String(next) })}
                    >
                      ‹ Previous
                    </Pager>
                    <Pager
                      to={Math.min(last, Number(page) + 1)}
                      disabled={offset + rows.length >= total}
                      onGo={(next) => patch({ page: String(next) })}
                    >
                      Next ›
                    </Pager>
                  </span>
                </div>
              )}
            </div>

            {selected && (
              /* Closing writes the URL, so it is one state and not two: a reload, a back
                 button and a pasted link all agree about whether the panel is open. */
              <Inspector id={selected} onClose={() => setSelected("")} />
            )}
          </div>
        )}
      </div>
    </RegistrySection>
  );
}

function Pager({
  to,
  disabled,
  onGo,
  children,
}: {
  to: number;
  disabled: boolean;
  onGo: (next: number) => void;
  children: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onGo(to)}
      className="border border-line-2 bg-transparent text-ink text-[11px] rounded-[var(--r)]
                 px-3 py-[5px] hover:bg-surface disabled:text-ink-3 disabled:border-line
                 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}
