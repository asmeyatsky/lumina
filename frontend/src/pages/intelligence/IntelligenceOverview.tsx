import { useState } from "react";
import { TrendingUp, TrendingDown, RefreshCw, ArrowRight, Minus } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import ScoreGauge from "@/components/common/ScoreGauge";
import TrendChart from "@/components/common/TrendChart";
import Badge from "@/components/common/Badge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import EmptyState from "@/components/common/EmptyState";
import {
  useAvs,
  useAvsTrends,
  useRecommendations,
  useCalculateAvs,
  useRootCause,
} from "@/hooks/useApi";
import type { RootCauseAnalysisResponse } from "@/types";

interface IntelligenceOverviewProps {
  brandId: string;
}

export default function IntelligenceOverview({ brandId }: IntelligenceOverviewProps) {
  const avs = useAvs(brandId);
  const avsTrends = useAvsTrends(brandId);
  const recommendations = useRecommendations(brandId);
  const calculateAvs = useCalculateAvs(brandId);
  const rootCause = useRootCause(brandId);
  const [rcaResult, setRcaResult] = useState<RootCauseAnalysisResponse | null>(null);

  const avsScore = avs.data?.overall_score ?? 0;
  const avsDelta = avs.data?.delta ?? 0;
  const components = avs.data?.components ?? [];
  const previousScore = avs.data?.previous_score;

  const trendData =
    avsTrends.data?.data_points.map((p) => ({
      timestamp: p.timestamp,
      score: p.score,
    })) ?? [];

  const recs = recommendations.data?.recommendations ?? [];

  const handleRecalculate = async () => {
    try {
      await calculateAvs.mutateAsync({});
    } catch {
      // handled
    }
  };

  const handleRootCause = async () => {
    if (!avs.data) return;
    const currentScores: Record<string, number> = {};
    const previousScores: Record<string, number> = {};
    components.forEach((c) => {
      currentScores[c.module_name] = c.score;
      previousScores[c.module_name] = c.score * 0.9; // approximate
    });
    try {
      const result = await rootCause.mutateAsync({
        current_scores: currentScores,
        previous_scores: previousScores,
      });
      setRcaResult(result);
    } catch {
      // handled
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

  const moduleColor = (module: string): string => {
    switch (module.toLowerCase()) {
      case "pulse":
      case "citation_frequency":
        return "#00d4ff";
      case "graph":
      case "entity_depth":
        return "#a855f7";
      case "beam":
      case "content_geo":
        return "#f59e0b";
      case "signal":
      case "distribution_coverage":
        return "#22c55e";
      default:
        return "#6b7280";
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Intelligence Engine"
        subtitle="AI Visibility Score analysis and recommendations"
        actions={
          <button
            onClick={handleRecalculate}
            disabled={calculateAvs.isPending}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <RefreshCw
              size={14}
              className={calculateAvs.isPending ? "animate-spin" : ""}
            />
            {calculateAvs.isPending ? "Calculating..." : "Recalculate AVS"}
          </button>
        }
      />

      {/* AVS Score + Components */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Large AVS Score */}
        <div className="glass-panel p-8 flex flex-col items-center justify-center">
          <ScoreGauge
            score={avsScore}
            size={200}
            label="AI Visibility Score"
            sublabel="AVS"
          />
          <div className="mt-4 flex items-center gap-2">
            {avsDelta > 0 ? (
              <TrendingUp size={16} className="text-success" />
            ) : avsDelta < 0 ? (
              <TrendingDown size={16} className="text-danger" />
            ) : (
              <Minus size={16} className="text-gray-500" />
            )}
            <span
              className={`text-sm font-medium ${
                avsDelta > 0
                  ? "text-success"
                  : avsDelta < 0
                  ? "text-danger"
                  : "text-gray-500"
              }`}
            >
              {avsDelta > 0 ? "+" : ""}
              {avsDelta.toFixed(1)} pts
            </span>
            {previousScore != null && (
              <span className="text-xs text-gray-600">
                (was {previousScore.toFixed(1)})
              </span>
            )}
          </div>
        </div>

        {/* Component Breakdown */}
        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Score Components
          </h2>
          <div className="space-y-5">
            {components.length > 0 ? (
              components.map((comp) => (
                <div key={comp.module_name}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: moduleColor(comp.module_name) }}
                      />
                      <span className="text-sm font-medium text-gray-200 capitalize">
                        {comp.module_name.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-500">
                        Weight: {(comp.weight * 100).toFixed(0)}%
                      </span>
                      <span className="text-sm font-bold text-gray-100">
                        {comp.score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.min(100, comp.score)}%`,
                        backgroundColor: moduleColor(comp.module_name),
                      }}
                    />
                  </div>
                  <div className="flex justify-end mt-1">
                    <span className="text-xs text-gray-600">
                      Weighted: {comp.weighted_score.toFixed(1)}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-gray-600 text-sm">
                No component data. Click "Recalculate AVS" to generate.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* AVS Trend Chart */}
      <div className="glass-panel p-6 mb-8">
        <h2 className="text-base font-semibold text-gray-200 mb-4">
          AVS Trend
        </h2>
        {trendData.length > 0 ? (
          <TrendChart
            data={trendData}
            series={[{ dataKey: "score", name: "AVS", color: "#00d4ff" }]}
            yAxisDomain={[0, 100]}
            height={320}
            showLegend={false}
          />
        ) : (
          <div className="flex items-center justify-center h-[320px] text-gray-600 text-sm">
            No trend data available. AVS will be tracked over time.
          </div>
        )}
      </div>

      {/* Root Cause Analysis + Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Root Cause Analysis */}
        <div className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-200">
              Root Cause Analysis
            </h2>
            <button
              onClick={handleRootCause}
              disabled={rootCause.isPending}
              className="btn-ghost text-xs flex items-center gap-1"
            >
              <RefreshCw
                size={12}
                className={rootCause.isPending ? "animate-spin" : ""}
              />
              {rootCause.isPending ? "Analyzing..." : "Analyze"}
            </button>
          </div>

          {rcaResult ? (
            <div className="space-y-4">
              <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <span className="text-xs text-gray-500">Trigger:</span>
                <p className="text-sm text-gray-200 mt-0.5">{rcaResult.trigger}</p>
              </div>

              {rcaResult.causes.map((cause, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-medium text-gray-200">
                      {cause.factor}
                    </span>
                    <Badge variant="neutral">
                      {(cause.contribution_weight * 100).toFixed(0)}% weight
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-400">{cause.evidence}</p>
                  <Badge variant="info" className="mt-2">
                    {cause.module}
                  </Badge>
                </div>
              ))}

              {rcaResult.recommended_actions.length > 0 && (
                <div className="pt-3 border-t border-white/[0.06]">
                  <h3 className="text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Recommended Actions
                  </h3>
                  <ul className="space-y-1.5">
                    {rcaResult.recommended_actions.map((action, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                        <ArrowRight size={14} className="text-accent mt-0.5 flex-shrink-0" />
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-600 text-sm">
              {avsDelta < 0
                ? "AVS has dropped. Click Analyze to understand why."
                : "Run root cause analysis when AVS changes significantly."}
            </div>
          )}
        </div>

        {/* Recommendation Queue */}
        <div className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-200">
              Recommendation Queue
            </h2>
            {recs.length > 0 && (
              <span className="text-xs text-gray-500">
                {recs.length} recommendations
              </span>
            )}
          </div>

          {recs.length > 0 ? (
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
              {recs.map((rec) => (
                <div
                  key={rec.id}
                  className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <p className="text-sm text-gray-200 leading-snug">
                      {rec.action_description}
                    </p>
                    <span className="text-xs text-gray-500 flex-shrink-0 font-mono">
                      #{rec.priority_rank}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={effortVariant(rec.effort_level)}>
                      {rec.effort_level} effort
                    </Badge>
                    <Badge variant="success">
                      +{rec.expected_avs_impact.toFixed(1)} AVS
                    </Badge>
                    <Badge variant="neutral">{rec.source_module}</Badge>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <button className="btn-ghost text-xs flex items-center gap-1">
                      Take Action <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No recommendations yet"
              description="Calculate your AVS score to receive prioritized recommendations"
              action={{ label: "Calculate AVS", onClick: handleRecalculate }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
