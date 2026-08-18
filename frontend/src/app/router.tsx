import { Navigate, type RouteObject } from "react-router";

import { Question } from "../forge/Question";
import { Queue } from "../forge/Queue";
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
    ],
  },
];
