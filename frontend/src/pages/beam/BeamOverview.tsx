import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, AlertTriangle, FileText } from "lucide-react";
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
import StatCard from "@/components/common/StatCard";
import Badge from "@/components/common/Badge";
import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useAuditSummary, useBulkAudit } from "@/hooks/useApi";

interface BeamOverviewProps {
  brandId: string;
}

export default function BeamOverview({ brandId }: BeamOverviewProps) {
  const navigate = useNavigate();
  const auditSummary = useAuditSummary(brandId);
  const bulkAudit = useBulkAudit();
  const [showBulkForm, setShowBulkForm] = useState(false);
  const [urlsInput, setUrlsInput] = useState("");

  const summary = auditSummary.data;
  const totalAssets = summary?.total_assets ?? 0;
  const avgScore = summary?.average_score ?? 0;
  const distribution = summary?.score_distribution ?? {
    "0-25": 0,
    "25-50": 0,
    "50-75": 0,
    "75-100": 0,
  };
  const topIssues = summary?.top_issues ?? [];
  const belowThreshold = (distribution["0-25"] ?? 0) + (distribution["25-50"] ?? 0);

  const histogramData = Object.entries(distribution).map(([range, count]) => ({
    range,
    count,
    fill:
      range === "0-25"
        ? "#ef4444"
        : range === "25-50"
        ? "#f59e0b"
        : range === "50-75"
        ? "#00d4ff"
        : "#22c55e",
  }));

  // Mock improvement opportunities
  const opportunities = [
    {
      id: "1",
      url: "https://example.com/about",
      score: 32,
      issue: "Low entity density, missing structured data",
    },
    {
      id: "2",
      url: "https://example.com/products",
      score: 41,
      issue: "Poor chunking quality, low factual density",
    },
    {
      id: "3",
      url: "https://example.com/blog/intro",
      score: 45,
      issue: "Weak answer shape, needs semantic restructuring",
    },
    {
      id: "4",
      url: "https://example.com/faq",
      score: 48,
      issue: "Low RAG survivability, too narrative-heavy",
    },
    {
      id: "5",
      url: "https://example.com/careers",
      score: 53,
      issue: "Missing authority signals",
    },
  ];

  const handleBulkAudit = async () => {
    const urls = urlsInput
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u);
    if (urls.length === 0) return;
    try {
      await bulkAudit.mutateAsync({
        brand_id: brandId,
        urls,
      });
      setShowBulkForm(false);
      setUrlsInput("");
    } catch {
      // handled
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="BEAM"
        subtitle="Content estate audit and GEO optimization"
        actions={
          <div className="flex gap-3">
            <button
              onClick={() => navigate("/beam/score")}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <FileText size={14} />
              Score Content
            </button>
            <button
              onClick={() => setShowBulkForm(!showBulkForm)}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              <Upload size={14} />
              Bulk Audit
            </button>
          </div>
        }
      />

      {/* Bulk Audit Form */}
      {showBulkForm && (
        <div className="glass-panel p-6 mb-6 animate-slide-up">
          <h2 className="text-base font-semibold text-gray-200 mb-3">
            Bulk Content Audit
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Enter URLs to audit, one per line.
          </p>
          <textarea
            value={urlsInput}
            onChange={(e) => setUrlsInput(e.target.value)}
            placeholder="https://example.com/page-1&#10;https://example.com/page-2&#10;https://example.com/page-3"
            className="input-field min-h-[120px] resize-y font-mono text-xs mb-4"
          />
          <div className="flex gap-3">
            <button
              onClick={handleBulkAudit}
              disabled={bulkAudit.isPending || !urlsInput.trim()}
              className="btn-primary text-sm disabled:opacity-40"
            >
              {bulkAudit.isPending ? "Auditing..." : "Start Audit"}
            </button>
            <button
              onClick={() => setShowBulkForm(false)}
              className="btn-ghost text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <StatCard
          icon={<FileText size={20} />}
          label="Total Assets"
          value={totalAssets}
        />
        <StatCard
          icon={<FileText size={20} />}
          label="Average GEO Score"
          value={avgScore.toFixed(1)}
        />
        <StatCard
          icon={<AlertTriangle size={20} />}
          label="Below Threshold"
          value={belowThreshold}
          className={belowThreshold > 0 ? "border-l-2 border-l-warning" : ""}
        />
      </div>

      {/* Score Distribution + Top Opportunities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Histogram */}
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            GEO Score Distribution
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={histogramData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />
              <XAxis
                dataKey="range"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#6b7280", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="bg-card border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl text-sm">
                      <p className="text-gray-200">
                        Score {payload[0].payload.range}: {payload[0].value} assets
                      </p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {histogramData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top Improvement Opportunities */}
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Top Improvement Opportunities
          </h2>
          <div className="space-y-3">
            {opportunities.map((opp) => (
              <div
                key={opp.id}
                onClick={() => navigate("/beam/score")}
                className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] cursor-pointer hover:border-white/[0.08] transition-colors"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-mono text-accent truncate max-w-[200px]">
                    {opp.url}
                  </span>
                  <Badge
                    variant={
                      opp.score < 40
                        ? "danger"
                        : opp.score < 60
                        ? "warning"
                        : "info"
                    }
                  >
                    {opp.score}
                  </Badge>
                </div>
                <p className="text-xs text-gray-500">{opp.issue}</p>
              </div>
            ))}
          </div>

          {topIssues.length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/[0.06]">
              <h3 className="text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                Common Issues
              </h3>
              <div className="flex flex-wrap gap-2">
                {topIssues.map((issue, i) => (
                  <Badge key={i} variant="warning">
                    {issue}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
