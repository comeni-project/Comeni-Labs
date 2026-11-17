import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { RailSlot, useHasRail, useRailMini } from "../app/rail/RailContext";
import type { CataloguePage } from "./useCatalogue";

type ReleasesPage = components["schemas"]["ReleasesPage"];
type Vocabulary = components["schemas"]["AuthoringVocabulary"];

/** **Registry's pages, in the rail** (board "7 · Registry", #511): Tools, Vocabulary and Releases
 *  under Registry, each with its count, the open one filled. Forging is Forge's. */
export function RegistryTabs(_: { registryAt?: string }) {
  const mini = useRailMini();
  const rail = useHasRail();
  const tools = useQuery({
    queryKey: ["catalogue-count"],
    queryFn: () => get<CataloguePage>("/forge/catalogue?limit=1"),
    enabled: rail && !mini,
    staleTime: 60_000,
  });
  const vocabulary = useQuery({
    queryKey: ["authoring-vocabulary"],
    queryFn: () => get<Vocabulary>("/pipeline/authoring/vocabulary"),
    enabled: rail && !mini,
    staleTime: Infinity,
  });
  const releases = useQuery({
    queryKey: ["releases"],
    queryFn: () => get<ReleasesPage>("/forge/releases"),
    enabled: rail && !mini,
  });
  if (!rail || mini) return null;
  const all = Object.values(tools.data?.counts?.states ?? {}).reduce((a, b) => a + b, 0);
  const waiting = releases.data?.merged?.length ?? 0;
  const pages = [
    { to: "/registry", label: "Tools", end: true, count: all ? all.toLocaleString("en") : "" },
    { to: "/registry/vocabulary", label: "Vocabulary", end: false,
      count: vocabulary.data?.types ? String(Object.keys(vocabulary.data.types).length) : "" },
    { to: "/registry/releases", label: "Releases", end: false, count: waiting ? `${waiting} waiting` : "" },
  ];
  return (
    <RailSlot>
      <ul aria-label="Registry pages" className="list-none m-0 p-0 flex flex-col gap-[1px]">
        {pages.map(({ to, label, end, count }) => (
          <li key={to}>
            <NavLink to={to} end={end} aria-label={label}
                     className={({ isActive }) =>
                       `flex items-center gap-2 pl-[32px] pr-[10px] py-[5px] rounded-control text-[13px] no-underline
                        ${isActive ? "bg-now-soft text-now-ink font-semibold" : "text-ink-2 hover:text-ink hover:bg-surface-2"}`}>
              {label}
              {count && <span className="ml-auto text-[11.5px] font-medium text-ink-3">{count}</span>}
            </NavLink>
          </li>
        ))}
      </ul>
    </RailSlot>
  );
}
