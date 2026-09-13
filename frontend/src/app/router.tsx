import { Navigate, type RouteObject } from "react-router";

import { Question } from "../forge/Question";
import { Queue } from "../forge/Queue";
import { Tools } from "../forge/Tools";
import { Home } from "../home/Home";
import { ContractRoute } from "../forge/ContractRoute";
import { Builder } from "../build/Builder";
import { LivingBuilder } from "../build/living/LivingBuilder";
import { Adaptation } from "../forge/registry/Adaptation";
import { Catalogue } from "../forge/registry/Catalogue";
import { Overview as Registry } from "../forge/registry/Overview";
import { Work } from "../forge/registry/Work";
import { Board as Runs } from "../runs/Board";
import { Run } from "../runs/Run";
import { ErrorBoundary } from "./ErrorBoundary";
import { Shell } from "./Shell";

/** The route table — spec §4.1.
 *
 * `/` is the front door as of 3B. It redirected to the queue for the whole of 3A, marked
 * temporary in writing, because a placeholder home built then would have been thrown away.
 *
 * Filters, groupings, sorts and the registry panel are QUERY PARAMS on these routes rather than
 * routes of their own, because they are views of one destination — `forge-review.md` §3. That is
 * also what makes any view linkable.
 */
/** The 3A/3D screens, kept mountable and off the application's table — Task 13.
 *
 * **`routes` no longer reaches them and their tests still do.** The plan's box says *redirect
 * the old links, delete old code in a later cleanup PR*, and those two halves pull against each
 * other: a redirect makes the components unreachable, and unreachable components with no test
 * mounting them are exactly the "commented code rots invisibly" that `make forge-rework` exists
 * to prevent.
 *
 * So the components stay compiled and stay exercised — by these routes, which nothing in the
 * app spreads in. What is gone is the *app* reaching them, which is what a redirect means.
 * `make forge-rework` lists them for the PR that deletes them.
 */
export const legacyRoutes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/forge/queue", element: <Queue /> },
      { path: "/forge/tools", element: <Tools /> },
    ],
  },
];

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/build", element: <Builder /> },
      // **The living builder, beside the one that ships** — a secondary route until Task 14's
      // walk. `/build` is untouched: a replacement mounted before it has been driven end to end
      // would send somebody from a screen that works to one that might not.
      { path: "/build/living", element: <LivingBuilder /> },
      { path: "/runs", element: <Runs /> },
      { path: "/runs/:id", element: <Run /> },
      // **The Registry section — `/forge` is its front door, not a redirect.** The three
      // screens below it are one destination with a subnav, for the same reason filters are
      // query params here: they are views of *the registry*, and three top-level tabs would
      // make them read as three workspaces.
      { path: "/forge", element: <Registry /> },
      { path: "/forge/catalogue", element: <Catalogue /> },
      { path: "/forge/work", element: <Work /> },
      // **One route owns every state of an adaptation** — §8.4. A refresh, or the candidate
      // finishing while somebody reads it, never sends the reviewer to a different page.
      { path: "/forge/adaptations/:id", element: <Adaptation /> },
      // **The 3A/3D screens redirect into the rework, as of Task 13.** They were kept
      // reachable through Tasks 10 to 12 on purpose: the plan's own box says *only after this
      // walk*, because a redirect installed before the replacement had been driven end to end
      // would have sent somebody from a screen that worked to one that did not.
      //
      // **Redirected, not deleted.** These paths are in the operator's history, in `make dev`'s
      // banner and in four journal entries. The components stay too — `Queue`, `Tools` and
      // `ContractRoute` are ~2,000 lines with their own tests, and deleting them in the change
      // that redirects away from them means the redirect and the deletion are one diff nobody
      // can review separately. The plan says *delete old code in a later cleanup PR*.
      //
      // `/forge/queue` answers *what is open* and the work queue is what answers it now;
      // `/forge/tools` answers *what exists* and that is the catalogue.
      { path: "/forge/queue", element: <Navigate to="/forge/work" replace /> },
      { path: "/forge/tools", element: <Navigate to="/forge/catalogue" replace /> },
      { path: "/forge/sources", element: <Navigate to="/forge/catalogue?status=unadapted" replace /> },
      { path: "/forge/contracts", element: <Navigate to="/forge/catalogue?status=adapted" replace /> },
      // **These two are NOT redirected**, and that is the line: a question and a contract are
      // addressed by an id in the path, and there is nowhere in the new section to send them
      // that answers about the same object. Sending them to a list would be turning a deep link
      // into a shrug. They keep their screens until the cleanup PR replaces them.
      { path: "/forge/queue/question/:subject", element: <Question /> },
      // `/*` rather than `:id`, because a contract id contains slashes —
      // `nf-core/samtools/index@1.21.0`. `useParams()["*"]` is the id.
      //
      // **Which is also why `:id/drift` cannot be a second pattern**: react-router has no
      // splat-in-the-middle, so one component owns the splat and reads the last segment.
      { path: "/forge/contracts/*", element: <ContractRoute /> },
    ],
  },
];
