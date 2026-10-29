import { type RouteObject } from "react-router";

import { Home } from "../home/Home";
import { Catalogue } from "../registry/Catalogue";
import { Board as Runs } from "../runs/Board";
import { Run } from "../runs/Run";
import { BuildRoute } from "./BuildRoute";
import { ErrorBoundary } from "./ErrorBoundary";
import { SettingsLink } from "./SettingsLink";
import { Shell } from "./Shell";

/** Application destinations.
 * Filters and settings overlays use query parameters so views remain linkable. */
export const routes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/build", element: <BuildRoute /> },
      { path: "/runs", element: <Runs /> },
      { path: "/runs/:id", element: <Run /> },
      { path: "/registry", element: <Catalogue /> },

      // Preserve older settings URLs by opening the settings overlay.
      { path: "/settings/:section?", element: <SettingsLink /> },
    ],
  },
];
