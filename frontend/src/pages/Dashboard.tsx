import { useNavigate } from "react-router-dom";
import { Activity, GitBranch, Zap, Radio, ArrowRight, AlertTriangle, CheckCircle, Info } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import ScoreGauge from "@/components/common/ScoreGauge";
import StatCard from "@/components/common/StatCard";
import TrendChart from "@/components/common/TrendChart";
import Badge from "@/components/common/Badge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import {
  useAvs,
  useAvsTrends,
  useRecommendations,
  useCitationTrends,
  useAuditSummary,
  useDistributionCoverage,
  useEntityProfile,
} from "@/hooks/useApi";

interface DashboardProps {
  brandId: string;
}

export default function Dashboard({ brandId }: DashboardProps) {
  const navigate = useNavigate();
  const avs = useAvs(brandId);
  const avsTrends = useAvsTrends(brandId);
  const recommendations = useRecommendations(brandId);
  const citationTrends = useCitationTrends(brandId);
  const auditSummary = useAuditSummary(brandId);
  const coverage = useDistributionCoverage(brandId);
  const entityProfile = useEntityProfile(brandId);

  const avsScore = avs.data?.overall_score ?? null;
  const avsDelta = avs.data?.delta ?? 0;

  const citationRate = citationTrends.data?.change_rate ?? 0;
  const entityHealth = entityProfile.data?.completeness_score ?? 0;
  const avgGeoScore = auditSummary.data?.average_score ?? 0;
  const coveragePct = coverage.data?.overall_coverage ?? 0;

  const trendData = avsTrends.data?.data_points.map((p) => ({
    timestamp: p.timestamp,
    score: p.score,
  })) ?? [];

  const recs = recommendations.data?.recommendations.slice(0, 5) ?? [];

  const alerts = [
    {
      id: "1",
      type: "warning" as const,
      title: "Citation Rate Declining",
      message: "GPT-4o citation rate dropped 12% this week",
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      module: "PULSE",
    },
    {
      id: "2",
      type: "success" as const,
      title: "New Knowledge Gap Resolved",
      message: "Entity description now recognized by Gemini",
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      module: "GRAPH",
    },
    {
      id: "3",
      type: "info" as const,
      title: "Bulk Audit Completed",
      message: "47 content assets scored, avg GEO: 62.3",
      timestamp: new Date(Date.now() - 14400000).toISOString(),
      module: "BEAM",
    },
  ];

  const alertIcon = (type: string) => {
    switch (type) {
      case "warning":
        return <AlertTriangle size={14} className="text-warning" />;
      case "success":
        return <CheckCircle size={14} className="text-success" />;
      case "danger":
        return <AlertTriangle size={14} className="text-danger" />;
      default:
        return <Info size={14} className="text-accent" />;
    }
  };

  const effortVariant = (level: string) => {
    switch (level) {
      case "low":
        return "success" as const;
      case "medium":
        return "warning" as const;
      case "high":
        return "danger" as const;
      default:
        return "neutral" as const;
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Dashboard"
        subtitle="AI Visibility overview across all modules"
      />

      {/* AVS Score */}
      <div className="flex justify-center mb-8">
        <div className="glass-panel p-8 flex flex-col items-center">
          <ScoreGauge
            score={avsScore ?? 0}
            size={180}
            label="AI Visibility Score"
            sublabel="AVS"
          />
          {avsDelta !== 0 && (
            <div
              className={`mt-3 flex items-center gap-1 text-sm font-medium ${
                avsDelta > 0 ? "text-success" : "text-danger"
              }`}
            >
              {avsDelta > 0 ? "+" : ""}
              {avsDelta.toFixed(1)} pts since last calculation
            </div>
          )}
        </div>
      </div>

      {/* Module Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<Activity size={20} />}
          label="Citation Rate"
          value={`${citationRate.toFixed(1)}%`}
          change={citationTrends.data?.change_rate}
          changeLabel="30d"
          onClick={() => navigate("/pulse")}
        />
        <StatCard
          icon={<GitBranch size={20} />}
          label="Entity Health"
          value={`${(entityHealth * 100).toFixed(0)}%`}
          onClick={() => navigate("/graph")}
        />
        <StatCard
          icon={<Zap size={20} />}
          label="Avg GEO Score"
          value={avgGeoScore.toFixed(1)}
          onClick={() => navigate("/beam")}
        />
        <StatCard
          icon={<Radio size={20} />}
          label="Coverage"
          value={`${coveragePct.toFixed(0)}%`}
          onClick={() => navigate("/signal")}
        />
      </div>

      {/* AVS Trend + Recommendations + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* AVS Trend Chart */}
        <div className="lg:col-span-2 glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-200">
              AVS Trend (30 Days)
            </h2>
            <button
              onClick={() => navigate("/intelligence")}
              className="btn-ghost text-xs flex items-center gap-1"
            >
              View Details <ArrowRight size={12} />
            </button>
          </div>
          {trendData.length > 0 ? (
            <TrendChart
              data={trendData}
              series={[
                { dataKey: "score", name: "AVS", color: "#00d4ff" },
              ]}
              yAxisDomain={[0, 100]}
              height={260}
              showLegend={false}
            />
          ) : (
            <div className="flex items-center justify-center h-[260px] text-gray-600 text-sm">
              No trend data available yet
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Recommendations */}
          <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-200">
                Top Recommendations
              </h2>
              <button
                onClick={() => navigate("/intelligence")}
                className="text-xs text-accent hover:text-accent-300 transition-colors"
              >
                View All
              </button>
            </div>
            {recs.length > 0 ? (
              <div className="space-y-3">
                {recs.map((rec, i) => (
                  <div
                    key={rec.id}
                    className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    <span className="text-xs font-bold text-accent bg-accent/10 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0">
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-300 leading-snug mb-1.5 line-clamp-2">
                        {rec.action_description}
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant={effortVariant(rec.effort_level)}>
                          {rec.effort_level}
                        </Badge>
                        <span className="text-xs text-gray-500">
                          +{rec.expected_avs_impact.toFixed(1)} AVS
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-600 py-4 text-center">
                No recommendations yet
              </p>
            )}
          </div>

          {/* Alerts */}
          <div className="glass-panel p-5">
            <h2 className="text-base font-semibold text-gray-200 mb-4">
              Recent Alerts
            </h2>
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className="mt-0.5">{alertIcon(alert.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-medium text-gray-200">
                        {alert.title}
                      </span>
                      <Badge variant="neutral">{alert.module}</Badge>
                    </div>
                    <p className="text-xs text-gray-500">{alert.message}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
