import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Monitor } from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import PageHeader from "@/components/layout/PageHeader";
import StatCard from "@/components/common/StatCard";
import TrendChart from "@/components/common/TrendChart";
import DataTable, { type Column } from "@/components/common/DataTable";
import Badge from "@/components/common/Badge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import EmptyState from "@/components/common/EmptyState";
import {
  useCitationTrends,
  useShareOfVoice,
  useRunMonitoring,
} from "@/hooks/useApi";

interface PulseOverviewProps {
  brandId: string;
}

const ENGINE_COLORS: Record<string, string> = {
  claude: "#00d4ff",
  "gpt-4o": "#22c55e",
  gemini: "#f59e0b",
  perplexity: "#a855f7",
};

const ENGINE_NAMES: Record<string, string> = {
  claude: "Claude",
  "gpt-4o": "GPT-4o",
  gemini: "Gemini",
  perplexity: "Perplexity",
};

export default function PulseOverview({ brandId }: PulseOverviewProps) {
  const navigate = useNavigate();
  const citationTrends = useCitationTrends(brandId);
  const shareOfVoice = useShareOfVoice(brandId);
  const runMonitoring = useRunMonitoring();
  const [isTriggering, setIsTriggering] = useState(false);

  const handleTriggerRun = async () => {
    setIsTriggering(true);
    try {
      const result = await runMonitoring.mutateAsync({
        brand_id: brandId,
        engines: ["claude", "gpt-4o", "gemini", "perplexity"],
      });
      navigate(`/pulse/runs/${result.run_id}`);
    } catch {
      // Error handled by React Query
    } finally {
      setIsTriggering(false);
    }
  };

  // Group citation trend data by timestamp for multi-series chart
  const trendByTimestamp = new Map<string, Record<string, number>>();
  citationTrends.data?.data_points.forEach((p) => {
    const key = p.timestamp;
    if (!trendByTimestamp.has(key)) {
      trendByTimestamp.set(key, { timestamp: 0 } as unknown as Record<string, number>);
    }
    const entry = trendByTimestamp.get(key)!;
    (entry as Record<string, unknown>).timestamp = p.timestamp;
    entry[p.engine] = p.citation_rate;
  });
  const trendData = Array.from(trendByTimestamp.values());

  const sovData =
    shareOfVoice.data?.entries.map((e) => ({
      name: e.entity,
      value: e.share,
      count: e.citation_count,
    })) ?? [];

  const SOV_COLORS = ["#00d4ff", "#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#6366f1"];

  // Mock recent runs data
  const recentRuns = [
    {
      run_id: "run-001",
      status: "completed",
      engines: "claude, gpt-4o, gemini, perplexity",
      created_at: new Date(Date.now() - 86400000).toISOString(),
      results_count: 124,
    },
    {
      run_id: "run-002",
      status: "completed",
      engines: "claude, gpt-4o",
      created_at: new Date(Date.now() - 172800000).toISOString(),
      results_count: 67,
    },
    {
      run_id: "run-003",
      status: "running",
      engines: "claude, gpt-4o, gemini, perplexity",
      created_at: new Date(Date.now() - 3600000).toISOString(),
      results_count: 0,
    },
  ];

  const columns: Column<(typeof recentRuns)[0]>[] = [
    {
      key: "run_id",
      header: "Run ID",
      render: (row) => (
        <span className="font-mono text-xs text-accent">{row.run_id}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <Badge
          variant={
            row.status === "completed"
              ? "success"
              : row.status === "running"
              ? "info"
              : "warning"
          }
          dot
        >
          {row.status}
        </Badge>
      ),
    },
    { key: "engines", header: "Engines" },
    {
      key: "created_at",
      header: "Started",
      render: (row) => (
        <span className="text-gray-400">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
    },
    { key: "results_count", header: "Results" },
  ];

  const engines = ["claude", "gpt-4o", "gemini", "perplexity"];

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="PULSE"
        subtitle="Citation monitoring across AI engines"
        actions={
          <button
            onClick={handleTriggerRun}
            disabled={isTriggering}
            className="btn-primary flex items-center gap-2"
          >
            <Play size={16} />
            {isTriggering ? "Starting..." : "New Monitoring Run"}
          </button>
        }
      />

      {/* Engine Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {engines.map((engine) => (
          <StatCard
            key={engine}
            icon={<Monitor size={20} />}
            label={ENGINE_NAMES[engine] || engine}
            value="--"
            className="border-l-2"
            // Dynamic border color based on engine
          />
        ))}
      </div>

      {/* Share of Voice + Citation Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Share of Voice Donut */}
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Share of Voice
          </h2>
          {sovData.length > 0 ? (
            <div className="flex flex-col items-center">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={sovData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {sovData.map((_, i) => (
                      <Cell key={i} fill={SOV_COLORS[i % SOV_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-card border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl text-sm">
                          <p className="text-gray-200 font-medium">{d.name}</p>
                          <p className="text-gray-400">
                            {d.value.toFixed(1)}% ({d.count} citations)
                          </p>
                        </div>
                      );
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-3 justify-center mt-2">
                {sovData.map((entry, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-xs">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: SOV_COLORS[i % SOV_COLORS.length] }}
                    />
                    <span className="text-gray-400">{entry.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState
              title="No share of voice data"
              description="Run a monitoring cycle to see share of voice analysis"
            />
          )}
        </div>

        {/* Citation Trend */}
        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Citation Frequency Trend
          </h2>
          {trendData.length > 0 ? (
            <TrendChart
              data={trendData}
              series={engines.map((e) => ({
                dataKey: e,
                name: ENGINE_NAMES[e] || e,
                color: ENGINE_COLORS[e] || "#888",
              }))}
              yAxisDomain={[0, "auto"]}
              height={260}
            />
          ) : (
            <div className="flex items-center justify-center h-[260px] text-gray-600 text-sm">
              No citation data available yet. Run a monitoring cycle to begin tracking.
            </div>
          )}
        </div>
      </div>

      {/* Recent Runs Table */}
      <div className="glass-panel p-6">
        <h2 className="text-base font-semibold text-gray-200 mb-4">
          Recent Monitoring Runs
        </h2>
        <DataTable
          columns={columns}
          data={recentRuns}
          searchable
          searchPlaceholder="Search runs..."
          onRowClick={(row) => navigate(`/pulse/runs/${row.run_id}`)}
          pageSize={5}
        />
      </div>
    </div>
  );
}
