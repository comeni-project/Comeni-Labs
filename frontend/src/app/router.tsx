import { Navigate, type RouteObject } from "react-router";

import { Question } from "../forge/Question";
import { Queue } from "../forge/Queue";
import { Tools } from "../forge/Tools";
import { Home } from "../home/Home";
import { ContractRoute } from "../forge/ContractRoute";
import { LivingBuilder } from "../build/living/LivingBuilder";
import { Adaptation } from "../forge/registry/Adaptation";
import { Catalogue } from "../forge/registry/Catalogue";
import { Overview as Registry } from "../forge/registry/Overview";
import { Work } from "../forge/registry/Work";
import { Board as Runs } from "../runs/Board";
import { Run } from "../runs/Run";
import { BuildRoute } from "./BuildRoute";
import { ErrorBoundary } from "./ErrorBoundary";
import { SettingsLink } from "./SettingsLink";
import { Shell } from "./Shell";

/** Retained screens mounted by tests; the application uses routes below. */
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

/** Application destinations, compatibility redirects and retained object-specific deep links.
 * Filters and settings overlays use query parameters so views remain linkable. */
export const routes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/build", element: <BuildRoute /> },

      // The conversational builder is also reachable through this explicit route.
      { path: "/build/living", element: <LivingBuilder /> },
      { path: "/runs", element: <Runs /> },
      { path: "/runs/:id", element: <Run /> },

      // Preserve older settings URLs by opening the settings overlay.
      { path: "/settings/:section?", element: <SettingsLink /> },

      { path: "/forge", element: <Registry /> },
      { path: "/forge/catalogue", element: <Catalogue /> },
      { path: "/forge/work", element: <Work /> },

      { path: "/forge/adaptations/:id", element: <Adaptation /> },

      // Preserve list bookmarks by directing them to the current registry views.
      { path: "/forge/queue", element: <Navigate to="/forge/work" replace /> },
      { path: "/forge/tools", element: <Navigate to="/forge/catalogue" replace /> },
      { path: "/forge/sources", element: <Navigate to="/forge/catalogue?status=unadapted" replace /> },
      { path: "/forge/contracts", element: <Navigate to="/forge/catalogue?status=adapted" replace /> },

      // Object-specific links retain their screens; a list redirect would lose the addressed object.
      { path: "/forge/queue/question/:subject", element: <Question /> },

      // Contract IDs contain slashes. The component owns the trailing splat, including drift views.
      { path: "/forge/contracts/*", element: <ContractRoute /> },
    ],
  },
];
