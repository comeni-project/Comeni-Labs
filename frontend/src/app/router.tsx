import { Navigate, type RouteObject } from "react-router";

import { BuildPage } from "../analysis/build/BuildPage";
import { DataPage } from "../analysis/data/DataPage";
import { RunPage } from "../analysis/run/RunPage";
import { Home } from "../home/Home";
import { Catalogue } from "../registry/Catalogue";
import { Adaptation } from "../registry/forging/Adaptation";
import { ForgingList } from "../registry/forging/ForgingList";
import { LearnedRules } from "../registry/LearnedRules";
import { Releases } from "../registry/Releases";
import { VocabularyPage } from "../registry/Vocabulary";
import { Tool } from "../registry/Tool";
import { Loading } from "../ui/States";
import {
  AnalysisFrame, AnalysisIndex, LegacyBuild, LegacyRun,
} from "./AnalysisFrame";
import { ErrorBoundary } from "./ErrorBoundary";
import { SettingsLink } from "./SettingsLink";
import { Shell } from "./Shell";

/** Application destinations (#511). An analysis is a pipeline draft, at `/a/<draft>/…`.
 * Filters and settings overlays use query parameters so views remain linkable. */
export const routes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: "/", element: <Home /> },
      {
        path: "/a/:draft",
        element: <AnalysisFrame />,
        children: [
          { index: true, element: <AnalysisIndex /> },
          { path: "data/:sub?", element: <DataPage /> },
          { path: "build", element: <BuildPage /> },
          { path: "run", element: <RunPage /> },
          { path: "run/:id/:sub?", element: <RunPage /> },
        ],
      },

      // Older addresses, sent to their analysis.
      { path: "/build", element: <LegacyBuild /> },
      { path: "/runs", element: <Navigate to="/" replace /> },
      { path: "/runs/:id", element: <LegacyRun fallback={<Loading what="the run" />} /> },

      { path: "/registry", element: <Catalogue /> },
      // The splat is the contract id, which carries `/` and `@` (`nf-core/star/align@2.7.11b`).
      { path: "/registry/tools/*", element: <Tool /> },
      { path: "/registry/forging", element: <ForgingList /> },
      { path: "/registry/forging/:id", element: <Adaptation /> },
      { path: "/registry/releases", element: <Releases /> },
      { path: "/registry/vocabulary", element: <VocabularyPage /> },
      { path: "/registry/learned", element: <LearnedRules /> },

      // Preserve older settings URLs by opening the settings overlay.
      { path: "/settings/:section?", element: <SettingsLink /> },
    ],
  },
];
