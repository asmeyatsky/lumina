import { StrictMode, createContext, useContext, useState, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";

// Lazy imports for pages
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

// =============================================================================
// Brand Context
// =============================================================================

interface BrandContextValue {
  brandId: string;
  setBrandId: (id: string) => void;
}

const BrandContext = createContext<BrandContextValue>({
  brandId: "brand-001",
  setBrandId: () => {},
});

export function useBrandContext() {
  return useContext(BrandContext);
}

// =============================================================================
// Query Client
// =============================================================================

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// =============================================================================
// Router-aware wrapper that passes brandId
// =============================================================================

function BrandRouter({ brandId }: { brandId: string }) {
  const router = useMemo(
    () =>
      createBrowserRouter([
        {
          path: "/",
          element: <App />,
          children: [
            { index: true, element: <Dashboard brandId={brandId} /> },
            {
              path: "pulse",
              children: [
                { index: true, element: <PulseOverview brandId={brandId} /> },
                { path: "batteries", element: <PromptBatteries brandId={brandId} /> },
                { path: "runs/:runId", element: <RunDetail brandId={brandId} /> },
              ],
            },
            {
              path: "graph",
              children: [
                { index: true, element: <GraphOverview brandId={brandId} /> },
                { path: "profile", element: <EntityProfilePage brandId={brandId} /> },
              ],
            },
            {
              path: "beam",
              children: [
                { index: true, element: <BeamOverview brandId={brandId} /> },
                { path: "score", element: <ContentScorePage brandId={brandId} /> },
              ],
            },
            {
              path: "signal",
              children: [
                { index: true, element: <SignalOverview brandId={brandId} /> },
                { path: "plans/:planId", element: <DistributionPlanPage brandId={brandId} /> },
              ],
            },
            { path: "intelligence", element: <IntelligenceOverview brandId={brandId} /> },
            { path: "settings", element: <Settings /> },
          ],
        },
      ]),
    [brandId]
  );

  return <RouterProvider router={router} />;
}

// =============================================================================
// Root
// =============================================================================

function Root() {
  const [brandId, setBrandId] = useState(
    () => localStorage.getItem("lumina_brand_id") || "brand-001"
  );

  const handleBrandChange = (id: string) => {
    setBrandId(id);
    localStorage.setItem("lumina_brand_id", id);
  };

  return (
    <BrandContext.Provider value={{ brandId, setBrandId: handleBrandChange }}>
      <QueryClientProvider client={queryClient}>
        <BrandRouter brandId={brandId} />
      </QueryClientProvider>
    </BrandContext.Provider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>
);
