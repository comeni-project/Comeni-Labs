import { Navigate, type RouteObject } from "react-router";

import { Question } from "../forge/Question";
import { Contracts } from "../forge/Contracts";
import { ContractRoute } from "../forge/ContractRoute";
import { Queue } from "../forge/Queue";
import { Sources } from "../forge/Sources";
import { ErrorBoundary } from "./ErrorBoundary";
import { Shell } from "./Shell";

/** The route table — spec §4.1.
 *
 * `/` redirects for the whole of 3A: the landing page is 3B, and a placeholder home built now
 * would be thrown away. Filters, groupings, sorts and the registry panel are QUERY PARAMS on
 * these routes rather than routes of their own, because they are views of one destination —
 * `forge-review.md` §3. That is also what makes any view linkable.
 */
export const routes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/", element: <Navigate to="/forge/queue" replace /> },
      { path: "/forge/queue", element: <Queue /> },
      { path: "/forge/queue/question/:subject", element: <Question /> },
      { path: "/forge/contracts", element: <Contracts /> },
      { path: "/forge/sources", element: <Sources /> },
      // `/*` rather than `:id`, because a contract id contains slashes —
      // `nf-core/samtools/index@1.21.0`. `useParams()["*"]` is the id.
      //
      // **Which is also why `:id/drift` cannot be a second pattern**: react-router has no
      // splat-in-the-middle, so one component owns the splat and reads the last segment.
      { path: "/forge/contracts/*", element: <ContractRoute /> },
    ],
  },
];
