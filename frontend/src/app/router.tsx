import { Navigate, type RouteObject } from "react-router";

import { Question } from "../forge/Question";
import { Home } from "../home/Home";
import { ContractRoute } from "../forge/ContractRoute";
import { Builder } from "../build/Builder";
import { Queue } from "../forge/Queue";
import { Adaptation } from "../forge/registry/Adaptation";
import { Catalogue } from "../forge/registry/Catalogue";
import { Overview as Registry } from "../forge/registry/Overview";
import { Work } from "../forge/registry/Work";
import { Board as Runs } from "../runs/Board";
import { Run } from "../runs/Run";
import { Tools } from "../forge/Tools";
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
export const routes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/build", element: <Builder /> },
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
      { path: "/forge/queue", element: <Queue /> },
      { path: "/forge/queue/question/:subject", element: <Question /> },
      { path: "/forge/tools", element: <Tools /> },
      // **Redirects, not deletions.** `/forge/sources` and `/forge/contracts` are in the
      // operator's history, in `make dev`'s banner and in three journal entries. A merged
      // screen that breaks every link anybody saved is a merge that costs more than it gives.
      { path: "/forge/sources", element: <Navigate to="/forge/tools?state=undrafted" replace /> },
      { path: "/forge/contracts", element: <Navigate to="/forge/tools?state=landed" replace /> },
      // `/*` rather than `:id`, because a contract id contains slashes —
      // `nf-core/samtools/index@1.21.0`. `useParams()["*"]` is the id.
      //
      // **Which is also why `:id/drift` cannot be a second pattern**: react-router has no
      // splat-in-the-middle, so one component owns the splat and reads the last segment.
      { path: "/forge/contracts/*", element: <ContractRoute /> },
    ],
  },
];
