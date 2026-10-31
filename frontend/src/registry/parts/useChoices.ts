import { useQuery } from "@tanstack/react-query";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import type { PickerEntry } from "./RegistryPicker";

type Choices = components["schemas"]["Choices"];

/** The registry's choices, read when a picker first opens. */
export function useChoices(enabled: boolean) {
  return useQuery({
    queryKey: ["registry-choices"],
    queryFn: () => get<Choices>("/registry/choices"),
    enabled,
  });
}

export function typeEntries(choices: Choices): PickerEntry[] {
  return choices.types.map((t) => ({
    id: t.id, name: t.name ?? t.id, group: t.family, says: t.explain ?? t.family_says,
    before: t.made_by, after: t.read_by,
  }));
}

/** A job's only declared words are its name, so it is described by what does it. */
export function roleEntries(choices: Choices): PickerEntry[] {
  return choices.roles.map((r) => ({
    id: r.id, name: r.id.replace(/_/g, " "), group: r.id.split("_")[0],
    says: r.tools.length ? `Done by ${r.tools.join(", ")}` : "No tool does this yet.",
    before: r.reads, after: r.makes,
  }));
}
