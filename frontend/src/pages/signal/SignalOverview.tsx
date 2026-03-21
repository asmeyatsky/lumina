import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Globe, AlertCircle } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import PageHeader from "@/components/layout/PageHeader";
import ScoreGauge from "@/components/common/ScoreGauge";
import DataTable, { type Column } from "@/components/common/DataTable";
import Badge from "@/components/common/Badge";
import EmptyState from "@/components/common/EmptyState";
import { useDistributionCoverage, useCreatePlan } from "@/hooks/useApi";

interface SignalOverviewProps {
  brandId: string;
}

export default function SignalOverview({ brandId }: SignalOverviewProps) {
  const navigate = useNavigate();
  const coverage = useDistributionCoverage(brandId);
  const createPlan = useCreatePlan();
  const [creating, setCreating] = useState(false);

  const overallCoverage = coverage.data?.overall_coverage ?? 0;
  const surfaces = coverage.data?.surfaces ?? [];

  // Group surfaces by category for stacked bar
  const categoryData = surfaces.reduce<
    Record<string, { covered: number; gap: number }>
  >((acc, s) => {
    const cat = s.surface.split("/")[0] || "other";
    if (!acc[cat]) acc[cat] = { covered: 0, gap: 0 };
    acc[cat].covered += s.coverage_percentage;
    acc[cat].gap += 100 - s.coverage_percentage;
    return acc;
  }, {});

  const barData = Object.entries(categoryData).map(([category, data]) => ({
    category,
    covered: data.covered,
    gap: data.gap,
  }));

  // Mock plans
  const plans = [
    {
      plan_id: "plan-001",
      strategy: "balanced",
      status: "active",
      actions_count: 12,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    },
    {
      plan_id: "plan-002",
      strategy: "aggressive",
      status: "draft",
      actions_count: 8,
      created_at: new Date(Date.now() - 172800000).toISOString(),
    },
    {
      plan_id: "plan-003",
      strategy: "conservative",
      status: "completed",
      actions_count: 5,
      created_at: new Date(Date.now() - 604800000).toISOString(),
    },
  ];

  // Mock surface gaps
  const surfaceGaps = [
    { surface: "Wikipedia", priority: "high", reason: "No presence on main Wikipedia article" },
    { surface: "Wikidata", priority: "high", reason: "Missing Wikidata entity" },
    { surface: "Crunchbase", priority: "medium", reason: "Profile incomplete, missing funding data" },
    { surface: "GitHub", priority: "medium", reason: "Organization profile not claimed" },
    { surface: "Schema.org", priority: "low", reason: "JSON-LD could be improved" },
  ];

  const planColumns: Column<(typeof plans)[0]>[] = [
    {
      key: "plan_id",
      header: "Plan ID",
      render: (row) => (
        <span className="font-mono text-xs text-accent">{row.plan_id}</span>
      ),
    },
    {
      key: "strategy",
      header: "Strategy",
      render: (row) => (
        <span className="capitalize text-gray-200">{row.strategy}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <Badge
          variant={
            row.status === "active"
              ? "success"
              : row.status === "draft"
              ? "warning"
              : "neutral"
          }
          dot
        >
          {row.status}
        </Badge>
      ),
    },
    { key: "actions_count", header: "Actions" },
    {
      key: "created_at",
      header: "Created",
      render: (row) => (
        <span className="text-gray-400 text-xs">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
    },
  ];

  const handleCreatePlan = async () => {
    setCreating(true);
    try {
      const plan = await createPlan.mutateAsync({
        brand_id: brandId,
        strategy: "balanced",
      });
      navigate(`/signal/plans/${plan.plan_id}`);
    } catch {
      // handled
    } finally {
      setCreating(false);
    }
  };

  const priorityVariant = (p: string) => {
    switch (p) {
      case "high":
        return "danger" as const;
      case "medium":
        return "warning" as const;
      default:
        return "info" as const;
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="SIGNAL"
        subtitle="AI-surface distribution and coverage management"
        actions={
          <button
            onClick={handleCreatePlan}
            disabled={creating}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <Plus size={16} />
            {creating ? "Creating..." : "New Distribution Plan"}
          </button>
        }
      />

      {/* Coverage Gauge + Coverage by Category */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="glass-panel p-6 flex flex-col items-center justify-center">
          <ScoreGauge
            score={overallCoverage}
            size={160}
            label="Distribution Coverage"
            sublabel="Overall"
          />
        </div>

        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Coverage by Surface Category
          </h2>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barData} layout="vertical">
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.04)"
                  horizontal={false}
                />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `${v}%`}
                />
                <YAxis
                  type="category"
                  dataKey="category"
                  tick={{ fill: "#9ca3af", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={80}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div className="bg-card border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl text-sm">
                        <p className="text-gray-200 capitalize">
                          {payload[0].payload.category}
                        </p>
                        <p className="text-success">
                          Covered: {Number(payload[0].value).toFixed(0)}%
                        </p>
                      </div>
                    );
                  }}
                />
                <Bar
                  dataKey="covered"
                  fill="#22c55e"
                  radius={[0, 4, 4, 0]}
                  stackId="stack"
                />
                <Bar
                  dataKey="gap"
                  fill="rgba(255,255,255,0.06)"
                  radius={[0, 4, 4, 0]}
                  stackId="stack"
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[260px] text-gray-600 text-sm">
              No coverage data available yet
            </div>
          )}
        </div>
      </div>

      {/* Plans Table + Surface Gaps */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Distribution Plans */}
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Distribution Plans
          </h2>
          <DataTable
            columns={planColumns}
            data={plans}
            pageSize={5}
            onRowClick={(row) => navigate(`/signal/plans/${row.plan_id}`)}
          />
        </div>

        {/* Surface Gaps */}
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Surface Gaps
          </h2>
          <div className="space-y-3">
            {surfaceGaps.map((gap, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
              >
                <Globe size={16} className="text-gray-500 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-medium text-gray-200">
                      {gap.surface}
                    </span>
                    <Badge variant={priorityVariant(gap.priority)}>
                      {gap.priority}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500">{gap.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
