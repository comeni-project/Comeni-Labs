import { useMutation } from "@tanstack/react-query";

import { post } from "../api/client";
import type { components } from "../api/schema";

export type ActionResult = components["schemas"]["ActionResult"];

const at = (key: string, name: string, action: string) =>
  `/settings/${encodeURIComponent(key)}/items/${encodeURIComponent(name)}/${action}`;

export function useAction(key: string, name: string, action: string) {
  return useMutation({ mutationFn: () => post<ActionResult>(at(key, name, action), {}) });
}

export function listModels(key: string, name: string) {
  return post<ActionResult>(at(key, name, "models"), {});
}
