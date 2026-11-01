import { useMemo, useRef, useState } from "react";

import { suggest, type Pick } from "./suggest";
import type { CataloguePage, ModuleRow } from "./useCatalogue";
import { useFilters } from "./useCatalogue";

type Chip = { kind: string; value: string; drop: (next: URLSearchParams) => void };

const dropValue = (key: string, value: string) => (next: URLSearchParams) => {
  const kept = next.getAll(key).filter((v) => v !== value);
  next.delete(key);
  for (const v of kept) next.append(key, v);
};

/** One box for everything you can look for: what you type stays a search, and a suggestion
 *  becomes a chip you can remove. Arrow keys walk the suggestions; Backspace takes the last chip. */
export function SearchBar({ page, rows }: { page: CataloguePage; rows: ModuleRow[] }) {
  const filters = useFilters();
  const [text, setText] = useState(filters.q);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);

  const chips: Chip[] = [
    ...filters.reads.map((value) => ({ kind: "reads", value, drop: dropValue("reads", value) })),
    ...filters.makes.map((value) => ({ kind: "makes", value, drop: dropValue("makes", value) })),
    ...filters.topics.map((value) => ({ kind: "topic", value, drop: dropValue("topic", value) })),
    ...(filters.noTopic ? [{ kind: "topic", value: "none", drop: (n: URLSearchParams) => n.delete("no_topic") }] : []),
    ...filters.suites.map((value) => ({ kind: "suite", value, drop: dropValue("suite", value) })),
  ];
  const groups = useMemo(() => suggest(text, page.counts, page.aliases, rows),
                         [text, page.counts, page.aliases, rows]);
  const flat = groups.flatMap((g) => g.items);

  const type = (value: string) => {
    setText(value);
    setActive(-1);
    filters.set("q", value ? [value] : []);
  };
  const choose = ({ reads, makes, topic, suite, module }: Pick) => {
    filters.change((next) => {
      next.delete("q");
      const add = (key: string, value?: string) => {
        if (value && !next.getAll(key).includes(value)) next.append(key, value);
      };
      add("reads", reads);
      add("makes", makes);
      add("topic", topic);
      add("suite", suite);
      if (module) next.set("module", module);
    });
    setText("");
    setActive(-1);
    setOpen(false);
  };
  const keys = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") { event.preventDefault(); setActive(Math.min(flat.length - 1, active + 1)); }
    if (event.key === "ArrowUp") { event.preventDefault(); setActive(Math.max(-1, active - 1)); }
    if (event.key === "Enter" && flat[active]) { event.preventDefault(); choose(flat[active].pick); }
    if (event.key === "Escape") { setOpen(false); input.current?.blur(); }
    if (event.key === "Backspace" && !text && chips.length > 0) filters.change(chips[chips.length - 1].drop);
  };

  let index = -1;
  return (
    <div className="search-box">
      <div className="search-bar">
        <svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" strokeLinecap="round" className="text-ink-3 shrink-0">
          <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
        </svg>
        {chips.map((chip) => (
          <button key={`${chip.kind}:${chip.value}`} type="button" className="search-chip"
                  aria-label={`Remove ${chip.kind} ${chip.value}`} onClick={() => filters.change(chip.drop)}>
            <span><b>{chip.kind}</b> {chip.value}</span><span aria-hidden="true">×</span>
          </button>
        ))}
        <label htmlFor="catalogue-q" className="sr-only">Search modules</label>
        <input ref={input} id="catalogue-q" type="search" autoComplete="off" value={text}
               placeholder={chips.length ? "Add another filter" : "Search, or try “bam to vcf”, “fastq”, “samtools”"}
               onChange={(event) => type(event.target.value)} onKeyDown={keys}
               onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
               className="flex-[1_1_220px] min-w-[160px] bg-transparent border-0 outline-none text-ink text-[15px] py-1" />
        {(chips.length > 0 || text) && (
          <button type="button" className="link-plain" onClick={() => {
            setText("");
            filters.change((next) => ["q", "reads", "makes", "topic", "no_topic", "suite", "mentioned"]
              .forEach((key) => next.delete(key)));
          }}>Clear all</button>
        )}
      </div>
      {open && groups.length > 0 && (
        <div className="search-suggest">
          {groups.map((group) => (
            <div key={group.title} className="flex flex-col min-w-0">
              <p className="m-0 px-[10px] pt-2 pb-[3px] text-[11.5px] text-ink-3">{group.title}</p>
              {group.items.map((item) => {
                index += 1;
                return (
                  <button key={`${group.title}:${item.kind}:${item.label}`} type="button" className="search-option"
                          data-active={index === active} onMouseDown={(event) => { event.preventDefault(); choose(item.pick); }}>
                    {item.kind && <span className="search-kind">{item.kind}</span>}
                    <span className="shrink-0">{item.label}</span>
                    <span className="truncate text-[12.5px] text-ink-3">{item.sub}</span>
                    {item.n !== null && <span className="ml-auto font-data text-[12px] text-ink-3">{item.n.toLocaleString("en")}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
