import { useSearchParams } from "react-router";

import { Builder } from "../build/Builder";
import { LivingBuilder } from "../build/living/LivingBuilder";

/** `/build?session=<id>` restores a living session; anything else is the manual builder.
 *
 * **`?draft=<id>` stays in the manual builder**, and so does a bare `/build`. The living shell
 * addresses a *session*, and an old draft has none — opening one there would show a canvas with
 * no conversation behind it, which is the manual builder with fewer controls. Both stay mountable
 * through Task 14's walk, which is the plan's condition for cutting over.
 */
export function BuildRoute() {
  const [params] = useSearchParams();
  return params.get("session") ? <LivingBuilder /> : <Builder />;
}
