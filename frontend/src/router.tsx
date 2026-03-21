import { createBrowserRouter } from "react-router-dom";
import App from "@/App";
import Dashboard from "@/pages/Dashboard";
import PulseOverview from "@/pages/pulse/PulseOverview";
import PromptBatteries from "@/pages/pulse/PromptBatteries";
import RunDetail from "@/pages/pulse/RunDetail";
import GraphOverview from "@/pages/graph/GraphOverview";
import EntityProfilePage from "@/pages/graph/EntityProfile";
import BeamOverview from "@/pages/beam/BeamOverview";
import ContentScorePage from "@/pages/beam/ContentScore";
import SignalOverview from "@/pages/signal/SignalOverview";
import DistributionPlanPage from "@/pages/signal/DistributionPlan";
import IntelligenceOverview from "@/pages/intelligence/IntelligenceOverview";
import Settings from "@/pages/Settings";

export function createRouter(brandId: string) {
  return createBrowserRouter([
    {
      path: "/",
      element: <App />,
      children: [
        {
          index: true,
          element: <Dashboard brandId={brandId} />,
        },
        {
          path: "pulse",
          children: [
            {
              index: true,
              element: <PulseOverview brandId={brandId} />,
            },
            {
              path: "batteries",
              element: <PromptBatteries brandId={brandId} />,
            },
            {
              path: "runs/:runId",
              element: <RunDetail brandId={brandId} />,
            },
          ],
        },
        {
          path: "graph",
          children: [
            {
              index: true,
              element: <GraphOverview brandId={brandId} />,
            },
            {
              path: "profile",
              element: <EntityProfilePage brandId={brandId} />,
            },
          ],
        },
        {
          path: "beam",
          children: [
            {
              index: true,
              element: <BeamOverview brandId={brandId} />,
            },
            {
              path: "score",
              element: <ContentScorePage brandId={brandId} />,
            },
          ],
        },
        {
          path: "signal",
          children: [
            {
              index: true,
              element: <SignalOverview brandId={brandId} />,
            },
            {
              path: "plans/:planId",
              element: <DistributionPlanPage brandId={brandId} />,
            },
          ],
        },
        {
          path: "intelligence",
          element: <IntelligenceOverview brandId={brandId} />,
        },
        {
          path: "settings",
          element: <Settings />,
        },
      ],
    },
  ]);
}
