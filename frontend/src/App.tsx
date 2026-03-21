import { Outlet } from "react-router-dom";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { useAvs } from "@/hooks/useApi";
import { useBrandContext } from "@/main";

const BRANDS = [
  { id: "brand-001", name: "LUMINA Demo" },
  { id: "brand-002", name: "Acme Corp" },
  { id: "brand-003", name: "TechStart Inc" },
];

export default function App() {
  const { brandId, setBrandId } = useBrandContext();
  const avs = useAvs(brandId);

  return (
    <div className="min-h-screen bg-surface">
      <Sidebar />
      <div className="ml-[240px] min-h-screen flex flex-col transition-all duration-300">
        <Header
          currentBrandId={brandId}
          brands={BRANDS}
          onBrandChange={setBrandId}
          avsScore={avs.data?.overall_score ?? null}
          notificationCount={3}
        />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
