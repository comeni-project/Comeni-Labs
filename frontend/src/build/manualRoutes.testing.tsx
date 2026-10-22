import { type RouteObject } from "react-router";

import { routes } from "../app/router";
import { Builder } from "./Builder";

/** The application's routes with the manual builder still at `/build`, for its own tests until
 *  it is deleted (one builder, #395, plan 2 Task 8). */
export const manualRoutes = routes.map((route) => ({
  ...route,
  children: route.children?.map((child) =>
    child.path === "/build" ? { path: "/build", element: <Builder /> } : child),
})) as RouteObject[];
