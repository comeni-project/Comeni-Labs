/** How a type and its states are written: `alignment.bam::coordinate_sorted`. States are a set,
 *  so they are sorted and one set has one spelling. Display only: nothing compares these. */
export function spelledStates(states: readonly string[] | undefined): string {
  return [...(states ?? [])].sort().map((state) => `::${state}`).join("");
}

export function spelled(type_id: string, states: readonly string[] | undefined): string {
  return type_id + spelledStates(states);
}
